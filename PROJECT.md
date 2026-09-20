# Project: ParallelDoc 3.0 (r2 / V3-ONLY)

> **Normative Reference**: `SPEC__2026-09-06__ParallelDoc_Design_Vision__ASTRA_INDEPENDENT.md` (r2 / V3-ONLY)  
> **Normative SHA-256**: `7d3097dedab3211beafa77efd2fd9d29dd7f95c30b353cfec9e8d13e01ee84ea`  
> **Workspace**: `C:\_Antigravity\A_4_Antigravity-Improvement\tools\paralleldoc`  
> **Status**: IN_PROGRESS  

---

## Architecture

ParallelDoc 3.0 is an offline document viewer and semantic verification ecosystem designed around declarative Draft 2020-12 schemas, a strict V3-only pipeline, an interactive visual relationship graph, multi-panel layouts, and independent trust axes.

```
+-------------------------------------------------------------------------------+
|                             PARALLELDOC 3.0 RUNTIME                           |
+-------------------------------------------------------------------------------+
| 1. Ingestion & Integrity:                                                     |
|    - Raw Byte Reader -> Exact SHA-256 (preserves UTF-8 BOM, zero CRLF norm)   |
|    - V3-Only Guard -> Rejects legacy/unknown with exact diagnostic message    |
|    - Draft 2020-12 Validator -> schema.v3.json & manifest.schema.json         |
+-------------------------------------------------------------------------------+
| 2. Semantic Graph & Core Data Model:                                          |
|    - 4 Unit Kinds: source, model, analysis, action                            |
|    - 6 Typed Relations: supports, qualifies, contradicts, depends_on,         |
|      precedes (directed), compares (symmetric)                                |
|    - Referential Integrity: units, groups, authors, assets, visuals           |
|    - Cycle Tolerance in depends_on; orphan collection under «Вне групп»       |
+-------------------------------------------------------------------------------+
| 3. Presentation Engine (paralleldoc.html - 100% Offline):                     |
|    - Multi-Panel Profiles: Compare (50/50), Evidence (32/36/32), Review       |
|    - Central Interactive Relationship Graph (labels >= 14px, zoom/pan/fit)    |
|    - Text Fallback Table (for disabled graphics / large graph > 200n/400e)    |
|    - Bidirectional Cross-Highlighting (Graph <-> Text) with scroll delta = 0  |
|    - Media Contract: PNG/JPEG/static WebP (budget <= 8MB/32MB, layout <= 2px) |
|    - Modal 1:1 Pixel Inspector with keyboard pan & Esc return                 |
|    - Typography: Reading (18px serif) vs Dense (15px sans), 14-24px sizing    |
|    - 3 Independent Trust Axes: Structure, Integrity, Epistemic/Workflow       |
+-------------------------------------------------------------------------------+
| 4. Verification & Corpora Suite:                                              |
|    - Corpora: V (Valid), G (SLA Benchmark), M (Media), E (Error),             |
|      S (Security Injection), R (Stress Load 1,000 units)                      |
|    - 44 Active P0 Criteria: 43 Technical + AC-47 (Pending Human Pilot)        |
+-------------------------------------------------------------------------------+
```

---

## Feature Inventory

Every feature mapped from Spec r2 survey with assigned milestone:

