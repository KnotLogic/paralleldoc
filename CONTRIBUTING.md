# Contributing to ParallelDoc

Thank you for your interest in contributing to **ParallelDoc**!

ParallelDoc is designed as a minimalist, zero-dependency, ultra-reliable 3-pane document inspector for cross-lingual and comparative analysis.

---

## Core Architectural Principles

1. **Zero External Runtime Dependencies:**
   - The primary application (`paralleldoc.html`) is a self-contained Single-File HTML5/CSS/JavaScript application.
   - Do NOT introduce npm packages, build tools, webpack/vite bundlers, or remote CDN dependencies (fonts, icons, scripts) into `paralleldoc.html`.
   - The viewer must work offline directly via `file:///` protocol.

2. **CORS & Cryptographic Integrity:**
   - Web Crypto API (`crypto.subtle.digest("SHA-256", ...)`) is used to compute a strict 64-character SHA-256 hash of the exact input string.
   - Always normalize line endings (`\r\n` -> `\n`) when processing JSON across different operating systems to guarantee cross-platform cryptographic parity.
   - To support local execution under `file:///` without local HTTP servers, the viewer supports dual loading: `fetch("active_document.json")` with fallback to `window.ACTIVE_PARALLELDOC_RAW` inside `active_document.js`.

3. **Cognitive Ergonomics (UI Standard):**
   - **Font:** Georgia / Cambria serif typography with ClearType subpixel rendering.
   - **Base Size:** 16.5px with 1.78 line-height.
   - **Color Scheme:** Soft light reading theme (`#fcfcfd` background, `#ffffff` cards, `#1f2937` graphite text).
   - **Badges:** Prominent row callout badges (`#1`, `#2`) for precise operator referencing.

---

## Extending & Forking ParallelDoc

ParallelDoc is built to be easily forkable for specialized domains.

### Fork Idea: ParallelDoc Visual (Diagrams & Mermaid in Column 3)
If you are building a fork that visualizes architectures, data flows, or business logic in Column 3:
1. Embed a self-contained JS library (e.g. bundled SVG/canvas renderer or Mermaid bundle) inside the HTML file.
2. In the `parseMarkdown` routine, detect fenced code blocks with language `mermaid` or `canvas`.
3. Render the interactive diagram inline within Column 3 while keeping Columns 1 and 2 synchronized.

---

## Running the Automated Test Suite

ParallelDoc includes an end-to-end headless Chrome DevTools Protocol (CDP) test suite:

```bash
# 1. Validate sample document schema and SHA-256 calculation
python validate_document.py sample_document.json

# 2. Run browser automation CDP tests (validates DOM rendering, hash display, highlighter, search)
python test_cockpit_cdp.py
```

Prerequisites for running tests:
- Python 3.9+
- `websockets` library (`pip install websockets`)
- Any Chromium-based browser (Brave, Microsoft Edge, or Google Chrome)

---

## Submission Guidelines

- Ensure `python validate_document.py sample_document.json` exits with code 0.
- Ensure `python test_cockpit_cdp.py` passes all 12 test assertions.
- Verify that no private data, hardcoded personal usernames, or proprietary credentials exist in your diff.
- Keep commits clear and descriptive following Conventional Commits format (`feat:`, `fix:`, `docs:`, `refactor:`).
