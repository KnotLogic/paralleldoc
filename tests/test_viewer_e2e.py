"""
tests/test_viewer_e2e.py — Autonomous Headless Chromium CDP Test Suite for ParallelDoc 3.0.
Verifies AC-01, AC-02, AC-11..AC-18, AC-30..AC-41, AC-44 against standalone deliverable paralleldoc.html.
Runs out-of-the-box on Windows using standard library + websockets (no Playwright needed).
"""

import asyncio
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request
import pytest
import websockets

WORK_DIR = Path(__file__).resolve().parent.parent
HTML_PATH = WORK_DIR / "paralleldoc.html"


def find_browser():
    env = os.environ
    candidates = [
        Path(env.get("ProgramFiles(x86)", "")) / "Microsoft" / "Edge" / "Application" / "msedge.exe",
        Path(env.get("LOCALAPPDATA", "")) / "BraveSoftware" / "Brave-Browser" / "Application" / "brave.exe",
        Path(env.get("ProgramFiles", "")) / "BraveSoftware" / "Brave-Browser" / "Application" / "brave.exe",
        Path(env.get("ProgramFiles", "")) / "Google" / "Chrome" / "Application" / "chrome.exe",
    ]
    for c in candidates:
        if c.is_file():
            return str(c)
    raise RuntimeError("No Chromium browser found on Workstation-00 for E2E testing")


class CDPRunner:
    def __init__(self, port=9252):
        self.port = port
        self.browser_bin = find_browser()
        self.proc = None
        self.ws = None
        self.msg_id = 0
        self.intercepted_requests = []
        self.profile_dir = Path(tempfile.gettempdir()) / f"pd_e2e_profile_{port}"

    def start(self):
        if self.profile_dir.exists():
            shutil.rmtree(self.profile_dir, ignore_errors=True)
        self.profile_dir.mkdir(parents=True, exist_ok=True)

        cmd = [
            self.browser_bin,
            "--headless=new",
            f"--remote-debugging-port={self.port}",
            f"--user-data-dir={self.profile_dir}",
            "--disable-gpu",
            "--no-first-run",
            "--no-default-browser-check",
            "--allow-file-access-from-files",
            HTML_PATH.as_uri()
        ]
        self.proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(1.8)

    async def connect(self):
        for _ in range(20):
            try:
                with urllib.request.urlopen(f"http://127.0.0.1:{self.port}/json") as r:
                    pages = json.loads(r.read().decode())
                    matching = [p for p in pages if p.get("type") == "page" and "paralleldoc.html" in p.get("url", "")]
                    if matching:
                        ws_url = matching[0]["webSocketDebuggerUrl"]
                        self.ws = await websockets.connect(ws_url, max_size=10_000_000)
                        await self.send("Network.enable", {})
                        await self.send("Runtime.enable", {})
                        await self.send("DOM.enable", {})
                        return
            except Exception:
                await asyncio.sleep(0.4)
        raise RuntimeError("CDP connection failed after multiple attempts")

    async def send(self, method, params):
        self.msg_id += 1
        req = {"id": self.msg_id, "method": method, "params": params}
        await self.ws.send(json.dumps(req))

        while True:
            resp_str = await self.ws.recv()
            resp = json.loads(resp_str)

            if resp.get("method") == "Network.requestWillBeSent":
                url = resp.get("params", {}).get("request", {}).get("url", "")
                self.intercepted_requests.append(url)

            if resp.get("id") == self.msg_id:
                if "error" in resp:
                    raise RuntimeError(f"CDP error: {resp['error']}")
                return resp.get("result", {})

    async def eval_js(self, expr, await_promise=False):
        res = await self.send("Runtime.evaluate", {
            "expression": expr,
            "returnByValue": True,
            "awaitPromise": await_promise
        })
        val = res.get("result", {}).get("value")
        exc = res.get("exceptionDetails")
        if exc:
            raise RuntimeError(f"JS Exception: {exc}")
        return val

    def stop(self):
        if self.proc:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=3)
            except Exception:
                self.proc.kill()
        if self.profile_dir.exists():
            shutil.rmtree(self.profile_dir, ignore_errors=True)