| # | Feature | Description | Milestone | Source |
|---|---------|-------------|-----------|--------|
| F01 | Draft 2020-12 Document Schema | `schema.v3.json` with 9 required top-level collections & 18 `$defs` | M1 | Spec §8 |
| F02 | Draft 2020-12 Manifest Schema | `manifest.schema.json` with `scope: "raw-bytes"`, algorithm SHA-256 | M1 | Spec §8 |
| F03 | Referential Integrity Engine | Cross-collection validation (relations, units, authors, assets, groups) | M1 | Spec §8 |
| F04 | Orphan Unit Reconciliation | Automatic gathering of ungrouped units under «Вне групп» | M1 | Spec §8 |
| F05 | Test Harness & Meta-validation | Python + jsonschema Draft202012 test runner for schemas and refs | M1 | Spec §8, §11 |
| F06 | Raw Byte SHA-256 Engine | Digest computed over raw UTF-8 bytes (BOM preserved, no CRLF/LF norm) | M2 | Spec §7, §9 |
| F07 | V3-Only Format Guard | Rejection of non-v3 / legacy with exact message «Неподдерживаемый формат; требуется ParallelDoc 3.0» | M2 | Spec §9 |
| F08 | Raw Preview Diagnostics | Safe raw text preview for rejected non-v3 inputs with error pointer | M2 | Spec §9 |
| F09 | No Auto-Migration / Fallback | Blocking rejection without converting legacy formats or silent fallback | M2 | Spec §9 |
| F10 | Standalone Offline HTML Viewer | `paralleldoc.html` with zero external remote network dependencies | M3 | Spec §1, §3 |
| F11 | Interactive Relationship Graph | SVG/Canvas graph, labels >= 14px, zoom/pan/fit, cycle-tolerant | M3 | Spec §3, §6 |
| F12 | 6 Typed Relations Engine | Directional arrows for supports/qualifies/contradicts/depends_on/precedes; symmetric for compares | M3 | Spec §3, §8 |
| F13 | Graph Visual Legend | Visible legend indicating all 6 relation types and direction semantics | M3 | Spec §3 |
| F14 | Graph Accessible Fallback Table | Readable table (From - Relation - To - Grounds) for disabled graphics | M3 | Spec §3, §6 |
| F15 | Graph Scale Limit Guard | 200 nodes / 400 edges visual guard with explicit banner and full table | M3 | Spec §6, §11 |
| F16 | Bidirectional Cross-Highlighting | Graph <-> Text highlighting with zero scroll jump (delta = 0) | M3 | Spec §3, §4 |
| F17 | Multi-Panel Profile: Compare (2) | 50/50 layout (Foundations / Conclusion & Action) with model strip | M3 | Spec §4, §6 |
| F18 | Multi-Panel Profile: Evidence (3)| 32/36/32 layout (Source / Model / Analysis & Actions) with central graph | M3 | Spec §4, §6 |
| F19 | Multi-Panel Profile: Review (4)  | 28/30/26/16 layout (Source / Model / Analysis / Actions) | M3 | Spec §4, §6 |
| F20 | Zero Unit Loss on Profile Switch | All 4 roles visible across all profiles without dropped units | M3 | Spec §4, §6 |
| F21 | Explicit Missing Role Badges     | Visible placeholders («Нет анализа», «Действие не задано») | M3 | Spec §4 |
| F22 | Deep Navigation & History Stack  | 10-target history stack, jump with auto-expansion, return-to-anchor | M3 | Spec §4, §6 |
| F23 | Typography & Density Modes       | Reading (18px serif, 1.7) vs Dense (15px sans, 1.45), 14-24px sizing | M3 | Spec §6 |
| F24 | Progressive Disclosure of Quotes | Quotes > 1,200 chars folded with exact whitespace/indent copy fidelity | M3 | Spec §6 |
| F25 | Literal Full-Text Search         | Literal search across all units/nodes/captions with Enter/Shift+Enter | M3 | Spec §6 |
| F26 | Browser Find Compatibility Mode  | DOM unrolling mode for Ctrl+F access to all content | M3 | Spec §6 |
| F27 | Sticky Header Budget             | <= 160px desktop, <= 96px narrow, full 64-char SHA copyable | M3 | Spec §6 |
| F28 | Responsive Reflow & Mobile Zoom  | Reflow down to 320px single column without horizontal document scroll | M3 | Spec §6 |
| F29 | Session Persistence & Keying     | Restore profile, size, density, anchor across 5 re-opens; storage badge | M3 | Spec §6 |
| F30 | Keyboard Operability & Focus     | 100% keyboard operable, visible focus ring, zero focus traps | M3 | Spec §4, §11 |
| F31 | Screen Reader Sequential Order   | Source -> Graph Relation -> Analysis -> Image Alt sequential flow | M3 | Spec §4, §11 |
| F32 | WCAG AA Contrast Compliance      | >= 4.5:1 normal, >= 3:1 large/UI, redundant non-color encoding | M3 | Spec §6, §11 |
| F33 | Prefers-Reduced-Motion Support   | Zero mandatory animations/pulses when reduced-motion preferred | M3 | Spec §4, §11 |
| F34 | Embedded Raster Media Contract   | PNG, JPEG, static WebP embedded as Data URI (mime/base64 check) | M4 | Spec §5 |
| F35 | Strict Media Budget Enforcement  | <= 8 MiB/asset, <= 32 MiB total, <= 50 assets, <= 16 MP, <= 8192px side | M4 | Spec §5 |
| F36 | Pre-Reserved Thumbnail Geometry  | Fixed thumbnail frame (<= 240x144px normal) with layout shift <= 2px | M4 | Spec §5 |
| F37 | Modal 1:1 Pixel Inspector        | Modal zoom with keyboard panning, Esc return, focus restoration | M4 | Spec §5 |
| F38 | Media Failure Resilience         | Graceful diagnostic error blocks for corrupted/spoofed media without crash | M4 | Spec §5 |
| F39 | Asset Locator Security Guard     | Rejection of Windows drive, UNC, `file:`, traversal, credentials | M4 | Spec §5, §11 |
| F40 | 3 Independent Trust Axes Model   | Structure, Integrity, Epistemic/Workflow independent tracking | M4 | Spec §7 |
| F41 | 8 Distinct Integrity States      | Visual representation of 8 integrity/trust states per §7 table | M4 | Spec §7 |
| F42 | Detached Manifest Comparison     | Verification of external manifest.json against loaded raw bytes | M4 | Spec §7, §8 |
| F43 | Simultaneous Multi-Error Display | Simultaneous digest mismatch + missing asset displayed clearly | M4 | Spec §7, §11 |
| F44 | Honest Trust Boundaries          | UI clearly presents digest as byte consistency, not objective truth | M4 | Spec §7 |
| F45 | Test Corpus V (Valid Variants)   | Empty collections, UTF-8 LF/CRLF/BOM byte variants, extensions | M5 | Spec §11 |
| F46 | Test Corpus G (SLA Benchmark)    | Synthetic SLA (99.95 vs 99.99), >= 12 groups, >= 24 units, graph, answers | M5 | Spec §11 |
| F47 | Test Corpus M (Media Fixtures)   | 24 media fixtures (valid, corrupted base64, mime spoof, oversized) | M5 | Spec §11 |
| F48 | Test Corpus E (Error Fixtures)   | 14 error fixtures (structural, semantic, legacy v2.1 rejection) | M5 | Spec §11 |
| F49 | Test Corpus S (Security Suite)   | XSS, active scripts, `active_document.js` rejection, malicious paths | M5 | Spec §11 |
| F50 | Test Corpus R (Stress Corpus)    | 1,000 units, 250 groups, 100 nodes/150 edges, 12 MiB assets | M5 | Spec §11 |
| F51 | Performance Benchmarks (AC-43)   | Cold load <= 3s, thumbnails <= 5s, latency <= 100ms/<= 300ms | M5 | Spec §10, §11 |
| F52 | Security Defense Execution (AC-42)| Zero script execution on security injection corpus S | M5 | Spec §11 |
| F53 | Read-only Source Safety (AC-45)  | Zero modification of raw source bytes during inspection | M5 | Spec §11 |
| F54 | Fork Freedom Preservation (AC-46)| Namespaced extensions preserved without loss | M5 | Spec §11 |
| F55 | Environmental Reality Tracking   | Honest reporting: WSL2 Linux browser BLOCKED; AC-47 PENDING ACCEPTANCE | M5 | Spec §11, §12 |
| F56 | Structured Evidence Report AC-48 | Comprehensive matrix covering all 44 active P0s with fixture references | M5 | Spec §11, §12 |

