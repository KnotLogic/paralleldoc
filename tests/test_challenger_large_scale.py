"""
Challenger M1-r2-2 Empirical Stress Test Suite for ParallelDoc 3.0 (Milestone 1).
Objectives:
  1. Large graph scale: chains of 1,200, 2,000, and 5,000 nodes in depends_on.
     Confirm 0 RecursionError and linear execution time.
  2. Torture pointer tests: inject JSON null and primitives across all collection
     and pointer fields. Confirm 0 unhandled TypeError crashes.
  3. Verify all 4 parts of test_adversarial_stress.py pass without xfail.
"""

import copy
import time
from typing import Any, Callable, Dict, List
import pytest

from validator import (
    IntegrityEngine,
    IssueSeverity,
    ValidationIssue,
    validate_document,
)


# =============================================================================
# OBJECTIVE 1: Large Graph Scale Tests (1,200, 2,000, 5,000 nodes)
# =============================================================================

@pytest.mark.parametrize("node_count", [1200, 2000, 5000])
def test_detect_cycles_iterative_dfs_scale(engine: IntegrityEngine, node_count: int):
    """
    Empirical test: chain of 1,200, 2,000, and 5,000 nodes in depends_on closing a cycle.
    Python default recursion limit is 1000.
    Recursive DFS crashes with RecursionError at ~1000 depth.
    Iterative DFS must execute with 0 RecursionError and linear execution time.
    """
    adj = {f"n_{i:05d}": [f"n_{(i+1):05d}"] for i in range(node_count - 1)}
    adj[f"n_{(node_count - 1):05d}"] = ["n_00000"]

    start_time = time.perf_counter()
    cycles = engine._detect_cycles(adj)
    elapsed = time.perf_counter() - start_time

    assert len(cycles) == 1, f"Expected 1 cycle, detected {len(cycles)}"
    assert cycles[0][0] == "n_00000"
    assert len(cycles[0]) == node_count + 1
    assert elapsed < 1.0, f"Scale {node_count} took {elapsed:.4f}s (exceeded 1.0s limit)"


@pytest.mark.parametrize("node_count", [1200, 2000, 5000])
def test_detect_cycles_acyclic_scale(engine: IntegrityEngine, node_count: int):
    """
    Empirical test: acyclic chain of 1,200, 2,000, and 5,000 nodes.
    Iterative DFS must traverse all nodes without RecursionError, detect 0 cycles,
    and finish in < 0.5s.
    """
    adj = {f"n_{i:05d}": [f"n_{(i+1):05d}"] for i in range(node_count - 1)}
    adj[f"n_{(node_count - 1):05d}"] = []

    start_time = time.perf_counter()
    cycles = engine._detect_cycles(adj)
    elapsed = time.perf_counter() - start_time

    assert len(cycles) == 0
    assert elapsed < 0.5, f"Acyclic scale {node_count} took {elapsed:.4f}s"


@pytest.mark.parametrize("node_count", [1200, 2000, 5000])
def test_validate_document_large_graph_scale(
    make_rich_v3_doc: Callable[[], Dict[str, Any]],
    engine: IntegrityEngine,
    node_count: int,
):
    """
    End-to-end empirical test: full ParallelDoc 3.0 document containing 1,200, 2,000, and 5,000 nodes.
    Validates Draft 2020-12 schema, ID uniqueness, referential integrity, and depends_on cycle detection.
    Confirms 0 RecursionError, cycle tolerance (is_valid=True), and linear scaling.
    """
    doc = make_rich_v3_doc()

    nodes = [
        {"id": f"n-{i:05d}", "label": f"Node {i}", "unit_refs": ["u-src"]}
        for i in range(node_count)
    ]

    edges = [
        {
            "id": f"e-{i:05d}",
            "from": f"n-{i:05d}",
            "to": f"n-{(i + 1):05d}",
            "relation": "depends_on",
            "label": f"Dep {i}",
            "unit_refs": ["u-src"],
        }
        for i in range(node_count - 1)
    ]
    edges.append({
        "id": f"e-close-{node_count}",
        "from": f"n-{(node_count - 1):05d}",
        "to": "n-00000",
        "relation": "depends_on",
        "label": "Cycle closer",
        "unit_refs": ["u-src"],
    })

    doc["visuals"][0]["nodes"] = nodes
    doc["visuals"][0]["edges"] = edges

    start_time = time.perf_counter()
    report = engine.validate_document(doc)
    elapsed = time.perf_counter() - start_time

    assert report.is_valid, f"Expected valid doc with tolerated cycle, got errors: {report.issues}"
    assert report.structure_state == "valid"

    cycle_issues = [i for i in report.issues if i.code == "INFO_CYCLE_DETECTED"]
    assert len(cycle_issues) >= 1
    assert elapsed < 5.0, f"End-to-end validation for {node_count} nodes took {elapsed:.3f}s"