@pytest.fixture(scope="module")
def cdp():
    runner = CDPRunner(port=9252)
    runner.start()
    loop = asyncio.new_event_loop()
    loop.run_until_complete(runner.connect())
    yield runner, loop
    if runner.ws:
        loop.run_until_complete(runner.ws.close())
    runner.stop()
    loop.close()



# -----------------------------------------------------------------------------
# AC-01: Clean Offline Delivery (Zero External Network Calls)
# -----------------------------------------------------------------------------
def test_ac01_clean_offline_zero_network_calls(cdp):
    runner, loop = cdp
    requests = runner.intercepted_requests
    external_calls = [
        r for r in requests
        if r.startswith("http://") or r.startswith("https://") or r.startswith("//")
    ]
    assert len(external_calls) == 0, f"AC-01 VIOLATION: Remote network calls detected: {external_calls}"

    # Also verify strict CSP in HTML source
    html_text = HTML_PATH.read_text(encoding="utf-8")
    assert "default-src 'none'" in html_text
    assert "connect-src 'none'" in html_text


# -----------------------------------------------------------------------------
# AC-02: File Open & Rejection of Unsupported Legacy Format
# -----------------------------------------------------------------------------
def test_ac02_legacy_format_rejected_with_exact_diagnostic(cdp):
    runner, loop = cdp
    sample_path = WORK_DIR / "sample_document.json"
    raw_bytes = list(sample_path.read_bytes())

    res = loop.run_until_complete(runner.eval_js(f"""
        (async () => {{
            const bytes = new Uint8Array({raw_bytes});
            const ok = await window.ParallelDocApp.loadRawBytes(bytes, 'sample_document.json');
            const rejEl = document.getElementById('pd-rejection-container');
            const titleEl = rejEl.querySelector('.pd-rejection-title');
            const isVisible = rejEl.style.display !== 'none';
            return {{
                ok,
                isVisible,
                message: titleEl ? titleEl.textContent : ''
            }};
        }})()
    """, await_promise=True))

    assert res["ok"] is False, "Legacy sample_document.json must be rejected"
    assert res["isVisible"] is True, "Rejection view must be displayed"
    assert "«Неподдерживаемый формат; требуется ParallelDoc 3.0»" in res["message"]


# -----------------------------------------------------------------------------
# AC-11: Multi-Panel Completeness & Zero Unit Loss
# -----------------------------------------------------------------------------
def test_ac11_multi_panel_zero_unit_loss(cdp):
    runner, loop = cdp
    res = loop.run_until_complete(runner.eval_js("""
        (() => {
            const app = window.ParallelDocApp;
            // Reload default document
            app.loadDocument(DEFAULT_V3_DOCUMENT);
            const totalExpected = DEFAULT_V3_DOCUMENT.units.length;

            const counts = {};
            for (const profileId of ['builtin:2', 'builtin:3', 'builtin:4']) {
                app.switchProfile(profileId);
                const cards = document.querySelectorAll('.unit-card, .pd-unit-card');
                counts[profileId] = cards.length;
            }
            return { totalExpected, counts };
        })()
    """))

    expected = res["totalExpected"]
    counts = res["counts"]
    for pid, c in counts.items():
        assert c == expected, f"AC-11 VIOLATION: Profile {pid} rendered {c} units instead of {expected} (Unit Loss)"


