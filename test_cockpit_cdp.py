import subprocess
import time
import urllib.request
import json
import asyncio
import sys
import os
import tempfile
import hashlib
import socket
import shutil
from pathlib import Path
import websockets

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')

def find_browser_executable():
    env = os.environ
    candidates = [
        Path(env.get("ProgramFiles(x86)", "")) / "Microsoft" / "Edge" / "Application" / "msedge.exe",
        Path(env.get("ProgramFiles", "")) / "Microsoft" / "Edge" / "Application" / "msedge.exe",
        Path(env.get("LOCALAPPDATA", "")) / "Microsoft" / "Edge" / "Application" / "msedge.exe",
        Path(env.get("LOCALAPPDATA", "")) / "BraveSoftware" / "Brave-Browser" / "Application" / "brave.exe",
        Path(env.get("ProgramFiles", "")) / "BraveSoftware" / "Brave-Browser" / "Application" / "brave.exe",
        Path(env.get("ProgramFiles(x86)", "")) / "BraveSoftware" / "Brave-Browser" / "Application" / "brave.exe",
        Path(env.get("ProgramFiles", "")) / "Google" / "Chrome" / "Application" / "chrome.exe",
        Path(env.get("ProgramFiles(x86)", "")) / "Google" / "Chrome" / "Application" / "chrome.exe",
    ]
    for c in candidates:
        if c.is_file():
            return str(c)
    raise RuntimeError("No compatible Chromium browser found (Brave, Edge, or Chrome)")

BROWSER_PATH = find_browser_executable()
HTML_PATH = Path(__file__).resolve().parent / "paralleldoc.html"
HTML_URL = HTML_PATH.as_uri()
PROFILE_DIR = tempfile.mkdtemp(prefix="paralleldoc_cdp_test_")

def find_free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]