---

## Milestones

| # | Name | Scope | Dependencies | Status |
|---|------|-------|--------------|--------|
| M1 | Schemas & Test Harness | F01..F05 (Draft 2020-12 schemas `schema.v3.json`, `manifest.schema.json`, test harness) | none | **DONE** |
| M2 | V3 Loader & Strict Rejection | F06..F09 (Raw SHA-256 with BOM, V3-only format guard, exact rejection diagnostic) | M1 | **DONE** |
| M3 | Viewer, Semantic Graph & Multi-panel | F10..F33 (`paralleldoc.html`, interactive graph, 2/3/4 profiles, cross-highlight, typography, a11y) | M1, M2 | **DONE** |
| M4 | Media Contract, 1:1 Inspector & Trust Axes | F34..F44 (Data URI raster media, budgets, 1:1 modal inspector, 8 trust states, detached manifest) | M2, M3 | **DONE** |
| M5 | Complete Corpora & Verification of 44 P0s | F45..F56 (Corpora V/G/M/E/S/R, 44 P0 criteria verification, honest accounting, evidence report) | M1..M4 | **IN_PROGRESS** |

### E2E Testing Track (Parallel Track)

| Track | Scope | Deliverables | Status |
|-------|-------|--------------|--------|
| E2E Testing Track | Requirement-driven opaque-box test suite across Tiers 1-4 | `TEST_INFRA.md`, E2E test runner, tests matching 44 P0s, `TEST_READY.md` | IN_PROGRESS |

