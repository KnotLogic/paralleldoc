# 📑 ParallelDoc

> **Zero-Dependency 3-Pane Comparative Document Inspector for LLM Workflows & Human-in-the-Loop Review**

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Zero Dependencies](https://img.shields.io/badge/Dependencies-Zero-success.svg)]()
[![Single File HTML5](https://img.shields.io/badge/Architecture-Single_HTML5_File-orange.svg)]()
[![Platform: Windows | Linux | macOS](https://img.shields.io/badge/Platform-Windows%20%7C%20Linux%20%7C%20macOS-lightgrey.svg)]()

---

## 🎯 Overview

When reviewing complex multilingual contracts, legal statutes, technical specifications, or procurement tenders, standard chat interfaces cause severe cognitive fatigue and context drift.

**ParallelDoc** solves this by providing a dedicated, distraction-free desktop reading environment structured into three synchronized parallel panes:
1. **Original Clause** (e.g. source language or legacy contract clause)
2. **Plain Translation / Revision** (e.g. translated text or revised clause)
3. **Engineering & Risk Assessment** (e.g. legal risks, SLA compliance, margin calculations)

---

## ✨ Key Features

- 🔒 **Anti-Drift Cryptographic Header:**  
  A prominent, full 64-character SHA-256 hash badge is permanently rendered on the top left. When operators take screenshots of any clause, the hash is captured in the frame, allowing AI models in chat threads to cryptographically verify the document version. Click the badge to copy the full hash to your clipboard.

- 📖 **Cognitive Ergonomics & ClearType Typography:**  
  Built strictly according to book-reading ergonomic standards: **Georgia serif typography at 16.5px**, `1.78` line-height, and subpixel ClearType anti-aliasing on a soft off-white canvas (`#fcfcfd`).

- 🖍️ **Moon+ Style In-Memory Highlighter:**  
  Select any text across columns to instantly apply yellow highlights (`#fef08a`) or red underline accents (`#ef4444`). Click directly on any highlighted span to unwrap it. Annotations live in DOM memory for clean screenshot preparation without altering disk files.

- ⚡ **Zero External Runtime Dependencies:**  
  `paralleldoc.html` is a 100% self-contained file. No Node.js, no npm, no bundlers, and no remote CDN requests. It runs completely offline directly from `file:///`.

- 🖥️ **Silent Desktop App Launcher (Windows):**  
  `launch_paralleldoc.vbs` launches Brave, Microsoft Edge, or Google Chrome in standalone `--app` mode with zero command prompt flashing. `create_desktop_shortcut.vbs` generates a desktop icon in one click.

- 🔍 **Instant Search & Jump:**  
  `Ctrl+F` or click the search box to filter clauses in real time. Press `Enter` / `Shift+Enter` to smoothly scroll through matches. Press `Escape` to reset.

- 📐 **Customizable Reading Experience:**  
  Adjust font size (`[A-]` / `[A+]`), toggle line-height (`1.6` / `1.78` / `1.9`), and adjust column width ratios (`30/30/40`, `33/33/33`, `25/25/50`). Settings persist automatically in browser `localStorage`.

---

## 🚀 Quick Start

### Windows (Recommended)
1. Double-click `launch_paralleldoc.vbs` to launch in silent app mode.
2. (Optional) Double-click `create_desktop_shortcut.vbs` to place a permanent shortcut on your Desktop.

### Linux / macOS / Browser
Open `paralleldoc.html` directly in any Chromium-based browser:
```bash
brave --app="file://$(pwd)/paralleldoc.html"
# or
google-chrome --app="file://$(pwd)/paralleldoc.html"
```

---

## 📊 Document Data Schema (`cockpit-v1.json`)

Documents are structured as clean, readable JSON files:

```json
{
  "$schema": "https://antigravity.local/schemas/cockpit-v1.json",
  "metadata": {
    "title": "Sample: Cloud Infrastructure SLA & Security Review",
    "document_id": "DOC-2026-SEC-SLA-001",
    "created_at": "2026-09-04T12:00:00Z",
    "source_file": "sla_specification.docx"
  },
  "columns": [
    { "key": "col1", "title": "Original Clause (EN)", "width_weight": 30 },
    { "key": "col2", "title": "Target Translation (UA)", "width_weight": 30 },
    { "key": "col3", "title": "Engineering & Risk Assessment (EN)", "width_weight": 40 }
  ],
  "items": [
    {
      "id": "1",
      "col1": "1. High Availability: Service availability must be at least 99.95%...",
      "col2": "1. Висока доступність: Доступність сервісу не менше 99.95%...",
      "col3": "✅ **Compliance:** Multi-AZ architecture satisfies target requirements..."
    }
  ]
}
```

*Markdown formatting:* Cells support standard Markdown formatting including `**bold**`, `*italic*`, code blocks (`` `code` ``), and bulleted lists (`- item`).

---

## 🛠️ CLI Utilities

ParallelDoc includes lightweight Python utilities:

### 1. Initialize a Blank Document
```bash
python generate_paralleldoc.py --init my_document.json --title "Contract Analysis #42"
```

### 2. Convert from TSV / Spreadsheet
Create a 3-column tab-separated file (`col1 <tab> col2 <tab> col3`) and convert it directly:
```bash
python generate_paralleldoc.py --from-tsv input.tsv -o my_document.json --title "Tender Review"
```

### 3. Validate Document & Compute SHA-256
```bash
python validate_document.py my_document.json
```

---

## 🧪 Testing & Verification

ParallelDoc includes an end-to-end headless browser test suite using Chrome DevTools Protocol (CDP):

```bash
# Run headless browser verification
python test_cockpit_cdp.py
```

Tests verify:
- Accurate DOM title and metadata rendering.
- Exact match between Python-computed SHA-256 and browser Web Crypto API display.
- Row structure and markdown list grouping.
- In-memory highlighting, direct click unwrap, and selection clearing.
- Cross-column selection protection (prevents grid corruption).
- Real-time search filtering, Enter navigation, and Escape reset.
- Clipboard copy fallbacks.

---

## 💡 Extending & Forking

ParallelDoc is built to serve as a clean base for specialized forks:
- **ParallelDoc Visual:** Extend Column 3 with bundled client-side Mermaid.js or SVG canvas rendering for automated architecture diagrams.
- **ParallelDoc Legal Diff:** Add word-level redlining diff algorithms across Column 1 and Column 2.
- **ParallelDoc Audio:** Connect Web Speech API for line-by-line synchronized text-to-speech dictation.

See [`CONTRIBUTING.md`](CONTRIBUTING.md) for contribution guidelines and coding standards.

---

## 📄 License

MIT License — see [`LICENSE`](LICENSE) for details.