def test_dfs_linear_complexity_scaling(engine: IntegrityEngine):
    """
    Empirical linearity check: ratio of execution time between 1,200, 2,000, and 5,000 nodes.
    Linear complexity O(V+E) implies:
      time(2000) / time(1200) ≈ 1.67
      time(5000) / time(2000) ≈ 2.5
    Assert that scaling factor does not exhibit superlinear (e.g. O(N^2)) blowup.
    """
    timings = {}
    for n in [1200, 2000, 5000]:
        adj = {f"n_{i:05d}": [f"n_{(i+1):05d}"] for i in range(n - 1)}
        adj[f"n_{(n - 1):05d}"] = ["n_00000"]

        # Warmup
        engine._detect_cycles(adj)

        # Average over 3 runs
        runs = []
        for _ in range(3):
            t0 = time.perf_counter()
            engine._detect_cycles(adj)
            runs.append(time.perf_counter() - t0)
        timings[n] = min(runs)

    ratio_5000_2000 = timings[5000] / max(timings[2000], 1e-9)

    assert timings[5000] < 0.05, f"5,000 nodes DFS took {timings[5000]:.4f}s"
    assert ratio_5000_2000 < 5.0, f"Superlinear scaling observed: ratio {ratio_5000_2000:.2f}x"


# =============================================================================
# OBJECTIVE 2: Torture Pointer Tests (JSON null & Primitives across Collections & Pointers)
# =============================================================================

PRIMITIVE_VALUES = [
    None,            # JSON null
    123,             # int primitive
    "scalar-string", # str primitive
    True,            # bool primitive
    3.14,            # float primitive
]


@pytest.mark.parametrize("coll_name", ["authors", "units", "groups", "visuals", "assets", "profiles"])
@pytest.mark.parametrize("bad_val", PRIMITIVE_VALUES)
def test_torture_top_level_collections_resilience(
    make_rich_v3_doc: Callable[[], Dict[str, Any]],
    engine: IntegrityEngine,
    coll_name: str,
    bad_val: Any,
):
    """
    Adversarial torture: inject null and primitives into top-level collections.
    Validator MUST NOT crash with TypeError, AttributeError, or KeyError.
    Must return report with is_valid=False and structure_state='invalid'.
    """
    doc = make_rich_v3_doc()
    doc[coll_name] = bad_val

    try:
        report = engine.validate_document(doc)
    except Exception as exc:
        pytest.fail(f"Unhandled exception on doc[{coll_name}] = {bad_val!r}: {type(exc).__name__}: {exc}")

    assert report is not None
    assert isinstance(report.issues, list)
    assert not report.is_valid, f"Expected doc to be invalid when {coll_name}={bad_val!r}"
    assert report.structure_state == "invalid"


@pytest.mark.parametrize("ptr_field", ["author_refs", "default_profile_id"])
@pytest.mark.parametrize("bad_val", PRIMITIVE_VALUES)
def test_torture_metadata_pointers_resilience(
    make_rich_v3_doc: Callable[[], Dict[str, Any]],
    engine: IntegrityEngine,
    ptr_field: str,
    bad_val: Any,
):
    """
    Adversarial torture: inject null and primitives into metadata pointer fields.
    Validator must handle gracefully with 0 crashes.
    """
    doc = make_rich_v3_doc()
    doc["metadata"][ptr_field] = bad_val

    try:
        report = engine.validate_document(doc)
    except Exception as exc:
        pytest.fail(f"Unhandled exception on metadata.{ptr_field} = {bad_val!r}: {type(exc).__name__}: {exc}")

    assert report is not None
    assert not report.is_valid or ptr_field == "default_profile_id"


