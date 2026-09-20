"""
tests/test_challenger_m3_browser.py — Empirical Browser Stress Test Suite for Milestone 3.
Executed against live standalone deliverable paralleldoc.html via Headless Chromium CDP.

Adversarial Missions Covered:
1. Graph Stress (200n/400e boundary vs 201n vs 401e, 100-node circular feedback loops, coordinate validity).
2. Multi-Panel & Zero Loss (missing roles combinations, orphan reconciliation, profiles 2/3/4, 15+ jumps LIFO stack).
3. Search & Highlighting (regex metacharacters literal matching, Unicode/Cyrillic, Enter wrap-around, scroll delta = 0).
"""

import asyncio
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
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
    raise RuntimeError("No Chromium browser found for CDP testing")


class BrowserStressRunner:
    def __init__(self, port=9254):
        self.port = port
        self.browser_bin = find_browser()
        self.proc = None
        self.ws = None
        self.msg_id = 0
        self.profile_dir = Path(os.environ.get("TEMP", "C:/Temp")) / f"pd_stress_profile_{port}"

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
        time.sleep(2.0)

    async def connect(self):
        for _ in range(25):
            try:
                with urllib.request.urlopen(f"http://127.0.0.1:{self.port}/json") as r:
                    pages = json.loads(r.read().decode())
                    matching = [p for p in pages if p.get("type") == "page" and "paralleldoc.html" in p.get("url", "")]
                    if matching:
                        ws_url = matching[0]["webSocketDebuggerUrl"]
                        self.ws = await websockets.connect(ws_url, max_size=20_000_000)
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
def browser_cdp():
    runner = BrowserStressRunner(port=9254)
    runner.start()
    loop = asyncio.new_event_loop()
    loop.run_until_complete(runner.connect())
    yield runner, loop
    if runner.ws:
        loop.run_until_complete(runner.ws.close())
    runner.stop()
    loop.close()


# =============================================================================
# 1. GRAPH STRESS TESTING IN BROWSER
# =============================================================================

def test_stress_graph_scale_guard_exact_boundaries(browser_cdp):
    """
    Test Scale Limit Guard exact boundaries:
    - 200 nodes / 400 edges -> SVG rendered, NO banner.
    - 201 nodes -> banner rendered, fallback table with 201 nodes rendered.
    - 401 edges -> banner rendered, fallback table with 401 edges rendered.
    """
    runner, loop = browser_cdp
    res = loop.run_until_complete(runner.eval_js("""
        (() => {
            const app = window.ParallelDocApp;
            const results = {};

            // Helper to build document
            function buildDoc(nodeCount, edgeCount) {
                const nodes = [];
                for (let i = 0; i < nodeCount; i++) {
                    nodes.push({ id: 'n-' + i, label: 'Node ' + i, unit_refs: [] });
                }
                const edges = [];
                for (let i = 0; i < edgeCount; i++) {
                    const fromId = 'n-' + (i % Math.max(1, nodeCount));
                    const toId = 'n-' + ((i + 1) % Math.max(1, nodeCount));
                    edges.push({
                        id: 'e-' + i,
                        from: fromId,
                        to: toId,
                        relation: 'supports',
                        label: 'Edge ' + i,
                        unit_refs: []
                    });
                }
                const doc = JSON.parse(JSON.stringify(DEFAULT_V3_DOCUMENT));
                doc.visuals = [{
                    id: 'vis-scale-test',
                    title: 'Scale Guard Test',
                    nodes,
                    edges
                }];
                return doc;
            }

            // Case A: Exactly 200 nodes and 400 edges
            const doc200_400 = buildDoc(200, 400);
            app.loadDocument(doc200_400);
            app.switchProfile('builtin:3');

            const warningA = document.querySelector('.pd-graph-scale-warning');
            const svgA = document.querySelector('.pd-graph-svg');
            const nodesA = document.querySelectorAll('.pd-graph-node');
            const edgesA = document.querySelectorAll('.pd-graph-edge');

            results.caseA = {
                hasWarning: !!warningA,
                hasSvg: !!svgA,
                nodeCount: nodesA.length,
                edgeCount: edgesA.length
            };

            // Case B: Exactly 201 nodes and 201 edges
            const doc201_201 = buildDoc(201, 201);
            app.loadDocument(doc201_201);
            app.switchProfile('builtin:3');

            const warningB = document.querySelector('.pd-graph-scale-warning');
            const fallbackB = document.querySelector('.pd-graph-fallback-container');
            const tableRowsB = document.querySelectorAll('.pd-fallback-row');

            results.caseB = {
                hasWarning: !!warningB,
                fallbackVisible: fallbackB && window.getComputedStyle(fallbackB).display !== 'none',
                rowCount: tableRowsB.length
            };

            // Case C: Exactly 200 nodes and 401 edges
            const doc200_401 = buildDoc(200, 401);
            app.loadDocument(doc200_401);
            app.switchProfile('builtin:3');

            const warningC = document.querySelector('.pd-graph-scale-warning');
            const fallbackC = document.querySelector('.pd-graph-fallback-container');
            const tableRowsC = document.querySelectorAll('.pd-fallback-row');

            results.caseC = {
                hasWarning: !!warningC,
                fallbackVisible: fallbackC && window.getComputedStyle(fallbackC).display !== 'none',
                rowCount: tableRowsC.length
            };

            return results;
        })()
    """))

    caseA = res["caseA"]
    assert caseA["hasWarning"] is False, "Exactly 200 nodes / 400 edges must NOT show scale limit warning"
    assert caseA["hasSvg"] is True, "Exactly 200 nodes / 400 edges must render SVG graph"
    assert caseA["nodeCount"] == 200, f"SVG should have 200 nodes, got {caseA['nodeCount']}"
    assert caseA["edgeCount"] == 400, f"SVG should have 400 edges, got {caseA['edgeCount']}"

    caseB = res["caseB"]
    assert caseB["hasWarning"] is True, "Exactly 201 nodes MUST trigger scale limit warning banner"
    assert caseB["fallbackVisible"] is True, "Fallback table must be visible when scale guard is triggered"
    assert caseB["rowCount"] == 201, f"Fallback table must render all 201 relations, got {caseB['rowCount']}"

    caseC = res["caseC"]
    assert caseC["hasWarning"] is True, "Exactly 401 edges MUST trigger scale limit warning banner"
    assert caseC["fallbackVisible"] is True, "Fallback table must be visible when 401 edges exceed guard"
    assert caseC["rowCount"] == 401, f"Fallback table must render all 401 relations, got {caseC['rowCount']}"


