# 📐 ParallelDoc: 3-Pane Comparative Document Inspector

> **Status:** `PRODUCTION RELEASE SPECIFICATION (V2.1)`  
> **Type:** Domain-Agnostic Visual Document Inspector (Standalone Desktop App)  
> **License:** MIT Open Source  

---

## 1. Purpose & Concept

**ParallelDoc** is a standalone, focused desktop workspace for reading, cross-referencing, and comparative analysis of three-tier textual data:
- **Original Clause ↔ Translation ↔ Technical & Risk Analysis** (international procurement, contracts, technical specifications).
- **Previous Revision ↔ New Revision ↔ Change Impact** (legal redlines, RFC amendments, code diff reviews).
- **Requirements ↔ Vendor Proposals ↔ Compliance Scoring** (RFP audits, vendor diligence).

### Architectural Principle (Separation of Concerns):
- **Viewer (ParallelDoc Engine):** Completely autonomous, deterministic, zero-dependency HTML5 application. It performs **no autonomous network requests and makes no disk modifications**. Its sole responsibility is reliable layout rendering, book-grade typography, instant search, and cryptographic integrity verification.
- **Intelligence (AI Agents & CLI Scripts):** Any autonomous agent, LLM pipeline, or CLI converter prepares data conforming to the open `cockpit-v1.json` specification.
- **Human-in-the-Loop Anti-Drift:** Operators keep the window open side-by-side with their chat session, referencing specific clause numbers while a full 64-character SHA-256 hash is permanently visible on screenshots for automated verification by the AI model.

---

## 2. Canonical Data Protocol (JSON Schema)

Every document is stored as a clean, human-readable `.json` file conforming to the following structure:

```json
{
  "$schema": "https://antigravity.local/schemas/cockpit-v1.json",
  "metadata": {
    "title": "Sample: Cloud Infrastructure SLA & Security Compliance Review",
    "document_id": "DOC-2026-SEC-SLA-001",
    "created_at": "2026-09-04T12:00:00Z",
    "source_file": "cloud_sla_security_specification.docx"
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

*Markdown Cell Formatting:* Text cells support standard inline and block Markdown formatting, including `**bold**`, `*italic*`, inline code (`` `code` ``), and structured bullet lists (`- item`).

---

## 3. Anti-Drift Cryptographic Header

A sticky header panel is permanently pinned at the top:
1. **Full 64-Character SHA-256 Hash Badge (Primary Anchor):**
   - Positioned in the priority top-left quadrant (before the document title).
   - Displayed in large, high-contrast monospace font (`ui-monospace`, 14–15px) inside a prominent locked badge 🔒.
   - Any screen capture or window snip of the clause view immediately captures the hash for LLM provenance verification.
   - Clicking the badge copies the full hash string to the system clipboard.
2. **Document Title & Clause Count:** Clean typography indicating title and total item count.
3. **Instant Search (`Ctrl+F`):** Live filtering and highlighted matches with circular `Enter` / `Shift+Enter` navigation.

---

## 4. Visual Ergonomics & ClearType Typography

1. **Typeface:** Classic serif typography **Georgia** (`font-family: Georgia, Cambria, 'Times New Roman', serif;`).
2. **Base Size:** **16.5px** (user-scalable between 14px and 22px).
3. **Line Height:** **1.78** (switchable to 1.6 or 1.95) for fatigue-free long-form reading.
4. **Subpixel ClearType Antialiasing (Windows Optimization):**
   ```css
   body, * {
     -webkit-font-smoothing: subpixel-antialiased !important;
     -moz-osx-font-smoothing: auto !important;
     text-rendering: optimizeLegibility !important;
   }
   ```
5. **Theme:** Gentle book reading aesthetic:
   - Canvas: Soft off-white `#fcfcfd`.
   - Cards: Pure white `#ffffff` with subtle borders (`#e5e7eb`).
   - Body text: Deep graphite `#1f2937` (avoiding harsh pure black).
6. **Callout Row Badges:**
   - Prominent badge numbering (`#1`, `#2`) to the left of each row.
   - Clicking any badge instantly copies the clause ID.
7. **Synchronized Row Grid:**
   - Columns are locked row-by-row with top alignment.
   - Heavy analysis in Column 3 never offsets or misaligns Columns 1 and 2.

---

## 5. In-Memory Highlighter

Optimized for preparing annotated screenshots for chat discussions:
- Select text in any column to summon the floating micro-toolbar:
  - 🟡 **Yellow Highlight** (`#fef08a`).
  - 🔴 **Red Accent** (`border-bottom: 2px solid #ef4444`).
  - ⚪ **Clear:** Unwraps `<mark>` tags cleanly without breaking text nodes.
- Direct click on any existing highlight immediately removes it.

---

## 6. Preferences & State Persistence

The top settings bar allows customization of:
- Font scale (`[A-]` / `[A+]`).
- Line height (`1.6` / `1.78` / `1.95`).
- Column width distribution (`30/30/40`, `33/33/33`, `25/25/50`).
- Settings persist across sessions in browser `localStorage`.

---

## 7. Packaging & Desktop Execution

1. **Zero-Dependency Single HTML5 File:** `paralleldoc.html` embeds all CSS, SVG icons, Markdown parser, and Web Crypto logic.
2. **Silent Desktop Execution (Windows):**
   - `launch_paralleldoc.vbs` executes Chromium browsers in `--app` mode without console window flashing.
   - `create_desktop_shortcut.vbs` provisions a desktop icon in one click.