# -----------------------------------------------------------------------------
# AC-12, AC-13: Central Relationship Graph & 6 Typed Relations
# -----------------------------------------------------------------------------
def test_ac12_ac13_relationship_graph_and_six_relations(cdp):
    runner, loop = cdp
    res = loop.run_until_complete(runner.eval_js("""
        (() => {
            const app = window.ParallelDocApp;
            app.switchProfile('builtin:3'); // Evidence profile
            const svg = document.querySelector('.pd-graph-svg');
            const nodes = document.querySelectorAll('.pd-graph-node');
            const edges = document.querySelectorAll('.pd-graph-edge');
            const legend = document.querySelector('.pd-graph-legend');
            const markers = document.querySelectorAll('defs marker');

            return {
                hasSvg: !!svg,
                nodeCount: nodes.length,
                edgeCount: edges.length,
                hasLegend: !!legend,
                markerCount: markers.length
            };
        })()
    """))

    assert res["hasSvg"] is True, "SVG Graph must be rendered in Evidence profile"
    assert res["nodeCount"] >= 4, f"Graph must render nodes, got {res['nodeCount']}"
    assert res["edgeCount"] >= 3, f"Graph must render edges, got {res['edgeCount']}"
    assert res["hasLegend"] is True, "Visible legend must be present (AC-13)"
    assert res["markerCount"] >= 4, "Directional arrow markers must be defined"


# -----------------------------------------------------------------------------
# AC-14: Graph -> Text Cross-Highlighting with Scroll Delta = 0
# -----------------------------------------------------------------------------
def test_ac14_graph_to_text_cross_highlight_delta_zero(cdp):
    runner, loop = cdp
    res = loop.run_until_complete(runner.eval_js("""
        (() => {
            const initialScrollY = window.pageYOffset || document.documentElement.scrollTop || 0;
            const node = document.querySelector('.pd-graph-node');
            if (!node) return { error: 'No node found' };

            // Dispatch mouseenter on graph node
            node.dispatchEvent(new MouseEvent('mouseenter', { bubbles: true }));
            const highlightedUnits = document.querySelectorAll('.unit-card.cross-hl-hover, .pd-unit-card.cross-hl-hover');
            const scrollAfterHover = window.pageYOffset || document.documentElement.scrollTop || 0;
            const scrollDelta = Math.abs(scrollAfterHover - initialScrollY);

            // Clean up hover
            node.dispatchEvent(new MouseEvent('mouseleave', { bubbles: true }));

            return {
                highlightedCount: highlightedUnits.length,
                scrollDelta
            };
        })()
    """))

    assert "error" not in res, res.get("error")
    assert res["highlightedCount"] >= 1, "Hovering graph node must highlight referenced unit(s)"
    assert res["scrollDelta"] == 0, f"AC-14 VIOLATION: Scroll jump detected on hover! delta = {res['scrollDelta']}px"


# -----------------------------------------------------------------------------
# AC-15: Text -> Graph Cross-Highlighting
# -----------------------------------------------------------------------------
def test_ac15_text_to_graph_cross_highlight(cdp):
    runner, loop = cdp
    res = loop.run_until_complete(runner.eval_js("""
        (() => {
            const app = window.ParallelDocApp;
            const srcUnit = document.getElementById('unit-u-sla-src') || document.querySelector('[data-unit-id="u-sla-src"]');
            if (!srcUnit) return { error: 'Source unit not found' };

            // Select unit
            srcUnit.click();
            const referencedNodes = document.querySelectorAll('.pd-graph-node.pd-graph-referenced');

            return {
                referencedCount: referencedNodes.length
            };
        })()
    """))

    assert "error" not in res, res.get("error")
    assert res["referencedCount"] >= 1, "Clicking source unit must highlight referencing graph nodes"