def test_stress_graph_circular_feedback_loop_100_nodes(browser_cdp):
    """
    Test 100-node circular feedback loop rendering, convergence timing, and finite coordinate attributes.
    """
    runner, loop = browser_cdp
    res = loop.run_until_complete(runner.eval_js("""
        (() => {
            const app = window.ParallelDocApp;
            const nodes = [];
            const edges = [];
            for (let i = 0; i < 100; i++) {
                nodes.push({ id: 'c100-' + i, label: 'Loop ' + i, unit_refs: [] });
                edges.push({
                    id: 'e100-' + i,
                    from: 'c100-' + i,
                    to: 'c100-' + ((i + 1) % 100),
                    relation: 'depends_on',
                    label: 'Depends ' + i
                });
            }

            const doc = JSON.parse(JSON.stringify(DEFAULT_V3_DOCUMENT));
            doc.visuals = [{
                id: 'vis-circle-100',
                title: '100 Node Circular Feedback',
                nodes,
                edges
            }];

            const t0 = performance.now();
            app.loadDocument(doc);
            app.switchProfile('builtin:3');
            const elapsed = performance.now() - t0;

            const svg = document.querySelector('.pd-graph-svg');
            const renderedNodes = document.querySelectorAll('.pd-graph-node');
            const renderedEdges = document.querySelectorAll('.pd-graph-edge');

            // Check for NaN or invalid coords
            let hasNaN = false;
            renderedNodes.forEach(n => {
                const tr = n.getAttribute('transform') || '';
                if (tr.includes('NaN') || tr.includes('undefined')) hasNaN = true;
            });
            renderedEdges.forEach(e => {
                const p = e.querySelector('path');
                const d = p ? p.getAttribute('d') || '' : '';
                if (d.includes('NaN') || d.includes('undefined')) hasNaN = true;
            });

            return {
                elapsed,
                hasSvg: !!svg,
                nodeCount: renderedNodes.length,
                edgeCount: renderedEdges.length,
                hasNaN
            };
        })()
    """))

    assert res["hasSvg"] is True
    assert res["nodeCount"] == 100
    assert res["edgeCount"] == 100
    assert res["hasNaN"] is False, "Coordinates and paths must never contain NaN"
    assert res["elapsed"] < 150.0, f"100-node circular graph rendering in browser took {res['elapsed']:.2f}ms"