@pytest.mark.parametrize("unit_field", ["author_refs", "asset_ids", "source_refs"])
@pytest.mark.parametrize("bad_val", PRIMITIVE_VALUES)
def test_torture_unit_pointer_fields_resilience(
    make_rich_v3_doc: Callable[[], Dict[str, Any]],
    engine: IntegrityEngine,
    unit_field: str,
    bad_val: Any,
):
    """
    Adversarial torture: inject null and primitives into unit pointer fields.
    Must never crash with TypeError: 'NoneType' object is not iterable.
    """
    doc = make_rich_v3_doc()
    doc["units"][0][unit_field] = bad_val

    try:
        report = engine.validate_document(doc)
    except Exception as exc:
        pytest.fail(f"Unhandled exception on unit[0].{unit_field} = {bad_val!r}: {type(exc).__name__}: {exc}")

    assert report is not None
    assert not report.is_valid


@pytest.mark.parametrize("visual_field", ["author_refs", "owner_unit_id", "nodes", "edges"])
@pytest.mark.parametrize("bad_val", PRIMITIVE_VALUES)
def test_torture_visual_pointer_fields_resilience(
    make_rich_v3_doc: Callable[[], Dict[str, Any]],
    engine: IntegrityEngine,
    visual_field: str,
    bad_val: Any,
):
    """
    Adversarial torture: inject null and primitives into visual elements and pointers.
    Must never crash with TypeError.
    """
    doc = make_rich_v3_doc()
    doc["visuals"][0][visual_field] = bad_val

    try:
        report = engine.validate_document(doc)
    except Exception as exc:
        pytest.fail(f"Unhandled exception on visuals[0].{visual_field} = {bad_val!r}: {type(exc).__name__}: {exc}")

    assert report is not None
    assert not report.is_valid


@pytest.mark.parametrize("node_field", ["id", "label", "unit_refs"])
@pytest.mark.parametrize("bad_val", PRIMITIVE_VALUES)
def test_torture_visual_node_fields_resilience(
    make_rich_v3_doc: Callable[[], Dict[str, Any]],
    engine: IntegrityEngine,
    node_field: str,
    bad_val: Any,
):
    """
    Adversarial torture: inject null and primitives into node fields.
    Must handle gracefully without crash.
    """
    doc = make_rich_v3_doc()
    doc["visuals"][0]["nodes"][0][node_field] = bad_val

    try:
        report = engine.validate_document(doc)
    except Exception as exc:
        pytest.fail(f"Unhandled exception on node[0].{node_field} = {bad_val!r}: {type(exc).__name__}: {exc}")

    assert report is not None


@pytest.mark.parametrize("edge_field", ["id", "from", "to", "relation", "unit_refs"])
@pytest.mark.parametrize("bad_val", PRIMITIVE_VALUES)
def test_torture_visual_edge_fields_resilience(
    make_rich_v3_doc: Callable[[], Dict[str, Any]],
    engine: IntegrityEngine,
    edge_field: str,
    bad_val: Any,
):
    """
    Adversarial torture: inject null and primitives into edge fields.
    Must handle gracefully without crash.
    """
    doc = make_rich_v3_doc()
    doc["visuals"][0]["edges"][0][edge_field] = bad_val

    try:
        report = engine.validate_document(doc)
    except Exception as exc:
        pytest.fail(f"Unhandled exception on edge[0].{edge_field} = {bad_val!r}: {type(exc).__name__}: {exc}")

    assert report is not None


