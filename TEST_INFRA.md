# E2E Test Infra: ParallelDoc 3.0 (r2 / V3-ONLY)

## Test Philosophy
- Opaque-box, requirement-driven. Derived from normative spec r2 (`SPEC__2026-09-06__ParallelDoc_Design_Vision__ASTRA_INDEPENDENT.md`) and `ORIGINAL_REQUEST.md`.
- Zero reuse of failed fixtures from commit `d6af4e5a9f58495e5e75ecdc87df33908ff62d85`. Everything built fresh from spec r2.
- Methodology: Category-Partition + Boundary Value Analysis + Pairwise Interaction + Real-World Workload Testing (Tiers 1-4).
- Honest accounting: Unperformed checks are never marked PASS. Unavailable environments (Linux GUI browser in WSL2) are marked BLOCKED with explicit rationale. AC-47 is strictly PENDING ACCEPTANCE / BLOCKED until human pilot execution.

## Feature Inventory & Test Mapping (44 Active P0 Criteria)

| # | Criterion | Tier 1 (Feature) | Tier 2 (Boundary) | Tier 3 (Cross) | Tier 4 (Scenario) |
|---|-----------|:----------------:|:-----------------:|:--------------:|:-----------------:|
| AC-01 | Offline delivery (0 network calls) | 5 | 5 | ✓ | ✓ |
| AC-02 | File open & switch; reject E | 5 | 5 | ✓ | ✓ |
| AC-07 | Draft 2020-12 Schema v3 enforcement | 5 | 5 | ✓ | ✓ |
| AC-08 | Referential integrity & orphan units | 5 | 5 | ✓ | ✓ |
| AC-09 | ID & revision stability | 5 | 5 | ✓ | ✓ |
| AC-10 | Author & epistemic workflow status | 5 | 5 | ✓ | ✓ |
| AC-11 | Multi-panel profiles 2, 3, 4 | 5 | 5 | ✓ | ✓ |
| AC-12 | Central interactive relationship graph | 5 | 5 | ✓ | ✓ |
| AC-13 | Semantic utility of graph (SLA control) | 5 | 5 | ✓ | ✓ |
| AC-14 | Graph -> Text cross-highlight (delta=0) | 5 | 5 | ✓ | ✓ |
| AC-15 | Text -> Graph cross-highlight | 5 | 5 | ✓ | ✓ |
| AC-16 | Navigation history stack (10 targets) | 5 | 5 | ✓ | ✓ |
| AC-17 | Graph aesthetics (labels >=14px, pan/zoom) | 5 | 5 | ✓ | ✓ |
| AC-18 | Text fallback table for graph | 5 | 5 | ✓ | ✓ |
| AC-19 | Embedded raster thumbnails (PNG/JPEG/WebP)| 5 | 5 | ✓ | ✓ |
| AC-20 | Modal 1:1 pixel inspector & keyboard pan | 5 | 5 | ✓ | ✓ |
| AC-21 | Portable transfer Windows <-> Linux (WSL2)| 5 | 5 | ✓ | ✓ |
| AC-22 | Unavailable asset placeholders (<=2px shift)| 5 | 5 | ✓ | ✓ |
| AC-23 | Diagnostic error blocks for broken media | 5 | 5 | ✓ | ✓ |
| AC-24 | Asset locator security (no UNC/file:) | 5 | 5 | ✓ | ✓ |
| AC-25 | Raw SHA-256 (preserves BOM, no CRLF norm)| 5 | 5 | ✓ | ✓ |
| AC-26 | Detached integrity manifest validation | 5 | 5 | ✓ | ✓ |
| AC-27 | 8 independent trust states display | 5 | 5 | ✓ | ✓ |
| AC-28 | Simultaneous multi-error handling | 5 | 5 | ✓ | ✓ |
| AC-29 | Honest trust boundaries presentation | 5 | 5 | ✓ | ✓ |
| AC-30 | Reading (18px) vs Dense (15px) typography | 5 | 5 | ✓ | ✓ |
| AC-31 | Progressive disclosure (>1200 chars quote)| 5 | 5 | ✓ | ✓ |
| AC-32 | Literal full-text search (10 test queries)| 5 | 5 | ✓ | ✓ |
| AC-33 | Browser Find (Ctrl+F) compatibility mode | 5 | 5 | ✓ | ✓ |
| AC-34 | Sticky header limits (<=160px desktop) | 5 | 5 | ✓ | ✓ |
| AC-35 | Reflow down to 320px without h-scroll | 5 | 5 | ✓ | ✓ |
| AC-36 | Session restoration across 5 re-opens | 5 | 5 | ✓ | ✓ |
| AC-37 | Version isolation (hashes don't leak pos) | 5 | 5 | ✓ | ✓ |
| AC-38 | 100% Keyboard accessibility & no traps | 5 | 5 | ✓ | ✓ |
| AC-39 | Accessible names, ARIA states, >=24px touch | 5 | 5 | ✓ | ✓ |
| AC-40 | WCAG AA contrast (>=4.5:1 normal, >=3:1 UI) | 5 | 5 | ✓ | ✓ |
| AC-41 | Screen reader sequential order & motion | 5 | 5 | ✓ | ✓ |
| AC-42 | Security injection suite S execution (0 exec)| 5 | 5 | ✓ | ✓ |
| AC-43 | Stress performance benchmarks (corpus R) | 5 | 5 | ✓ | ✓ |
| AC-44 | Large graph handling (200 nodes/400 edges) | 5 | 5 | ✓ | ✓ |
| AC-45 | Read-only source safety (0 bytes modified) | 5 | 5 | ✓ | ✓ |
| AC-46 | Fork freedom & extension preservation | 5 | 5 | ✓ | ✓ |
| AC-47 | Human cognitive recovery pilot (>=24h) | - | - | - | BLOCKED |
| AC-48 | Complete structured evidence report | 5 | 5 | ✓ | ✓ |

## Real-World Application Scenarios (Tier 4)
1. **Scenario 1 (G Corpus - SLA Evaluation)**: Legal/technical SLA assessment of Cloud Provider uptime (99.95% vs 99.99%) with maintenance window exclusion, 6-node decision graph, 3 diagram assets, Russian quote analysis (>8k chars), cross-highlighting, and conclusion derivation matching control answer table.
2. **Scenario 2 (Corrupted & Malicious Feed)**: Ingestion of mixed corpus with schema errors, corrupted image base64, MIME spoofing, and XSS injection vectors; verifying clean rejection of malformed files and graceful diagnostic rendering of damaged media without document crash.
3. **Scenario 3 (Extreme Stress Load - R Corpus)**: 1,000 units across 250 groups, 100 graph nodes / 150 edges, 12 MiB embedded assets. Verifying cold load <= 3s, thumbnail rendering <= 5s, highlight latency <= 100ms, and search <= 300ms.
4. **Scenario 4 (Multi-profile Navigation & Session Recovery)**: User inspecting document in Evidence (3 panels), switching to Compare (2 panels) and Review (4 panels), expanding folded quotes, searching for clauses, closing viewer, and re-opening to verify exact reading position within 1 text line.
5. **Scenario 5 (Cross-Platform Integrity Check)**: Document loaded on Windows and verified via CLI on Linux WSL2; verifying byte-identical SHA-256 and detached manifest validation under spaces and Unicode directory paths.

## Test Harness & Invocation
- Python Test Runner: `pytest tests/ -v`
- Headless Browser Test Runner (CDP): `python tests/test_e2e_cdp.py` (runs against isolated port, e.g. 9223)
- Verification Matrix Script: `python tests/verify_44_p0.py`
