"""
ParallelDoc 3.0 (r2 / V3-ONLY) — Challenger M2-r2 Test Integration.

Executes both Node.js adversarial test suites from within pytest, ensuring
continuous verification of the 3 remediated discrepancies:
1. Manifest expected_sha256 lowercase hex pattern
2. Manifest additionalProperties: false & document_id/revision string types
3. V8 syntax error locator line/column fallback accuracy
"""

import subprocess
from pathlib import Path
import pytest


def test_adversarial_loader_node_runner():
    """Execute tests/test_adversarial_loader_node.cjs and assert 0 failures."""
    test_path = Path(__file__).resolve().parent / "test_adversarial_loader_node.cjs"
    repo_root = Path(__file__).resolve().parent.parent

    proc = subprocess.run(
        ["node", str(test_path)],
        capture_output=True,
        text=True,
        cwd=str(repo_root),
    )
    assert proc.returncode == 0, f"Node.js runner failed:\n{proc.stdout}\n{proc.stderr}"
    assert "Passed: 38, Failed: 0" in proc.stdout


def test_adversarial_remediation_m2_r2_stress():
    """Execute tests/test_adversarial_remediation_m2_r2.cjs (61 adversarial assertions)."""
    test_path = Path(__file__).resolve().parent / "test_adversarial_remediation_m2_r2.cjs"
    repo_root = Path(__file__).resolve().parent.parent

    proc = subprocess.run(
        ["node", str(test_path)],
        capture_output=True,
        text=True,
        cwd=str(repo_root),
    )
    assert proc.returncode == 0, f"Challenger stress suite failed:\n{proc.stdout}\n{proc.stderr}"
    assert "Passed: 61, Failed: 0" in proc.stdout
