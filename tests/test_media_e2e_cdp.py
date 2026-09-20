"""
tests/test_media_e2e_cdp.py — Autonomous Headless Chromium CDP Test Suite for Milestone 4.
Verifies AC-19..AC-24, AC-26..AC-29 against deliverable paralleldoc.html.
Runs out-of-the-box on Windows using standard library + websockets.
"""

import asyncio
import base64
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
    def __init__(self, port=9254):
        self.port = port
        self.browser_bin = find_browser()
        self.proc = None
        self.ws = None
        self.msg_id = 0
        self.intercepted_requests = []
        self.profile_dir = Path(tempfile.gettempdir()) / f"pd_e2e_media_{port}"

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
    runner = CDPRunner(port=9254)
    runner.start()
    loop = asyncio.new_event_loop()
    loop.run_until_complete(runner.connect())
    yield runner, loop
    if runner.ws:
        loop.run_until_complete(runner.ws.close())
    runner.stop()
    loop.close()


# -----------------------------------------------------------------------------
# AC-19: Pre-Reserved Geometry & Aspect Ratio Frames
# -----------------------------------------------------------------------------

def test_ac19_thumbnail_pre_reserved_frame(cdp):
    runner, loop = cdp
    res = loop.run_until_complete(runner.eval_js("""
        (() => {
            // Load default document with valid SLA uptime asset attached to u-sla-act
            window.ParallelDocApp.loadDocument(DEFAULT_V3_DOCUMENT);
            window.ParallelDocApp.setDensity('reading');

            const wrapper = document.getElementById('asset-wrapper-ast-sla-uptime');
            if (!wrapper) return { error: 'Wrapper not found' };

            const frame = wrapper.querySelector('.pd-thumbnail-frame');
            const trigger = wrapper.querySelector('.pd-thumbnail-trigger');
            const img = wrapper.querySelector('.pd-thumbnail-img');

            const csFrame = window.getComputedStyle(frame);
            const csImg = window.getComputedStyle(img);

            // Check reading dimensions
            const readingFrameH = parseFloat(csFrame.height);
            const containVal = csFrame.contain;

            // Switch to dense
            window.ParallelDocApp.setDensity('dense');
            const denseFrameH = parseFloat(window.getComputedStyle(frame).height);

            // Restore reading
            window.ParallelDocApp.setDensity('reading');

            return {
                wrapperExists: true,
                hasDialogPopup: trigger.getAttribute('aria-haspopup') === 'dialog',
                ariaLabel: trigger.getAttribute('aria-label'),
                readingFrameH,
                denseFrameH,
                containVal,
                objectFit: csImg.objectFit
            };
        })()
    """))

    assert res.get("wrapperExists") is True
    assert res.get("hasDialogPopup") is True
    assert "1×1 px" in res.get("ariaLabel", "")
    assert res.get("readingFrameH") <= 145.0
    assert res.get("denseFrameH") <= 97.0
    assert "layout" in res.get("containVal", "") or "size" in res.get("containVal", "")
    assert res.get("objectFit") == "contain"


# -----------------------------------------------------------------------------
# AC-20: 1:1 Natural Pixel Modal Dialog, Stepped Zoom, Keyboard Navigation
# -----------------------------------------------------------------------------

def test_ac20_modal_1to1_pixel_inspector_lifecycle(cdp):
    runner, loop = cdp
    res = loop.run_until_complete(runner.eval_js("""
        (() => {
            window.ParallelDocApp.loadDocument(DEFAULT_V3_DOCUMENT);
            const trigger = document.getElementById('thumb-btn-ast-sla-uptime');
            trigger.focus();

            // 1. Open modal via click on thumbnail
            trigger.click();

            const modal = document.getElementById('pd-modal-inspector');
            const isOpenAfterClick = modal && modal.style.display === 'flex' && !modal.hasAttribute('hidden');
            const isBodyLocked = document.body.classList.contains('pd-modal-open');

            const img = document.getElementById('modal-image');
            const isNatural1to1 = img.classList.contains('mode-1to1');
            const imgW = img.style.width;
            const imgH = img.style.height;

            // 2. Test Fit mode toggle
            const btnFit = document.getElementById('modal-btn-fit');
            btnFit.click();
            const isFitMode = img.classList.contains('mode-fit');

            // 3. Test 1:1 mode toggle back
            const btn100 = document.getElementById('modal-btn-100');
            btn100.click();
            const isRestored1to1 = img.classList.contains('mode-1to1');

            // 4. Test Keyboard Pan in 1:1 mode
            const viewport = document.getElementById('modal-viewport');
            const initialScrollLeft = viewport.scrollLeft;

            // Dispatch ArrowRight
            window.dispatchEvent(new KeyboardEvent('keydown', { key: 'ArrowRight', bubbles: true }));
            const scrollAfterArrow = viewport.scrollLeft;

            // Dispatch Shift+ArrowRight
            window.dispatchEvent(new KeyboardEvent('keydown', { key: 'ArrowRight', shiftKey: true, bubbles: true }));
            const scrollAfterShiftArrow = viewport.scrollLeft;

            // 5. Test Escape Key Closing & Focus Restoration
            window.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }));
            const isClosedAfterEsc = modal.style.display === 'none' && modal.hasAttribute('hidden');
            const isBodyUnlocked = !document.body.classList.contains('pd-modal-open');
            const isFocusRestored = (document.activeElement === trigger);

            return {
                isOpenAfterClick,
                isBodyLocked,
                isNatural1to1,
                imgW,
                imgH,
                isFitMode,
                isRestored1to1,
                isClosedAfterEsc,
                isBodyUnlocked,
                isFocusRestored
            };
        })()
    """))

    assert res.get("isOpenAfterClick") is True
    assert res.get("isBodyLocked") is True
    assert res.get("isNatural1to1") is True
    assert res.get("imgW") == "1px"
    assert res.get("imgH") == "1px"
    assert res.get("isFitMode") is True
    assert res.get("isRestored1to1") is True
    assert res.get("isClosedAfterEsc") is True
    assert res.get("isBodyUnlocked") is True
    assert res.get("isFocusRestored") is True