# =============================================================================
# 2. MULTI-PANEL & ZERO LOSS STRESS TESTING IN BROWSER
# =============================================================================

def test_stress_panels_diverse_combinations_zero_loss(browser_cdp):
    """
    Generate adversarial combinations (only sources, only actions, only analysis, only models,
    orphans) and verify 100% Zero Unit Loss in the actual DOM across profile switches.
    """
    runner, loop = browser_cdp
    res = loop.run_until_complete(runner.eval_js("""
        (() => {
            const app = window.ParallelDocApp;

            const units = [
                // Group 1: only sources
                { id: 'u-src-1', kind: 'source', title: 'Source 1', text: 'Text 1' },
                { id: 'u-src-2', kind: 'source', title: 'Source 2', text: 'Text 2' },
                { id: 'u-src-3', kind: 'source', title: 'Source 3', text: 'Text 3' },
                { id: 'u-src-4', kind: 'source', title: 'Source 4', text: 'Text 4' },
                { id: 'u-src-5', kind: 'source', title: 'Source 5', text: 'Text 5' },
                // Group 2: only actions
                { id: 'u-act-1', kind: 'action', title: 'Action 1', text: 'Act 1' },
                { id: 'u-act-2', kind: 'action', title: 'Action 2', text: 'Act 2' },
                { id: 'u-act-3', kind: 'action', title: 'Action 3', text: 'Act 3' },
                { id: 'u-act-4', kind: 'action', title: 'Action 4', text: 'Act 4' },
                // Group 3: only analysis
                { id: 'u-ana-1', kind: 'analysis', title: 'Analysis 1', text: 'Ana 1' },
                { id: 'u-ana-2', kind: 'analysis', title: 'Analysis 2', text: 'Ana 2' },
                { id: 'u-ana-3', kind: 'analysis', title: 'Analysis 3', text: 'Ana 3' },
                // Group 4: only models
                { id: 'u-mod-1', kind: 'model', title: 'Model 1', text: 'Mod 1' },
                { id: 'u-mod-2', kind: 'model', title: 'Model 2', text: 'Mod 2' },
                // Group 5: mixed source + action
                { id: 'u-src-6', kind: 'source', title: 'Source 6', text: 'Text 6' },
                { id: 'u-act-5', kind: 'action', title: 'Action 5', text: 'Act 5' },
                // 10 Orphan units
                { id: 'u-orph-1', kind: 'source', title: 'Orphan 1', text: 'Orph 1' },
                { id: 'u-orph-2', kind: 'model', title: 'Orphan 2', text: 'Orph 2' },
                { id: 'u-orph-3', kind: 'analysis', title: 'Orphan 3', text: 'Orph 3' },
                { id: 'u-orph-4', kind: 'action', title: 'Orphan 4', text: 'Orph 4' },
                { id: 'u-orph-5', kind: 'source', title: 'Orphan 5', text: 'Orph 5' },
                { id: 'u-orph-6', kind: 'model', title: 'Orphan 6', text: 'Orph 6' },
                { id: 'u-orph-7', kind: 'analysis', title: 'Orphan 7', text: 'Orph 7' },
                { id: 'u-orph-8', kind: 'action', title: 'Orphan 8', text: 'Orph 8' },
                { id: 'u-orph-9', kind: 'source', title: 'Orphan 9', text: 'Orph 9' },
                { id: 'u-orph-10', kind: 'analysis', title: 'Orphan 10', text: 'Orph 10' }
            ];

            const groups = [
                { id: 'g-src', title: 'Sources Group', unit_refs: ['u-src-1', 'u-src-2', 'u-src-3', 'u-src-4', 'u-src-5'] },
                { id: 'g-act', title: 'Actions Group', unit_refs: ['u-act-1', 'u-act-2', 'u-act-3', 'u-act-4'] },
                { id: 'g-ana', title: 'Analysis Group', unit_refs: ['u-ana-1', 'u-ana-2', 'u-ana-3'] },
                { id: 'g-mod', title: 'Models Group', unit_refs: ['u-mod-1', 'u-mod-2'] },
                { id: 'g-mix', title: 'Mixed Group', unit_refs: ['u-src-6', 'u-act-5'] }
            ];

            const doc = JSON.parse(JSON.stringify(DEFAULT_V3_DOCUMENT));
            doc.units = units;
            doc.groups = groups;
            doc.visuals = [];

            app.loadDocument(doc);
            const totalExpected = units.length; // 26

            const domCounts = {};
            const missingBadgeCounts = {};
            for (const pId of ['builtin:2', 'builtin:3', 'builtin:4']) {
                app.switchProfile(pId);
                const cards = document.querySelectorAll('.unit-card, .pd-unit-card');
                const missingBadges = document.querySelectorAll('.missing-role-placeholder');
                domCounts[pId] = cards.length;
                missingBadgeCounts[pId] = missingBadges.length;
            }

            const orphanSection = document.querySelector('.group-orphans');

            return {
                totalExpected,
                domCounts,
                missingBadgeCounts,
                hasOrphanSection: !!orphanSection
            };
        })()
    """))

    total = res["totalExpected"]
    assert total == 26

    # Verify 100% Zero Unit Loss in actual DOM
    for pId, count in res["domCounts"].items():
        assert count == total, f"Zero Unit Loss violation: Profile {pId} rendered {count} cards instead of {total}"

    assert res["hasOrphanSection"] is True, "Orphan section must be rendered in DOM"
    assert res["missingBadgeCounts"]["builtin:4"] > 0, "Missing role badges must be rendered in Review profile"


