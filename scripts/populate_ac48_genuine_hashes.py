#!/usr/bin/env python3
"""
scripts/populate_ac48_genuine_hashes.py — Programmatic AC-48 Evidence Report Generator.

Computes 100% authentic, full 64-hex SHA-256 digests directly from on-disk files
for all 71 fixtures across all 6 corpora (V, G, M, E, S, R) and updates Section 5
of AC-48_EVIDENCE_REPORT.md with zero truncation and zero fabricated characters.
"""

import hashlib
import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
REPORT_FILE = PROJECT_ROOT / "AC-48_EVIDENCE_REPORT.md"
FIXTURES_DIR = PROJECT_ROOT / "fixtures"


def audit_on_disk_fixtures(fixtures_dir: Path):
    corpora = ["corpus_V", "corpus_G", "corpus_M", "corpus_E", "corpus_S", "corpus_R"]
    file_registry = {}
    corpora_summary = {}
    grand_total_files = 0
    grand_total_bytes = 0

    for corp in corpora:
        cdir = fixtures_dir / corp
        if not cdir.exists():
            raise FileNotFoundError(f"Corpus directory {cdir} does not exist")
        
        files = sorted([f for f in cdir.iterdir() if f.is_file()])
        corp_bytes = 0
        corpora_summary[corp] = {"count": len(files), "bytes": 0}

        for f in files:
            raw_bytes = f.read_bytes()
            sha = hashlib.sha256(raw_bytes).hexdigest().lower()
            size = len(raw_bytes)
            corp_bytes += size
            file_registry[f.name] = {
                "corpus": corp,
                "bytes": size,
                "bytes_formatted": f"{size:,}",
                "sha256": sha
            }

        corpora_summary[corp]["bytes"] = corp_bytes
        grand_total_files += len(files)
        grand_total_bytes += corp_bytes

    return file_registry, corpora_summary, grand_total_files, grand_total_bytes


def update_evidence_report():
    if not REPORT_FILE.exists():
        print(f"Error: {REPORT_FILE} not found", file=sys.stderr)
        sys.exit(1)

    file_registry, corpora_summary, total_files, total_bytes = audit_on_disk_fixtures(FIXTURES_DIR)
    print(f"Audited {total_files} files across 6 corpora ({total_bytes:,} bytes / {total_bytes / (1024*1024):.2f} MiB).")

    lines = REPORT_FILE.read_text(encoding="utf-8").splitlines()
    updated_lines = []
    in_sec5 = False
    updated_row_count = 0

    # Matches any markdown table row starting with a filename in column 1: | `filename` | ...
    row_pattern = re.compile(r"^\|\s*[`]?([a-zA-Z0-9_.-]+)[`]?\s*\|(.*)$")

    for line in lines:
        if line.startswith("## 5. Corpora Audit Manifest"):
            in_sec5 = True
            updated_lines.append(line)
            continue
        elif in_sec5 and line.startswith("## 6."):
            in_sec5 = False
            updated_lines.append(line)
            continue

        if in_sec5:
            # Update summary statistics in Section 5
            if line.startswith("- **Total Fixture Files**:"):
                updated_lines.append(f"- **Total Fixture Files**: {total_files}")
                continue
            if line.startswith("- **Total Payload Size**:"):
                updated_lines.append(f"- **Total Payload Size**: {total_bytes:,} bytes ({total_bytes / (1024*1024):.2f} MiB)")
                continue

            # Update corpus subsection headers
            if "#### Corpus V:" in line:
                s = corpora_summary["corpus_V"]
                updated_lines.append(f"#### Corpus V: Valid Baseline Fixtures ({s['count']} files, {s['bytes']:,} bytes)")
                continue
            if "#### Corpus G:" in line:
                s = corpora_summary["corpus_G"]
                updated_lines.append(f"#### Corpus G: Golden Benchmark Fixtures ({s['count']} files, {s['bytes']:,} bytes)")
                continue
            if "#### Corpus M:" in line:
                s = corpora_summary["corpus_M"]
                updated_lines.append(f"#### Corpus M: Media Contract Fixtures ({s['count']} files, {s['bytes']:,} bytes)")
                continue
            if "#### Corpus E:" in line:
                s = corpora_summary["corpus_E"]
                updated_lines.append(f"#### Corpus E: Error & Boundary Fixtures ({s['count']} files, {s['bytes']:,} bytes)")
                continue
            if "#### Corpus S:" in line:
                s = corpora_summary["corpus_S"]
                updated_lines.append(f"#### Corpus S: Security Injection Fixtures ({s['count']} files, {s['bytes']:,} bytes)")
                continue
            if "#### Corpus R:" in line:
                s = corpora_summary["corpus_R"]
                updated_lines.append(f"#### Corpus R: Stress & Performance Fixtures ({s['count']} files, {s['bytes']:,} bytes)")
                continue

            m = row_pattern.match(line)
            if m:
                fname = m.group(1)
                remainder = m.group(2)
                if fname in file_registry:
                    finfo = file_registry[fname]
                    # Parse existing columns: cols[0] is old bytes, cols[1] is old sha, cols[2..] are extra cols
                    cols = [c.strip() for c in remainder.split("|")]
                    extra_cols = [c for c in cols[2:] if c]
                    extra_str = f" {' | '.join(extra_cols)} |" if extra_cols else ""
                    
                    # Construct clean, 100% genuine markdown table row
                    new_row = f"| `{fname}` | {finfo['bytes_formatted']} | `{finfo['sha256']}` |{extra_str}"
                    updated_lines.append(new_row)
                    updated_row_count += 1
                    continue

        updated_lines.append(line)

    assert updated_row_count == 71, f"Expected to update 71 table rows, but updated {updated_row_count}"
    REPORT_FILE.write_text("\n".join(updated_lines) + "\n", encoding="utf-8")
    print(f"SUCCESS: Updated all {updated_row_count} fixture rows in {REPORT_FILE} with 100% authentic 64-hex SHA-256 digests.")


if __name__ == "__main__":
    update_evidence_report()