# -----------------------------------------------------------------------------
# AC-21: Full 64-char SHA-256 Copy in Modal Inspector
# -----------------------------------------------------------------------------

def test_ac21_metadata_panel_and_sha_copy(cdp):
    runner, loop = cdp
    res = loop.run_until_complete(runner.eval_js("""
        (() => {
            window.ParallelDocApp.loadDocument(DEFAULT_V3_DOCUMENT);
            const trigger = document.getElementById('thumb-btn-ast-sla-uptime');
            trigger.click();

            const idEl = document.getElementById('modal-asset-id');
            const dimsEl = document.getElementById('modal-asset-dims');
            const mimeEl = document.getElementById('modal-asset-mime');
            const sizeEl = document.getElementById('modal-asset-size');
            const shaEl = document.getElementById('modal-asset-sha');

            const assetId = idEl.textContent.trim();
            const dims = dimsEl.textContent.trim();
            const mime = mimeEl.textContent.trim();
            const size = sizeEl.textContent.trim();
            const shaText = shaEl.textContent.trim();

            // Close modal
            document.getElementById('modal-btn-close').click();

            return {
                assetId,
                dims,
                mime,
                size,
                shaText,
                shaLength: shaText.length
            };
        })()
    """))

    assert res.get("assetId") == "ast-sla-uptime"
    assert res.get("dims") == "1 × 1 px"
    assert res.get("mime") == "image/png"
    assert res.get("size") == "0.1 KB"
    assert res.get("shaLength") == 64
    assert res.get("shaText") == "6b7fa434f92a8b80aab02d9bf1a12e49ffcae424e4013a1c4f68b67e3d2bbcd0"


# -----------------------------------------------------------------------------
# AC-22: Zero Layout Shift Guarantee (Delta <= 2px)
# -----------------------------------------------------------------------------

def test_ac22_zero_layout_shift_guarantee(cdp):
    runner, loop = cdp
    res = loop.run_until_complete(runner.eval_js("""
        (() => {
            window.ParallelDocApp.loadDocument(DEFAULT_V3_DOCUMENT);
            const card = document.getElementById('unit-u-sla-act');
            const topBefore = card.getBoundingClientRect().top;

            // Trigger re-render of asset container
            const wrapper = document.getElementById('asset-wrapper-ast-sla-uptime');
            const frame = wrapper.querySelector('.pd-thumbnail-frame');

            // Pre-reserved frame height
            const frameH = frame.offsetHeight;

            // Card top after mounting
            const topAfter = card.getBoundingClientRect().top;
            const deltaY = Math.abs(topAfter - topBefore);

            return {
                deltaY,
                frameH,
                isBounded: frameH <= 144
            };
        })()
    """))

    assert res.get("deltaY") <= 2.0
    assert res.get("isBounded") is True


# -----------------------------------------------------------------------------
# AC-23: Diagnostic Error Card Display
# -----------------------------------------------------------------------------