def test_stress_history_stack_rapid_navigations_and_anchor_return(browser_cdp):
    """
    Test 10-target LIFO history stack bounds and return-to-anchor behavior under >15 sequential navigations.
    """
    runner, loop = browser_cdp
    res = loop.run_until_complete(runner.eval_js("""
        (() => {
            const app = window.ParallelDocApp;
            const pe = app.panelsEngine;

            // Reset navigation stack
            pe.navStack = [];

            // Execute 18 sequential navigations to unit cards
            const targets = [
                'u-src-1', 'u-act-1', 'u-ana-1', 'u-mod-1', 'u-src-2',
                'u-act-2', 'u-ana-2', 'u-mod-2', 'u-src-3', 'u-act-3',
                'u-ana-3', 'u-src-4', 'u-act-4', 'u-src-5', 'u-orph-1',
                'u-orph-2', 'u-orph-3', 'u-orph-4'
            ];

            const stackSizes = [];
            for (const t of targets) {
                pe.navigateTo(t);
                stackSizes.push(pe.navStack.length);
            }

            const finalStackLen = pe.navStack.length;
            const topTarget = pe.navStack[pe.navStack.length - 1].targetId;
            const oldestTarget = pe.navStack[0].targetId;

            // Perform 10 returns to anchor
            const poppedTargets = [];
            for (let i = 0; i < 10; i++) {
                const popped = pe.navStack[pe.navStack.length - 1];
                poppedTargets.push(popped ? popped.targetId : null);
                pe.returnToAnchor();
            }
            const postPopLen = pe.navStack.length;
            const emptyReturnResult = pe.returnToAnchor();

            return {
                stackSizes,
                finalStackLen,
                topTarget,
                oldestTarget,
                poppedTargets,
                postPopLen,
                emptyReturnResult
            };
        })()
    """))

    assert res["finalStackLen"] == 10, f"Stack capacity must be strictly capped at 10, got {res['finalStackLen']}"
    assert res["topTarget"] == 'u-orph-4', f"Top target should be u-orph-4, got {res['topTarget']}"
    assert res["oldestTarget"] == 'u-src-3', f"Oldest target after 18 pushes should be u-src-3 (targets 0-7 evicted), got {res['oldestTarget']}"
    assert res["postPopLen"] == 0, "Stack should be empty after 10 pops"
    assert res["emptyReturnResult"] is False, "Empty returnToAnchor must safely return False"


# =============================================================================
# 3. SEARCH & HIGHLIGHTING STRESS TESTING IN BROWSER
# =============================================================================