class CDPClient:
    def __init__(self, port=None):
        self.port = port or find_free_port()
        self.proc = None
        self.ws = None
        self.msg_id = 0

    def start(self):
        self.proc = subprocess.Popen([
            BROWSER_PATH,
            "--headless=new",
            f"--remote-debugging-port={self.port}",
            f"--user-data-dir={PROFILE_DIR}",
            "--disable-gpu",
            "--allow-file-access-from-files",
            HTML_URL
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(2)

    async def connect(self):
        for _ in range(10):
            try:
                with urllib.request.urlopen(f"http://127.0.0.1:{self.port}/json") as r:
                    pages = json.loads(r.read().decode())
                    if pages:
                        ws_url = pages[0]["webSocketDebuggerUrl"]
                        self.ws = await websockets.connect(ws_url)
                        return
            except Exception:
                await asyncio.sleep(0.5)
        raise RuntimeError("Could not connect to browser CDP")

    async def eval_js(self, expression, await_promise=False):
        self.msg_id += 1
        req = {
            "id": self.msg_id,
            "method": "Runtime.evaluate",
            "params": {
                "expression": expression,
                "returnByValue": True,
                "awaitPromise": await_promise
            }
        }
        await self.ws.send(json.dumps(req))
        while True:
            resp_raw = await self.ws.recv()
            resp = json.loads(resp_raw)
            if resp.get("id") == self.msg_id:
                result = resp.get("result", {})
                if "exceptionDetails" in result:
                    raise RuntimeError(f"JS Exception: {result['exceptionDetails']}")
                return result.get("result", {}).get("value")

    async def close(self):
        if self.ws:
            await self.ws.close()
        if self.proc:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=3)
            except Exception:
                self.proc.kill()
        shutil.rmtree(PROFILE_DIR, ignore_errors=True)

async def run_tests():
    client = CDPClient()
    client.start()
    try:
        await client.connect()
        print(f"Connected to headless browser via CDP ({Path(BROWSER_PATH).name}).")

        # Test 1: Document title and basic metadata
        title = await client.eval_js("document.title")
        print(f"Test 1 - Title: {title}")
        assert "ParallelDoc" in title

        # Test 2: Full SHA-256 visibly displayed on screen (Anti-Drift Header requirement)
        hash_text = await client.eval_js("document.getElementById('hashText').textContent")
        print(f"Test 2 - Visible Hash text: {hash_text}")

        full_hash = await client.eval_js("currentFullHash")
        print(f"Test 2 - Internal Full hash: {full_hash}")

        # Compute expected hash from active_document.json / sample_document.json
        sample_file = Path(__file__).resolve().parent / "sample_document.json"
        normalized_bytes = sample_file.read_text(encoding="utf-8").replace("\r\n", "\n").encode("utf-8")
        EXPECTED_HASH = hashlib.sha256(normalized_bytes).hexdigest()

        assert full_hash == EXPECTED_HASH, f"Expected {EXPECTED_HASH}, got {full_hash}"
        assert hash_text == EXPECTED_HASH, f"Expected visible hashText {EXPECTED_HASH}, got {hash_text}"
        assert len(hash_text) == 64, f"Hash text must be full 64 characters, got {len(hash_text)}"
        print(f"✅ Test 2 Passed: Full 64-char SHA-256 is visibly rendered in DOM: {EXPECTED_HASH}")

        # Test 3: Rows rendering
        row_count = await client.eval_js("document.querySelectorAll('.doc-row').length")
        print(f"Test 3 - Row count: {row_count}")
        assert row_count == 5

        # Test 4: Markdown list grouping
        ul_count = await client.eval_js("document.querySelectorAll('#row-1 .col3 ul').length")
        li_count = await client.eval_js("document.querySelectorAll('#row-1 .col3 li').length")
        print(f"Test 4 - col3 <ul> count: {ul_count}, <li> count: {li_count}")
        assert ul_count == 1, f"Expected 1 <ul>, got {ul_count}"
        assert li_count == 3, f"Expected 3 <li>, got {li_count}"
        print("✅ Test 4 Passed: Markdown lists are cleanly grouped into a single <ul>")

        # Test 5: Marker creation (Yellow highlight)
        js_select = """
        (() => {
            const el = document.querySelector('#row-1 .col1 p');
            const range = document.createRange();
            range.setStart(el.firstChild, 0);
            range.setEnd(el.firstChild, 10);
            const sel = window.getSelection();
            sel.removeAllRanges();
            sel.addRange(range);
            return sel.toString();
        })()
        """
        selected_text = await client.eval_js(js_select)
        print(f"Test 5 - Selected text: '{selected_text}'")

        # Apply yellow highlight
        await client.eval_js("applyHighlight('hl-yellow')")
        mark_count = await client.eval_js("document.querySelectorAll('mark.hl-yellow').length")
        mark_text = await client.eval_js("document.querySelector('mark.hl-yellow')?.textContent")
        print(f"Test 5 - Mark count: {mark_count}, Mark text: '{mark_text}'")
        assert mark_count == 1

        # Test 6: Click on mark to remove it (Direct click clearing)
        js_click_mark = """
        (() => {
            const mark = document.querySelector('mark.hl-yellow');
            if (!mark) return false;
            window.getSelection().removeAllRanges();
            const evt = new MouseEvent('click', { bubbles: true, cancelable: true, view: window });
            mark.dispatchEvent(evt);
            return true;
        })()
        """
        clicked = await client.eval_js(js_click_mark)
        mark_count_after_click = await client.eval_js("document.querySelectorAll('mark.hl-yellow').length")
        print(f"Test 6 - Direct click mark removed: {mark_count_after_click == 0} (count: {mark_count_after_click})")
        assert mark_count_after_click == 0
        print("✅ Test 6 Passed: Direct click on <mark> unwraps it")

        # Test 7: Selection clearing with btnHlClear
        await client.eval_js("""
        (() => {
            const el = document.querySelector('#row-1 .col1 p');
            const range = document.createRange();
            range.setStart(el.firstChild, 0);
            range.setEnd(el.firstChild, 10);
            const sel = window.getSelection();
            sel.removeAllRanges();
            sel.addRange(range);
            applyHighlight('hl-red');
        })()
        """)
        mark_red_count = await client.eval_js("document.querySelectorAll('mark.hl-red').length")
        assert mark_red_count == 1

        js_clear_selection = """
        (() => {
            const row = document.querySelector('#row-1 .col1 p');
            const range = document.createRange();
            range.selectNodeContents(row);
            const sel = window.getSelection();
            sel.removeAllRanges();
            sel.addRange(range);

            clearSelectedHighlights();
            return document.querySelectorAll('mark').length;
        })()
        """
        remaining_marks = await client.eval_js(js_clear_selection)
        print(f"Test 7 - Remaining marks after clearSelectedHighlights: {remaining_marks}")
        assert remaining_marks == 0
        print("✅ Test 7 Passed: clearSelectedHighlights unwraps all marks in selection")

        # Test 8: Protection against cross-column / cross-cell selection
        js_cross_col = """
        (() => {
            const row1 = document.querySelector('#row-1');
            const col1 = row1.querySelector('.col1 p');
            const col2 = row1.querySelector('.col2 p');
            const range = document.createRange();
            range.setStart(col1.firstChild, 0);
            range.setEnd(col2.firstChild, 10);
            const sel = window.getSelection();
            sel.removeAllRanges();
            sel.addRange(range);

            // Attempt to highlight across columns
            applyHighlight('hl-yellow');

            const gridChildren = row1.querySelector('.row-grid').children.length;
            const marks = row1.querySelectorAll('mark').length;
            return { gridChildren, marks };
        })()
        """
        cross_res = await client.eval_js(js_cross_col)
        print(f"Test 8 - Cross-column protection result: {cross_res}")
        assert cross_res['gridChildren'] == 3, f"Grid children corrupted! Count: {cross_res['gridChildren']}"
        assert cross_res['marks'] == 0, f"Cross-col mark should be rejected! Marks: {cross_res['marks']}"
        print("✅ Test 8 Passed: Cross-cell selection is rejected, grid layout preserved at exactly 3 columns")

        # Test 9: Search and scroll
        js_search = """
        (() => {
            const searchInput = document.getElementById('searchInput');
            searchInput.value = 'AES-256';
            handleSearch(true);
            return {
                matches: searchMatches.length,
                displayedRows: Array.from(document.querySelectorAll('.doc-row')).filter(r => r.style.display !== 'none').length
            };
        })()
        """
        search_res = await client.eval_js(js_search)
        print(f"Test 9 - Search 'AES-256': {search_res}")
        assert search_res['matches'] == 1
        assert search_res['displayedRows'] == 1

        # Test 10: Enter key navigation in search
        js_enter = """
        (() => {
            const searchInput = document.getElementById('searchInput');
            const evt = new KeyboardEvent('keydown', { key: 'Enter', bubbles: true });
            searchInput.dispatchEvent(evt);
            return currentMatchIndex;
        })()
        """
        match_idx = await client.eval_js(js_enter)
        print(f"Test 10 - Match index after Enter: {match_idx}")
        assert match_idx == 0

        # Test 11: Escape key resets search
        js_escape = """
        (() => {
            const searchInput = document.getElementById('searchInput');
            const evt = new KeyboardEvent('keydown', { key: 'Escape', bubbles: true });
            searchInput.dispatchEvent(evt);
            return {
                val: searchInput.value,
                displayedRows: Array.from(document.querySelectorAll('.doc-row')).filter(r => r.style.display !== 'none').length
            };
        })()
        """
        esc_res = await client.eval_js(js_escape)
        print(f"Test 11 - Escape search reset: {esc_res}")
        assert esc_res['val'] == ''
        assert esc_res['displayedRows'] == 5
        print("✅ Test 11 Passed: Search and escape reset work cleanly")

        # Test 12: Row and cell clipboard text
        js_clipboard = """
        (() => {
            copyRowId('1');
            const rowText = window.__lastCopiedText;
            copyCell('1', 0);
            const cellText = window.__lastCopiedText;
            return { rowText, cellText };
        })()
        """
        clip_res = await client.eval_js(js_clipboard)
        print(f"Test 12 - Clipboard result: {clip_res}")
        assert "Original Clause (EN)\n" in clip_res["rowText"]
        assert "Target Translation (UA)\n" in clip_res["rowText"]
        assert "Engineering & Risk Assessment (EN)\n" in clip_res["rowText"]
        assert "**" not in clip_res["rowText"]
        assert clip_res["cellText"].startswith("1. High Availability")
        assert "Target Translation" not in clip_res["cellText"]
        print("✅ Test 12 Passed: Row and cell copying produce clean structured text")

        # Test 13: JSON column weights and manual ratio modes
        ratio_res = await client.eval_js("""
        (() => {
            userPrefs.ratio = 'from-json';
            applyUserPrefs();
            const fromJson = [
                getComputedStyle(document.documentElement).getPropertyValue('--col1-w').trim(),
                getComputedStyle(document.documentElement).getPropertyValue('--col2-w').trim(),
                getComputedStyle(document.documentElement).getPropertyValue('--col3-w').trim()
            ];
            userPrefs.ratio = '25-25-50';
            applyUserPrefs();
            const manual = getComputedStyle(document.documentElement).getPropertyValue('--col3-w').trim();
            userPrefs.ratio = 'from-json';
            applyUserPrefs();
            return { fromJson, manual };
        })()
        """)
        print(f"Test 13 - Ratios: {ratio_res}")
        assert ratio_res["fromJson"] == ["30.0000fr", "30.0000fr", "40.0000fr"]
        assert ratio_res["manual"] == "50fr"
        print("✅ Test 13 Passed: JSON and manual column ratios work")

        # Test 14: Data rows scroll normally and every cell exposes a copy button
        sticky_res = await client.eval_js("""
        (() => ({
            position: getComputedStyle(document.querySelector('.doc-row:first-child')).position,
            copyButtons: document.querySelectorAll('.cell-copy-btn').length,
            firstRowButtons: document.querySelectorAll('.doc-row:first-child .cell-copy-btn').length
        }))()
        """)
        print(f"Test 14 - Sticky/copy UI: {sticky_res}")
        assert sticky_res["position"] == "static"
        assert sticky_res["copyButtons"] == 15
        assert sticky_res["firstRowButtons"] == 3
        print("✅ Test 14 Passed: Data rows remain unpinned and cell copy buttons render")

        # Test 15: In-memory JSON history, navigation, and forward-branch truncation
        history_res = await client.eval_js("""
        (async () => {
            const doc2 = JSON.parse(JSON.stringify(currentDoc));
            doc2.metadata.title = 'History document 2';
            await addDocumentToHistory(doc2, JSON.stringify(doc2), 'second.json');
            await navigateHistory(-1);
            const afterBack = { index: currentHistoryIndex, file: currentFileName };
            const doc3 = JSON.parse(JSON.stringify(currentDoc));
            doc3.metadata.title = 'History document 3';
            await addDocumentToHistory(doc3, JSON.stringify(doc3), 'third.json');
            return {
                afterBack,
                index: currentHistoryIndex,
                length: documentHistory.length,
                file: currentFileName,
                forwardDisabled: document.getElementById('historyForward').disabled
            };
        })()
        """, await_promise=True)
        print(f"Test 15 - History: {history_res}")
        assert history_res["afterBack"]["index"] == 0
        assert history_res["length"] == 2
        assert history_res["index"] == 1
        assert history_res["file"] == "third.json"
        assert history_res["forwardDisabled"] is True
        print("✅ Test 15 Passed: Session history navigates and truncates forward branches")

    finally:
        await client.close()

if __name__ == "__main__":
    asyncio.run(run_tests())