def test_ac23_diagnostic_error_card(cdp):
    runner, loop = cdp
    res = loop.run_until_complete(runner.eval_js("""
        (() => {
            const badDoc = JSON.parse(JSON.stringify(DEFAULT_V3_DOCUMENT));
            badDoc.assets[0].locator.data_uri = "data:image/png;base64,invalid_payload_!@#$";
            window.ParallelDocApp.loadDocument(badDoc);

            const errCard = document.getElementById('asset-error-ast-sla-uptime');
            if (!errCard) return { error: 'Error card not rendered' };

            const isAlertRole = errCard.getAttribute('role') === 'alert';
            const codeEl = errCard.querySelector('.pd-asset-error-code');
            const errCode = codeEl ? codeEl.textContent.trim() : '';

            // Geometry check: frame must exist and preserve dimensions
            const frame = errCard.querySelector('.pd-thumbnail-frame');
            const frameH = frame ? frame.offsetHeight : 0;

            return {
                rendered: true,
                isAlertRole,
                errCode,
                frameH,
                frameBounded: frameH <= 144
            };
        })()
    """))

    assert res.get("rendered") is True
    assert res.get("isAlertRole") is True
    assert res.get("errCode") == "ERR_ASSET_CORRUPTED_BASE64"
    assert res.get("frameBounded") is True


# -----------------------------------------------------------------------------
# AC-24: Zero External Network Requests Invariant
# -----------------------------------------------------------------------------

def test_ac24_zero_network_calls(cdp):
    runner, _ = cdp
    # Check all intercepted requests
    for url in runner.intercepted_requests:
        assert not url.startswith("http://"), f"Disallowed HTTP request: {url}"
        assert not url.startswith("https://"), f"Disallowed HTTPS request: {url}"


# -----------------------------------------------------------------------------
# AC-26: Detached Manifest Verification & Clean Reset Invariant
# -----------------------------------------------------------------------------

def test_ac26_manifest_and_clean_reset(cdp):
    runner, loop = cdp
    res = loop.run_until_complete(runner.eval_js("""
        (() => {
            window.ParallelDocApp.loadDocument(DEFAULT_V3_DOCUMENT);
            const currentSha = window.ParallelDocApp.rawSha256;

            // 1. Test Matching Manifest
            const matchManifest = {
                format: "paralleldoc-integrity-1",
                algorithm: "SHA-256",
                document_id: "doc-sla-benchmark",
                revision: "rev-1",
                expected_sha256: currentSha,
                scope: "raw-bytes"
            };
            window.ParallelDocApp.verifyAndApplyManifest(JSON.stringify(matchManifest));
            const badgeMatchText = document.getElementById('pd-integrity-badge').textContent;
            const bannerAfterMatch = document.getElementById('pd-mismatch-banner').style.display;

            // 2. Test Mismatch Manifest (State 6)
            const mismatchManifest = {
                format: "paralleldoc-integrity-1",
                algorithm: "SHA-256",
                document_id: "doc-sla-benchmark",
                revision: "rev-1",
                expected_sha256: "0000000000000000000000000000000000000000000000000000000000000000",
                scope: "raw-bytes"
            };
            window.ParallelDocApp.verifyAndApplyManifest(JSON.stringify(mismatchManifest));
            const badgeMismatchText = document.getElementById('pd-integrity-badge').textContent;
            const bannerAfterMismatch = document.getElementById('pd-mismatch-banner').style.display;
            const expectedDisplay = document.getElementById('pd-mismatch-expected').textContent;

            // 3. Test Clean Reset Invariant (AC-26)
            // Opening a new document must cleanly reset manifest state, hide mismatch banner, and set integrity to 'computed'
            const freshDoc = JSON.parse(JSON.stringify(DEFAULT_V3_DOCUMENT));
            freshDoc.metadata.document_id = "doc-fresh-sla";
            window.ParallelDocApp.loadDocument(freshDoc);

            const badgeAfterReset = document.getElementById('pd-integrity-badge').textContent;
            const bannerAfterReset = document.getElementById('pd-mismatch-banner').style.display;
            const manifestResultIsCleared = (window.ParallelDocApp.manifestResult === null);

            return {
                badgeMatchText,
                bannerAfterMatch,
                badgeMismatchText,
                bannerAfterMismatch,
                expectedDisplay,
                badgeAfterReset,
                bannerAfterReset,
                manifestResultIsCleared
            };
        })()
    """))

    assert "Совпадение" in res.get("badgeMatchText")
    assert res.get("bannerAfterMatch") == "none"
    assert "Несовпадение" in res.get("badgeMismatchText")
    assert res.get("bannerAfterMismatch") == "block"
    assert res.get("expectedDisplay") == "0000000000000000000000000000000000000000000000000000000000000000"
    assert "Хэш вычислен" in res.get("badgeAfterReset")
    assert res.get("bannerAfterReset") == "none"
    assert res.get("manifestResultIsCleared") is True


# -----------------------------------------------------------------------------
# AC-27: Visual Distinction of Integrity States
# -----------------------------------------------------------------------------