---

## Interface Contracts

### 1. Schema Validation Interface (`src/schema_validator.py` / `src/schema_validator.js`)
- `validate_document(doc_obj: dict) -> Tuple[bool, List[ValidationError]]`
- `validate_manifest(manifest_obj: dict) -> Tuple[bool, List[ValidationError]]`
- `validate_referential_integrity(doc_obj: dict) -> Tuple[bool, List[IntegrityError]]`

### 2. Loader & Integrity Engine (`src/loader.js`)
- `compute_raw_sha256(raw_bytes: Uint8Array) -> string` (exact lowercase hex)
- `load_document(raw_bytes: Uint8Array) -> DocumentLoadResult`:
  - If valid v3: `{ success: true, doc: object, raw_sha256: string, trust_states: TrustState }`
  - If invalid / unsupported: `{ success: false, error_type: "REJECTED_UNSUPPORTED"|"SCHEMA_INVALID", diagnostic_message: "«Неподдерживаемый формат; требуется ParallelDoc 3.0»"|string, raw_text: string, raw_sha256: string }`

### 3. Graph Engine Contract (`src/graph.js` inside `paralleldoc.html`)
- `render_graph(visual_def: object, container_el: HTMLElement, options: GraphOptions) -> GraphController`
- `GraphController.highlight_nodes(unit_id: string)`: Highlights connected nodes/edges without scroll delta.
- `GraphController.on_select(callback: (selected_node_or_edge) -> void)`: Pins selection and cross-highlights units.
- `GraphController.render_fallback_table(visual_def: object) -> HTMLElement`: Table of all edges with relation types.

### 4. Media & Trust Inspector Contract (`src/media.js` inside `paralleldoc.html`)
- `validate_asset(asset_def: object, total_budget_state: object) -> AssetValidationResult`
- `open_modal_inspector(asset_def: object, origin_el: HTMLElement) -> void` (Traps focus, supports arrow pan, Esc return)

---

## Code Layout

```
C:\_Antigravity\A_4_Antigravity-Improvement\tools\paralleldoc/
├── schema.v3.json                  # Draft 2020-12 Document Schema
├── manifest.schema.json            # Draft 2020-12 Detached Manifest Schema
├── paralleldoc.html                # Deliverable: 100% Standalone Offline Viewer
├── src/                            # Modular source code (bundled into paralleldoc.html & CLI)
│   ├── loader.js                   # Raw SHA-256, V3-only format guard, parser
│   ├── validator.py                # Python schema & referential integrity validator
│   ├── graph.js                    # Interactive semantic relationship graph & fallback table
│   ├── media.js                    # Media contract validator, budgets, modal inspector
│   ├── panels.js                   # Multi-panel layouts (Compare, Evidence, Review)
│   └── search.js                   # Literal full-text search & browser Find mode
├── tests/                          # Automated test suites
│   ├── test_schemas.py             # Schema meta-validation & structural tests
│   ├── test_loader.py              # Loader & rejection tests
│   ├── test_referential.py         # Referential integrity & orphan tests
│   ├── test_media.py               # Media budgets & security tests
│   ├── test_e2e_cdp.py             # Headless CDP browser tests (port 9223+)
│   └── run_all_tests.py            # Master test runner
├── fixtures/                       # Complete Test Corpora
│   ├── corpus_V/                   # Valid v3.0 documents (LF, CRLF, BOM variants)
│   ├── corpus_G/                   # Synthetic SLA benchmark document + control answers
│   ├── corpus_M/                   # Media fixtures (PNG/JPEG/WebP, corrupted, spoofed)
│   ├── corpus_E/                   # Error documents (legacy v2.1, invalid format, broken refs)
│   ├── corpus_S/                   # Security injection suite (XSS, scripts, UNC/file:)
│   └── corpus_R/                   # Stress load corpus (1,000 units, 250 groups)
├── .agents/                        # Agent working metadata (strictly gitignored)
├── PROJECT.md                      # This project specification & tracking index
├── TEST_INFRA.md                   # E2E Test infrastructure index
└── teamwork_progress.md            # Public non-blocking progress log
```