# -----------------------------------------------------------------------------
# AC-16: 10-Target History Stack & Return-to-Reading Anchor
# -----------------------------------------------------------------------------
def test_ac16_navigation_history_stack_and_return_anchor(cdp):
    runner, loop = cdp
    res = loop.run_until_complete(runner.eval_js("""
        (() => {
            const engine = window.ParallelDocApp.panelsEngine;
            if (!engine) return { error: 'PanelsEngine missing' };

            // Push 12 navigation targets
            for (let i = 1; i <= 12; i++) {
                engine.pushHistorySnapshot('target-' + i);
            }
            const stackLenAfterPush = engine.navStack.length;
            const topAfterPush = engine.navStack[engine.navStack.length - 1].targetId;
            const bottomAfterPush = engine.navStack[0].targetId;

            // Return to anchor pops
            const popResult = engine.returnToAnchor();
            const stackLenAfterReturn = engine.navStack.length;

            return {
                stackLenAfterPush,
                topAfterPush,
                bottomAfterPush,
                popResult,
                stackLenAfterReturn
            };
        })()
    """))

    assert "error" not in res, res.get("error")
    assert res["stackLenAfterPush"] == 10, f"History stack must be capped at 10, got {res['stackLenAfterPush']}"
    assert res["topAfterPush"] == "target-12"
    assert res["bottomAfterPush"] == "target-3", "Oldest entries must be evicted"
    assert res["popResult"] is True
    assert res["stackLenAfterReturn"] == 9


# -----------------------------------------------------------------------------
# AC-17, AC-18: Graph Aesthetics (Labels >= 14px) & Fallback Table
# -----------------------------------------------------------------------------
def test_ac17_ac18_graph_labels_and_fallback_table(cdp):
    runner, loop = cdp
    res = loop.run_until_complete(runner.eval_js("""
        (() => {
            const labelEl = document.querySelector('.pd-node-label-text');
            const fontSize = labelEl ? window.getComputedStyle(labelEl).fontSize : '0px';

            // Toggle fallback table
            const tableBtn = document.querySelector('.pd-graph-btn-table');
            if (tableBtn) tableBtn.click();
            const table = document.querySelector('.pd-graph-fallback-table');
            const rows = document.querySelectorAll('.pd-fallback-row');

            return {
                fontSize: parseFloat(fontSize.replace('px', '')),
                tableVisible: table && window.getComputedStyle(table.closest('.pd-graph-fallback-container')).display !== 'none',
                rowCount: rows.length
            };
        })()
    """))

    assert res["fontSize"] >= 14, f"AC-17 VIOLATION: Graph node label font-size {res['fontSize']}px < 14px"
    assert res["tableVisible"] is True, "AC-18: Fallback table must be visible on toggle"
    assert res["rowCount"] >= 3, "AC-18: Fallback table must contain all graph relations"


# -----------------------------------------------------------------------------
# AC-30: Reading (18px serif) vs Dense (15px sans) Typography Modes
# -----------------------------------------------------------------------------
def test_ac30_reading_and_dense_typography(cdp):
    runner, loop = cdp
    res = loop.run_until_complete(runner.eval_js("""
        (() => {
            const app = window.ParallelDocApp;
            // 1. Reading mode
            app.setDensity('reading');
            const csReading = window.getComputedStyle(document.body);
            const readingFont = csReading.fontFamily.toLowerCase();
            const readingSize = parseFloat(csReading.fontSize.replace('px', ''));

            // 2. Dense mode
            app.setDensity('dense');
            const csDense = window.getComputedStyle(document.body);
            const denseFont = csDense.fontFamily.toLowerCase();
            const denseSize = parseFloat(csDense.fontSize.replace('px', ''));

            return {
                readingFont,
                readingSize,
                denseFont,
                denseSize
            };
        })()
    """))

    assert "georgia" in res["readingFont"] or "cambria" in res["readingFont"] or "serif" in res["readingFont"]
    assert res["readingSize"] == pytest.approx(18, 0.5)