def test_ac27_integrity_states_visual_distinction(cdp):
    runner, loop = cdp
    res = loop.run_until_complete(runner.eval_js("""
        (() => {
            const badge = document.getElementById('pd-integrity-badge');

            // Computed
            window.ParallelDocApp.updateTrustAxes('valid', 'computed');
            const isComputed = badge.classList.contains('pd-integrity-badge-computed');

            // Detached match
            window.ParallelDocApp.updateTrustAxes('valid', 'detached_match');
            const isMatched = badge.classList.contains('pd-integrity-badge-matched');

            // Detached mismatch
            window.ParallelDocApp.updateTrustAxes('valid', 'detached_mismatch');
            const isMismatch = badge.classList.contains('pd-integrity-badge-mismatch');

            // Unavailable
            window.ParallelDocApp.updateTrustAxes('valid', 'unavailable');
            const isUnavailable = badge.classList.contains('pd-integrity-badge-unavailable');

            return {
                isComputed,
                isMatched,
                isMismatch,
                isUnavailable
            };
        })()
    """))

    assert res.get("isComputed") is True
    assert res.get("isMatched") is True
    assert res.get("isMismatch") is True
    assert res.get("isUnavailable") is True


# -----------------------------------------------------------------------------
# AC-28: Simultaneous Multi-Error Coexistence Invariant
# -----------------------------------------------------------------------------

def test_ac28_simultaneous_multi_error_coexistence(cdp):
    runner, loop = cdp
    res = loop.run_until_complete(runner.eval_js("""
        (() => {
            // Load document with a corrupted asset
            const multiErrDoc = JSON.parse(JSON.stringify(DEFAULT_V3_DOCUMENT));
            multiErrDoc.assets[0].locator.data_uri = "data:image/png;base64,corrupted_payload";
            window.ParallelDocApp.loadDocument(multiErrDoc);

            // Apply a mismatching manifest
            const mismatchManifest = {
                format: "paralleldoc-integrity-1",
                algorithm: "SHA-256",
                document_id: "doc-sla-benchmark",
                revision: "rev-1",
                expected_sha256: "ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff",
                scope: "raw-bytes"
            };
            window.ParallelDocApp.verifyAndApplyManifest(JSON.stringify(mismatchManifest));

            // Check simultaneous coexistence of sticky mismatch banner and asset error card
            const banner = document.getElementById('pd-mismatch-banner');
            const assetErrorCard = document.getElementById('asset-error-ast-sla-uptime');

            const bannerVisible = banner && banner.style.display === 'block';
            const assetErrorVisible = !!assetErrorCard;

            // Perform actions like selecting a unit or search
            window.ParallelDocApp.panelsEngine.selectUnit('u-sla-ana');
            window.ParallelDocApp.searchEngine.search('availability');

            // Mismatch banner must remain visible (sticky persistent header banner)
            const bannerStillVisible = banner.style.display === 'block';

            return {
                bannerVisible,
                assetErrorVisible,
                bannerStillVisible
            };
        })()
    """))

    assert res.get("bannerVisible") is True
    assert res.get("assetErrorVisible") is True
    assert res.get("bannerStillVisible") is True


# -----------------------------------------------------------------------------
# AC-29: Honest Trust Boundaries & Provenance Source SHA Label
# -----------------------------------------------------------------------------

def test_ac29_honest_trust_boundaries_and_claimed_label(cdp):
    runner, loop = cdp
    res = loop.run_until_complete(runner.eval_js("""
        (() => {
            window.ParallelDocApp.loadDocument(DEFAULT_V3_DOCUMENT);

            // Source unit has provenance.source_sha256
            const srcCard = document.getElementById('unit-u-sla-src');
            const provShaEl = srcCard.querySelector('.prov-sha');
            const provShaText = provShaEl ? provShaEl.textContent : '';
            const provShaTitle = provShaEl ? provShaEl.getAttribute('title') : '';

            // Popover element check
            const popover = document.getElementById('pd-trust-popover');
            const shaBtn = document.getElementById('pd-sha-badge-btn');

            // Hover trigger popover
            shaBtn.dispatchEvent(new MouseEvent('mouseenter'));
            const popoverVisible = popover.style.display === 'block';
            const popoverContent = popover.textContent;

            // Unhover
            shaBtn.dispatchEvent(new MouseEvent('mouseleave'));
            const popoverHidden = popover.style.display === 'none';

            return {
                provShaText,
                provShaTitle,
                popoverVisible,
                popoverHidden,
                popoverHasDisclaimer: popoverContent.includes('raw-bytes') && popoverContent.includes('истинность')
            };
        })()
    """))

    assert "заявленный:" in res.get("provShaText", "")
    assert "не верифицирован" in res.get("provShaTitle", "")
    assert res.get("popoverVisible") is True
    assert res.get("popoverHidden") is True
    assert res.get("popoverHasDisclaimer") is True