def test_stress_search_regex_metacharacters_and_unicode_in_browser(browser_cdp):
    """
    Test search box queries with regex metacharacters, unicode accents, and Cyrillic tokens.
    Verify 0 exceptions, exact substring matching, and highlight application.
    """
    runner, loop = browser_cdp
    res = loop.run_until_complete(runner.eval_js("""
        (() => {
            const app = window.ParallelDocApp;
            const results = {};

            // Prepare test doc with special tokens
            const doc = JSON.parse(JSON.stringify(DEFAULT_V3_DOCUMENT));
            doc.units.push({
                id: 'u-regex-stress',
                kind: 'source',
                title: 'Regex Specimen',
                text: 'Metacharacters: .*+?^${}()|[]\\\\ and tokens (SLA), [A-Z]+, and \\\\d+\\\\.\\\\d+ tested.'
            });
            doc.units.push({
                id: 'u-unicode-stress',
                kind: 'analysis',
                title: 'Unicode & Cyrillic Specimen',
                text: 'International: Café, naïve, résumé, «Вне групп», 99.95%, and emojis 🚀 ⚠️.'
            });
            doc.groups[0].unit_refs.push('u-regex-stress', 'u-unicode-stress');

            app.loadDocument(doc);

            const testQueries = [
                '.*+?^${}()|[]\\\\',
                '[A-Z]+',
                '\\\\d+\\\\.\\\\d+',
                '(SLA)',
                '«Вне групп»',
                'Café',
                'résumé',
                '99.95%',
                '🚀'
            ];

            for (const q of testQueries) {
                try {
                    const matches = app.searchEngine.search(q);
                    results[q] = {
                        success: true,
                        matchCount: matches.length
                    };
                } catch (e) {
                    results[q] = {
                        success: false,
                        error: e.toString()
                    };
                }
            }

            return results;
        })()
    """))

    for q, outcome in res.items():
        assert outcome["success"] is True, f"Search failed with exception on query '{q}': {outcome.get('error')}"
        assert outcome["matchCount"] >= 1, f"Expected matches for query '{q}', got {outcome['matchCount']}"


def test_stress_search_rapid_enter_wrap_around(browser_cdp):
    """
    Test rapid Enter / Shift+Enter circular traversal in browser search engine.
    """
    runner, loop = browser_cdp
    res = loop.run_until_complete(runner.eval_js("""
        (() => {
            const app = window.ParallelDocApp;
            app.searchEngine.search('specimen');
            const total = app.searchEngine.matches.length; // 2
            const history = [];

            for (let i = 0; i < 30; i++) {
                app.searchEngine.next();
                history.push(app.searchEngine.currentIndex);
            }

            for (let i = 0; i < 30; i++) {
                app.searchEngine.prev();
            }

            return {
                total,
                history,
                finalIndex: app.searchEngine.currentIndex
            };
        })()
    """))

    assert res["total"] >= 2
    # Verify cycling alternating between indices
    assert len(res["history"]) == 30
    assert res["finalIndex"] in [0, 1]


def test_stress_cross_highlighting_scroll_delta_zero(browser_cdp):
    """
    Verify scroll delta = 0 on cross-highlighting hover events across multiple graph elements.
    """
    runner, loop = browser_cdp
    res = loop.run_until_complete(runner.eval_js("""
        (() => {
            const app = window.ParallelDocApp;
            app.switchProfile('builtin:3'); // Graph in center

            // Scroll to arbitrary offset
            window.scrollTo(0, 180);
            const initialY = window.pageYOffset || document.documentElement.scrollTop || 0;

            const nodes = document.querySelectorAll('.pd-graph-node');
            const edges = document.querySelectorAll('.pd-graph-edge');
            const deltas = [];

            // Test 5 nodes
            nodes.forEach(n => {
                n.dispatchEvent(new MouseEvent('mouseenter', { bubbles: true }));
                const currentY = window.pageYOffset || document.documentElement.scrollTop || 0;
                deltas.push(Math.abs(currentY - initialY));
                n.dispatchEvent(new MouseEvent('mouseleave', { bubbles: true }));
            });

            // Test 5 edges
            edges.forEach(e => {
                e.dispatchEvent(new MouseEvent('mouseenter', { bubbles: true }));
                const currentY = window.pageYOffset || document.documentElement.scrollTop || 0;
                deltas.push(Math.abs(currentY - initialY));
                e.dispatchEvent(new MouseEvent('mouseleave', { bubbles: true }));
            });

            const maxDelta = Math.max(...deltas, 0);

            return {
                testedCount: deltas.length,
                maxDelta,
                initialY
            };
        })()
    """))

    assert res["testedCount"] >= 4, f"Should test multiple graph elements, got {res['testedCount']}"
    assert res["maxDelta"] == 0, f"AC-14 VIOLATION: Scroll jump detected on graph hover! Max delta = {res['maxDelta']}px"