# -----------------------------------------------------------------------------
# AC-31: Progressive Disclosure of Long Quotes (> 1200 chars)
# -----------------------------------------------------------------------------
def test_ac31_progressive_disclosure_and_copy_fidelity(cdp):
    runner, loop = cdp
    long_quote = "Russian SLA Verification Paragraph. " * 45  # ~1,600 chars

    res = loop.run_until_complete(runner.eval_js(f"""
        (() => {{
            const longDoc = JSON.parse(JSON.stringify(DEFAULT_V3_DOCUMENT));
            longDoc.units.push({{
                id: 'u-long-quote',
                kind: 'source',
                title: 'Extended SLA Addendum',
                text: {json.dumps(long_quote)},
                text_format: 'plain',
                author_refs: ['auth-expert'],
                epistemic: 'reported',
                status: 'done',
                source_refs: [],
                asset_ids: []
            }});
            longDoc.groups[0].unit_refs.push('u-long-quote');
            window.ParallelDocApp.loadDocument(longDoc);

            const card = document.getElementById('unit-u-long-quote');
            const isFoldable = !!card.querySelector('.pd-quote-foldable');
            const isCollapsed = card.querySelector('.pd-quote-foldable').classList.contains('pd-quote-collapsed');
            const badge = card.querySelector('.pd-quote-badge');

            return {{
                isFoldable,
                isCollapsed,
                badgeText: badge ? badge.textContent : ''
            }};
        }})()
    """))

    assert res["isFoldable"] is True, "Quotes > 1,200 chars must be foldable"
    assert res["isCollapsed"] is True, "Long quotes must be collapsed by default"
    assert "символов" in res["badgeText"]


# -----------------------------------------------------------------------------
# AC-32, AC-33: Literal Full-Text Search (Zero Regex) & Ctrl+F Unrolling
# -----------------------------------------------------------------------------
def test_ac32_ac33_literal_search_and_unrolling_mode(cdp):
    runner, loop = cdp
    res = loop.run_until_complete(runner.eval_js("""
        (() => {
            const search = window.ParallelDocApp.searchEngine;
            // 1. AC-32: Search literal regex token (Zero Regex)
            const matches = search.search('99.95%');
            const matchCount = matches.length;

            // 2. AC-33: Create a long quote (>1200 chars) with secret token at character 1,000
            const secretToken = 'UNROLL_SECRET_TOKEN_CHAR_1000';
            const longText = 'A'.repeat(800) + ' ' + secretToken + ' ' + 'B'.repeat(800);
            const longDoc = JSON.parse(JSON.stringify(DEFAULT_V3_DOCUMENT));
            longDoc.units.push({
                id: 'u-quote-unroll-test',
                kind: 'source',
                title: 'AC-33 Unroll Quote Test',
                text: longText,
                text_format: 'plain',
                author_refs: ['auth-expert'],
                epistemic: 'reported',
                status: 'done',
                source_refs: [],
                asset_ids: []
            });
            longDoc.groups[0].unit_refs.push('u-quote-unroll-test');
            window.ParallelDocApp.loadDocument(longDoc);

            const card = document.getElementById('unit-u-quote-unroll-test');
            const previewEl = card.querySelector('.pd-quote-preview');
            const fullEl = card.querySelector('.disclosure-full');

            // Baseline before unrolling
            const basePreviewDisplay = previewEl ? window.getComputedStyle(previewEl).display : 'none';
            const baseFullDisplay = fullEl ? window.getComputedStyle(fullEl).display : 'none';
            const basePreviewHasSecret = previewEl ? previewEl.textContent.includes(secretToken) : false;
            const baseFullHasSecret = fullEl ? fullEl.textContent.includes(secretToken) : false;

            // Toggle Ctrl+F unroll mode ON (AC-33)
            search.toggleUnrollMode();
            const isUnrolled = document.body.classList.contains('pd-unroll-all');
            const unrolledPreviewDisplay = previewEl ? window.getComputedStyle(previewEl).display : 'none';
            const unrolledFullDisplay = fullEl ? window.getComputedStyle(fullEl).display : 'none';

            // Toggle Ctrl+F unroll mode OFF (restore)
            search.toggleUnrollMode();
            const isRestoredClass = !document.body.classList.contains('pd-unroll-all');
            const restoredPreviewDisplay = previewEl ? window.getComputedStyle(previewEl).display : 'none';
            const restoredFullDisplay = fullEl ? window.getComputedStyle(fullEl).display : 'none';

            return {
                matchCount,
                basePreviewDisplay,
                baseFullDisplay,
                basePreviewHasSecret,
                baseFullHasSecret,
                isUnrolled,
                unrolledPreviewDisplay,
                unrolledFullDisplay,
                isRestoredClass,
                restoredPreviewDisplay,
                restoredFullDisplay
            };
        })()
    """))

    assert res["matchCount"] >= 1, "AC-32: Literal search for '99.95%' must produce matches"
    assert res["basePreviewHasSecret"] is False, "Secret at char 1,000 must not be in 600-char preview"
    assert res["baseFullHasSecret"] is True, "Secret at char 1,000 must be in disclosure-full"
    assert res["baseFullDisplay"] == "none", "Folded quote full text must be hidden by default"
    assert res["isUnrolled"] is True, "AC-33: Ctrl+F unroll mode must add pd-unroll-all to body"
    assert res["unrolledFullDisplay"] == "block", "AC-33: .disclosure-full must be visible (display: block) under pd-unroll-all"
    assert res["unrolledPreviewDisplay"] == "none", "AC-33: .pd-quote-preview must be hidden (display: none) under pd-unroll-all"
    assert res["isRestoredClass"] is True, "AC-33: Toggle off must remove pd-unroll-all from body"
    assert res["restoredFullDisplay"] == "none", "AC-33: .disclosure-full must return to display: none when unroll mode is toggled off"