@pytest.mark.parametrize("group_field", ["id", "title", "unit_refs"])
@pytest.mark.parametrize("bad_val", PRIMITIVE_VALUES)
def test_torture_group_fields_resilience(
    make_rich_v3_doc: Callable[[], Dict[str, Any]],
    engine: IntegrityEngine,
    group_field: str,
    bad_val: Any,
):
    """
    Adversarial torture: inject null and primitives into group fields.
    Must handle gracefully without crash.
    """
    doc = make_rich_v3_doc()
    doc["groups"][0][group_field] = bad_val

    try:
        report = engine.validate_document(doc)
    except Exception as exc:
        pytest.fail(f"Unhandled exception on group[0].{group_field} = {bad_val!r}: {type(exc).__name__}: {exc}")

    assert report is not None


@pytest.mark.parametrize("asset_field", ["id", "author_refs", "alt", "caption"])
@pytest.mark.parametrize("bad_val", PRIMITIVE_VALUES)
def test_torture_asset_fields_resilience(
    make_rich_v3_doc: Callable[[], Dict[str, Any]],
    engine: IntegrityEngine,
    asset_field: str,
    bad_val: Any,
):
    """
    Adversarial torture: inject null and primitives into asset fields.
    Must handle gracefully without crash.
    """
    doc = make_rich_v3_doc()
    doc["assets"][0][asset_field] = bad_val

    try:
        report = engine.validate_document(doc)
    except Exception as exc:
        pytest.fail(f"Unhandled exception on asset[0].{asset_field} = {bad_val!r}: {type(exc).__name__}: {exc}")

    assert report is not None


@pytest.mark.parametrize("profile_field", ["id", "title", "panels"])
@pytest.mark.parametrize("bad_val", PRIMITIVE_VALUES)
def test_torture_profile_fields_resilience(
    make_rich_v3_doc: Callable[[], Dict[str, Any]],
    engine: IntegrityEngine,
    profile_field: str,
    bad_val: Any,
):
    """
    Adversarial torture: inject null and primitives into profile fields.
    Must handle gracefully without crash.
    """
    doc = make_rich_v3_doc()
    doc["profiles"][0][profile_field] = bad_val

    try:
        report = engine.validate_document(doc)
    except Exception as exc:
        pytest.fail(f"Unhandled exception on profile[0].{profile_field} = {bad_val!r}: {type(exc).__name__}: {exc}")

    assert report is not None


# Bug Demonstration: Unhashable types (list, dict) in edge.from and edge.to
@pytest.mark.parametrize("edge_field", ["from", "to"])
@pytest.mark.parametrize("unhashable_val", [["node_id_in_list"], {"id": "node_id_in_dict"}])
@pytest.mark.xfail(
    reason="BUG: src/validator.py lines 770 and 779 lack isinstance(..., str) guard before 'not in v_nodes' lookup",
    strict=True
)
def test_unhashable_edge_pointers_bug_demonstration(
    make_rich_v3_doc: Callable[[], Dict[str, Any]],
    engine: IntegrityEngine,
    edge_field: str,
    unhashable_val: Any,
):
    """
    Demonstrates that injecting unhashable compound structures (lists, dicts) into edge.from
    or edge.to triggers an unhandled TypeError: unhashable type.
    Marked xfail (strict=True) to track the defect until patched.
    """
    doc = make_rich_v3_doc()
    doc["visuals"][0]["edges"][0][edge_field] = unhashable_val
    # This will raise TypeError until validator.py adds `isinstance(e_from, str)` guard
    report = engine.validate_document(doc)
    assert not report.is_valid


# =============================================================================
# OBJECTIVE 3: Adversarial Suite Completeness Verification
# =============================================================================

def test_adversarial_stress_suite_passes_cleanly():
    """
    Verify that tests/test_adversarial_stress.py passes cleanly with 0 failures and 0 xfail.
    """
    import subprocess
    import sys
    
    cmd = [sys.executable, "-m", "pytest", "tests/test_adversarial_stress.py", "-q"]
    res = subprocess.run(cmd, capture_output=True, text=True)
    assert res.returncode == 0, f"test_adversarial_stress.py failed:\n{res.stdout}\n{res.stderr}"
    assert "failed" not in res.stdout
    assert "xfail" not in res.stdout