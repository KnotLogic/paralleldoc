#!/usr/bin/env python3
"""
fixtures/materialize_all_corpora.py — Master Corpora Materializer for ParallelDoc 3.0.

Deterministically synthesizes and verifies all 6 independent test corpora:
- Corpus V (Valid Variants: 11 docs + manifest + control)
- Corpus G (SLA Benchmark: SLA doc + control json/md)
- Corpus M (Media Contract: 24 fixtures + control)
- Corpus E (Error Fixtures: 14 fixtures + manifest + control)
- Corpus S (Security Injection: 6 fixtures + control)
- Corpus R (Stress & Scale: 1,000 units doc + 200n/400e + 201n/401e + control)

Strictly complies with Spec r2 §8, §9, §11, §12 without reusing failed artifacts.
"""

import hashlib
import os
import sys
import time
from pathlib import Path

# Add fixtures directory to import path
FIXTURES_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = FIXTURES_DIR.parent
sys.path.insert(0, str(FIXTURES_DIR))
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from generate_corpus_v import generate_corpus_v
from generate_corpus_g import generate_corpus_g
from generate_corpus_m import generate_corpus_m
from generate_corpus_e import generate_corpus_e
from generate_corpus_s import generate_corpus_s
from generate_corpus_r import generate_corpus_r


def materialize_all(base_dir: Path = FIXTURES_DIR) -> dict:
    """Run all generators and compile a comprehensive inventory."""
    start_time = time.perf_counter()
    print("=" * 70)
    print("PARALLELDOC 3.0: MATERIALIZING ALL 6 TEST CORPORA")
    print(f"Target directory: {base_dir}")
    print("=" * 70)

    # 1. Corpus V
    print("\n[1/6] Materializing Corpus V (Valid Variants)...")
    v_dir = base_dir / "corpus_V"
    v_dir.mkdir(parents=True, exist_ok=True)
    generate_corpus_v(v_dir)

    # 2. Corpus G
    print("\n[2/6] Materializing Corpus G (SLA Benchmark Document)...")
    g_dir = base_dir / "corpus_G"
    g_dir.mkdir(parents=True, exist_ok=True)
    generate_corpus_g(g_dir)

    # 3. Corpus M
    print("\n[3/6] Materializing Corpus M (24 Media Contract Fixtures)...")
    m_dir = base_dir / "corpus_M"
    m_dir.mkdir(parents=True, exist_ok=True)
    generate_corpus_m(m_dir)

    # 4. Corpus E
    print("\n[4/6] Materializing Corpus E (14 Error Fixtures)...")
    e_dir = base_dir / "corpus_E"
    e_dir.mkdir(parents=True, exist_ok=True)
    generate_corpus_e(e_dir)

    # 5. Corpus S
    print("\n[5/6] Materializing Corpus S (6 Security Injection Fixtures)...")
    s_dir = base_dir / "corpus_S"
    s_dir.mkdir(parents=True, exist_ok=True)
    generate_corpus_s(s_dir)

    # 6. Corpus R
    print("\n[6/6] Materializing Corpus R (Stress 1,000 Units & Scale Fixtures)...")
    r_dir = base_dir / "corpus_R"
    r_dir.mkdir(parents=True, exist_ok=True)
    generate_corpus_r(r_dir)

    elapsed = time.perf_counter() - start_time

    # Compile comprehensive inventory
    corpora = ["corpus_V", "corpus_G", "corpus_M", "corpus_E", "corpus_S", "corpus_R"]
    inventory = {}
    total_files = 0
    total_bytes = 0

    print("\n" + "=" * 70)
    print("MATERIALIZATION AUDIT SUMMARY")
    print("=" * 70)

    for corp in corpora:
        cdir = base_dir / corp
        files = sorted([f for f in cdir.iterdir() if f.is_file()])
        c_bytes = sum(f.stat().st_size for f in files)
        inventory[corp] = {
            "count": len(files),
            "bytes": c_bytes,
            "files": []
        }
        total_files += len(files)
        total_bytes += c_bytes
        print(f"\n{corp} ({len(files)} files, {c_bytes:,} bytes):")
        for f in files:
            raw_data = f.read_bytes()
            sha = hashlib.sha256(raw_data).hexdigest()
            inventory[corp]["files"].append({
                "name": f.name,
                "bytes": len(raw_data),
                "sha256": sha
            })
            print(f"  - {f.name:<45} {len(raw_data):>10,} bytes  SHA: {sha}")

    print("\n" + "-" * 70)
    print(f"TOTAL: {total_files} files, {total_bytes:,} bytes ({total_bytes / (1024*1024):.2f} MiB)")
    print(f"Generation completed in {elapsed:.3f} seconds.")
    print("=" * 70)

    return {
        "status": "SUCCESS",
        "total_files": total_files,
        "total_bytes": total_bytes,
        "elapsed_seconds": elapsed,
        "corpora": inventory
    }


if __name__ == "__main__":
    res = materialize_all()
    if res["status"] != "SUCCESS":
        sys.exit(1)