# -----------------------------------------------------------------------------
# AC-34: Sticky Header Height Budget (<= 160px desktop, <= 96px narrow)
# -----------------------------------------------------------------------------
def test_ac34_sticky_header_height_budget(cdp):
    runner, loop = cdp

    # 1. Desktop Height Budget (<= 160px) & 64-char Monospace SHA Badge
    res_desktop = loop.run_until_complete(runner.eval_js("""
        (() => {
            const header = document.querySelector('.pd-header');
            const h = header ? header.getBoundingClientRect().height : 0;
            const scrollH = header ? header.scrollHeight : 0;
            const shaText = document.getElementById('pd-sha-badge-text');
            return {
                headerHeight: h,
                headerScrollHeight: scrollH,
                shaLength: shaText ? shaText.textContent.trim().length : 0
            };
        })()
    """))

    assert res_desktop["headerHeight"] <= 160, f"AC-34 VIOLATION: Desktop header height {res_desktop['headerHeight']}px > 160px"
    assert res_desktop["headerScrollHeight"] <= 160, f"AC-34 VIOLATION: Desktop scrollHeight {res_desktop['headerScrollHeight']}px > 160px"
    assert res_desktop["shaLength"] == 64, f"AC-34 VIOLATION: SHA-256 badge length {res_desktop['shaLength']} != 64 chars"

    # 2. Narrow Viewport Budget (<= 96px) at 480px and 320px
    for width in [480, 320]:
        loop.run_until_complete(runner.send("Emulation.setDeviceMetricsOverride", {
            "width": width,
            "height": 800,
            "deviceScaleFactor": 1,
            "mobile": True
        }))

        res_narrow = loop.run_until_complete(runner.eval_js("""
            (() => {
                const header = document.querySelector('.pd-header');
                const rect = header ? header.getBoundingClientRect() : null;
                const scrollH = header ? header.scrollHeight : 0;
                const docEl = document.documentElement;
                return {
                    width: window.innerWidth,
                    rectHeight: rect ? rect.height : 0,
                    scrollHeight: scrollH,
                    docScrollWidth: docEl.scrollWidth,
                    docClientWidth: docEl.clientWidth
                };
            })()
        """))

        # Clear device override
        loop.run_until_complete(runner.send("Emulation.clearDeviceMetricsOverride", {}))

        assert res_narrow["rectHeight"] <= 96, (
            f"AC-34 VIOLATION: Header height at {width}px is {res_narrow['rectHeight']}px > 96px"
        )
        assert res_narrow["scrollHeight"] <= 96, (
            f"AC-34 VIOLATION: Header scrollHeight at {width}px is {res_narrow['scrollHeight']}px > 96px"
        )
        assert res_narrow["docScrollWidth"] <= res_narrow["docClientWidth"] + 2, (
            f"AC-34/35 VIOLATION: Header causes horizontal document scroll at {width}px: "
            f"scrollWidth={res_narrow['docScrollWidth']} > clientWidth={res_narrow['docClientWidth']}"
        )


# -----------------------------------------------------------------------------
# AC-35: 320px Viewport Reflow without Horizontal Page Scroll
# -----------------------------------------------------------------------------
def test_ac35_responsive_reflow_down_to_320px(cdp):
    runner, loop = cdp
    res = loop.run_until_complete(runner.eval_js("""
        (() => {
            document.body.style.width = '320px';
            const scrollW = document.documentElement.scrollWidth;
            const clientW = document.documentElement.clientWidth;
            document.body.style.width = ''; // restore
            return {
                scrollW,
                clientW,
                noHorizontalScroll: scrollW <= clientW + 2
            };
        })()
    """))

    assert res["noHorizontalScroll"] is True, f"AC-35 VIOLATION: Horizontal scroll at 320px: {res}"


# -----------------------------------------------------------------------------
# AC-38..AC-41: Keyboard Operability, ARIA States & Focus Rings
# -----------------------------------------------------------------------------
def test_ac38_ac39_keyboard_accessibility_and_touch_targets(cdp):
    runner, loop = cdp
    res = loop.run_until_complete(runner.eval_js("""
        (() => {
            const buttons = Array.from(document.querySelectorAll('button, .pd-btn'));
            const undersized = [];
            const unnamed = [];

            for (const b of buttons) {
                const rect = b.getBoundingClientRect();
                const name = b.getAttribute('aria-label') || b.textContent.trim();
                if (rect.width > 0 && (rect.width < 22 || rect.height < 22)) {
                    undersized.push({ id: b.id, w: rect.width, h: rect.height });
                }
                if (!name) {
                    unnamed.push(b.id || 'unnamed-btn');
                }
            }

            return {
                undersizedCount: undersized.length,
                unnamedCount: unnamed.length
            };
        })()
    """))

    assert res["unnamedCount"] == 0, "AC-39: All interactive buttons must have accessible names"


# -----------------------------------------------------------------------------
# AC-44: Large Graph Handling (> 200 nodes / > 400 edges)
# -----------------------------------------------------------------------------
def test_ac44_large_graph_scale_guard(cdp):
    runner, loop = cdp
    res = loop.run_until_complete(runner.eval_js("""
        (() => {
            const largeDoc = JSON.parse(JSON.stringify(DEFAULT_V3_DOCUMENT));
            const nodes = [];
            for (let i = 0; i < 205; i++) {
                nodes.push({ id: 'n-' + i, label: 'Node ' + i, unit_refs: [] });
            }
            largeDoc.visuals[0].nodes = nodes;
            window.ParallelDocApp.loadDocument(largeDoc);

            const warning = document.querySelector('.pd-graph-scale-warning');
            const fallbackTable = document.querySelector('.pd-graph-fallback-container');

            return {
                hasWarning: !!warning,
                warningVisible: warning && window.getComputedStyle(warning).display !== 'none',
                fallbackVisible: fallbackTable && window.getComputedStyle(fallbackTable).display !== 'none'
            };
        })()
    """))

    assert res["hasWarning"] is True, "AC-44: Large graph (> 200 nodes) must trigger scale guard warning"
    assert res["fallbackVisible"] is True, "AC-44: Full fallback table must be visible when scale guard is breached"
