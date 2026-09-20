"""
Suite 4: Adversarial Stress & Robustness Tests for ParallelDoc 3.0 (Milestone 1).
Author: Challenger M1-2
Evaluates:
  1. Large graph stress (500+ nodes, cycles, recursion limits, linearity)
  2. Exotic relation loops, self-loops, duplicate edges
  3. Dangling pointer torture (unit_refs, author_refs, asset bindings, visual references, corrupted types)
  4. Orphan unit boundary conditions (0% grouped vs 100% grouped, empty docs, multi-grouping)
"""

import copy
import sys
import time
from typing import Any, Callable, Dict, List
import pytest

from validator import (
    IntegrityEngine,
    IssueSeverity,
    ValidationIssue,
    validate_document,
)


def find_issues(issues: List[ValidationIssue], code: str) -> List[ValidationIssue]:
    """Helper to locate all issues by machine-readable error code."""
    return [i for i in issues if i.code == code]


def find_issue(issues: List[ValidationIssue], code: str, path: str = None) -> ValidationIssue:
    """Helper to locate a specific issue by error code and optional pointer path."""
    for issue in issues:
        if issue.code == code:
            if path is None or issue.path == path:
                return issue
    return None


# =============================================================================
# PART 1: Large Graph Stress & Cycle Tolerance (§3, §6, §8, AC-17, AC-44)
# =============================================================================


def test_large_graph_500_nodes_linear_time(make_rich_v3_doc: Callable[[], Dict[str, Any]], engine: IntegrityEngine):
    """
    Stress test with 500 nodes and multiple cyclic dependencies in depends_on.
    Verifies that validation and cycle detection run in linear time (< 2.0s).
    """
    doc = make_rich_v3_doc()
    node_count = 500

    # Build 500 nodes and a cyclic topology in depends_on
    nodes = [
        {"id": f"n-{i:04d}", "label": f"Node {i}", "unit_refs": ["u-src"]}
        for i in range(node_count)
    ]

    edges = []
    # Create chain of depends_on edges: n_0 -> n_1 -> ... -> n_499
    for i in range(node_count - 1):
        edges.append({
            "id": f"e-dep-{i:04d}",
            "from": f"n-{i:04d}",
            "to": f"n-{(i + 1):04d}",
            "relation": "depends_on",
            "label": f"Dep {i}",
            "unit_refs": ["u-src"],
        })

    # Add back-edges to introduce multiple nested cycles:
    # 1. Outer cycle: 499 -> 0
    edges.append({
        "id": "e-back-outer",
        "from": f"n-{(node_count - 1):04d}",
        "to": "n-0000",
        "relation": "depends_on",
        "label": "Outer loop",
        "unit_refs": ["u-src"],
    })

    # 2. Intermediate cycle: 250 -> 100
    edges.append({
        "id": "e-back-mid",
        "from": "n-0250",
        "to": "n-0100",
        "relation": "depends_on",
        "label": "Mid loop",
        "unit_refs": ["u-src"],
    })

    doc["visuals"][0]["nodes"] = nodes
    doc["visuals"][0]["edges"] = edges

    start_time = time.perf_counter()
    report = engine.validate_document(doc)
    elapsed = time.perf_counter() - start_time

    # Performance assertion: 500 nodes graph must validate in < 2.0 seconds
    assert elapsed < 2.0, f"500-node graph validation took too long: {elapsed:.3f}s"

    # Cycle tolerance: depends_on cycle is tolerated per spec §8 line 420
    assert report.is_valid, f"Expected valid document with tolerated depends_on cycle, got: {report.issues}"
    cycle_issues = find_issues(report.issues, "INFO_CYCLE_DETECTED")
    assert len(cycle_issues) >= 1, f"Expected at least one cycle detected, got {len(cycle_issues)}"


def test_graph_recursion_limit_chain_1200_nodes(engine: IntegrityEngine):
    """
    Adversarial challenge: Test whether cycle detection crashes on 1200 nodes in a chain.

    Standard Python recursion limit is 1000.
    A recursive implementation without iterative stack processing crashes with RecursionError.
    """
    node_count = 1200
    adj = {f"n_{i}": [f"n_{i+1}"] for i in range(node_count - 1)}
    adj[f"n_{node_count - 1}"] = ["n_0"]

    # Must survive without RecursionError
    cycles = engine._detect_cycles(adj)
    assert len(cycles) >= 1


def test_large_graph_dense_cycles_scalability(engine: IntegrityEngine):
    """
    Adversarial challenge: Dense DAG with cross-links.
    Ensure no exponential path explosion occurs during cycle detection.
    """
    node_count = 300
    adj: Dict[str, List[str]] = {f"n_{i}": [] for i in range(node_count)}
    # Add multiple forward edges per node and several cycle back-edges
    for i in range(node_count - 1):
        adj[f"n_{i}"].append(f"n_{i+1}")
        if i + 2 < node_count:
            adj[f"n_{i}"].append(f"n_{i+2}")
    # Add cycle back-edges
    adj["n_100"].append("n_50")
    adj["n_200"].append("n_150")
    adj["n_299"].append("n_0")

    start_time = time.perf_counter()
    cycles = engine._detect_cycles(adj)
    elapsed = time.perf_counter() - start_time

    assert elapsed < 1.0, f"Dense cycle detection exceeded 1.0s: {elapsed:.3f}s"
    assert len(cycles) >= 1


def test_cycle_tolerance_spec_compliance(make_rich_v3_doc: Callable[[], Dict[str, Any]], engine: IntegrityEngine):
    """
    Spec §8 line 420: 'циклы depends_on допускаются и показываются как цикл, не ломают layout'.
    Verify that INFO_CYCLE_DETECTED is emitted with cycle path, and structure_state remains valid.
    """
    doc = make_rich_v3_doc()
    doc["visuals"][0]["edges"] = [
        {"id": "e-1", "from": "n-01", "to": "n-02", "relation": "depends_on", "label": "L1", "unit_refs": ["u-src"]},
        {"id": "e-2", "from": "n-02", "to": "n-01", "relation": "depends_on", "label": "L2", "unit_refs": ["u-src"]},
    ]
    report = engine.validate_document(doc)
    assert report.is_valid
    assert report.structure_state == "valid"
    cycle_issue = find_issue(report.issues, "INFO_CYCLE_DETECTED")
    assert cycle_issue is not None
    assert cycle_issue.severity == IssueSeverity.INFO
    assert "cycle" in cycle_issue.context


# =============================================================================
# PART 2: Exotic Relation Loops, Self-Loops & Duplicate Edges (§3, §8)
# =============================================================================


@pytest.mark.parametrize("relation", [
    "supports", "qualifies", "contradicts", "depends_on", "precedes", "compares"
])
def test_self_loop_rejected_for_all_relation_types(
    make_rich_v3_doc: Callable[[], Dict[str, Any]],
    engine: IntegrityEngine,
    relation: str
):
    """Spec §8 line 420: 'Нет self-loop from=to'. Must be rejected for all 6 relation types."""
    doc = make_rich_v3_doc()
    doc["visuals"][0]["edges"][0]["from"] = "n-01"
    doc["visuals"][0]["edges"][0]["to"] = "n-01"
    doc["visuals"][0]["edges"][0]["relation"] = relation

    report = engine.validate_document(doc)
    issue = find_issue(report.issues, "ERR_SELF_LOOP", "/visuals/0/edges/0")
    assert issue is not None, f"Expected ERR_SELF_LOOP for relation '{relation}', got: {report.issues}"
    assert issue.severity == IssueSeverity.ERROR
    assert not report.is_valid


def test_duplicate_edge_id_rejected(
    make_rich_v3_doc: Callable[[], Dict[str, Any]],
    engine: IntegrityEngine
):
    """Spec §8 line 420: Node and edge IDs must be unique within visual."""
    doc = make_rich_v3_doc()
    dup_edge = dict(doc["visuals"][0]["edges"][0])
    doc["visuals"][0]["edges"].append(dup_edge)

    report = engine.validate_document(doc)
    issue = find_issue(report.issues, "ERR_VISUAL_ID_COLLISION", "/visuals/0/edges/1/id")
    assert issue is not None, f"Expected ERR_VISUAL_ID_COLLISION for duplicate edge ID, got: {report.issues}"
    assert not report.is_valid


def test_parallel_edges_different_ids(
    make_rich_v3_doc: Callable[[], Dict[str, Any]],
    engine: IntegrityEngine
):
    """
    Two edges with different IDs between the same endpoints and same relation.
    Multigraph check: verify whether parallel edges are tolerated or flagged.
    """
    doc = make_rich_v3_doc()
    parallel_edge = {
        "id": "e-02-parallel",
        "from": "n-01",
        "to": "n-02",
        "relation": "supports",
        "label": "Second support edge",
        "unit_refs": ["u-src"],
    }
    doc["visuals"][0]["edges"].append(parallel_edge)

    report = engine.validate_document(doc)
    # Multigraph with distinct edge IDs is structurally valid under Draft 2020-12
    assert report.is_valid, f"Expected valid multigraph with distinct edge IDs, got: {report.issues}"


@pytest.mark.parametrize("directed_rel", ["supports", "qualifies", "contradicts", "precedes"])
def test_exotic_2_cycle_in_directed_relations(
    make_rich_v3_doc: Callable[[], Dict[str, Any]],
    engine: IntegrityEngine,
    directed_rel: str
):
    """
    Test 2-cycle in directed relations other than depends_on.
    E.g. A precedes B and B precedes A (temporal paradox).
    Per Spec §8 line 420: only depends_on cycles are explicitly singled out as tolerated.
    Verify whether validator crashes or handles non-depends_on cycles.
    """
    doc = make_rich_v3_doc()
    doc["visuals"][0]["edges"] = [
        {
            "id": "e-rel-1",
            "from": "n-01",
            "to": "n-02",
            "relation": directed_rel,
            "label": f"Rel 1 {directed_rel}",
            "unit_refs": ["u-src"],
        },
        {
            "id": "e-rel-2",
            "from": "n-02",
            "to": "n-01",
            "relation": directed_rel,
            "label": f"Rel 2 {directed_rel}",
            "unit_refs": ["u-src"],
        },
    ]

    report = engine.validate_document(doc)
    # Validator should not crash
    assert report is not None
    # For non-depends_on relations, cycles are currently not collected in depends_on_adj
    cycle_issues = find_issues(report.issues, "INFO_CYCLE_DETECTED")
    assert len(cycle_issues) == 0, f"INFO_CYCLE_DETECTED should only apply to depends_on, got: {cycle_issues}"


def test_symmetric_compares_relation_both_directions(
    make_rich_v3_doc: Callable[[], Dict[str, Any]],
    engine: IntegrityEngine
):
    """Compares relation is symmetric per Spec §3. Validate pair of compares edges."""
    doc = make_rich_v3_doc()
    doc["visuals"][0]["edges"] = [
        {
            "id": "e-cmp-1",
            "from": "n-01",
            "to": "n-02",
            "relation": "compares",
            "label": "Compare A and B",
            "unit_refs": ["u-src"],
        },
        {
            "id": "e-cmp-2",
            "from": "n-02",
            "to": "n-01",
            "relation": "compares",
            "label": "Compare B and A",
            "unit_refs": ["u-src"],
        },
    ]
    report = engine.validate_document(doc)
    assert report.is_valid, f"Expected compares edges to be valid, got: {report.issues}"


def test_mixed_relation_cycle(
    make_rich_v3_doc: Callable[[], Dict[str, Any]],
    engine: IntegrityEngine
):
    """Mixed cycle: Node 1 supports Node 2, Node 2 qualifies Node 3, Node 3 contradicts Node 1."""
    doc = make_rich_v3_doc()
    doc["visuals"][0]["nodes"].append({"id": "n-03", "label": "Node 3", "unit_refs": ["u-src"]})
    doc["visuals"][0]["edges"] = [
        {"id": "e-1", "from": "n-01", "to": "n-02", "relation": "supports", "label": "S", "unit_refs": ["u-src"]},
        {"id": "e-2", "from": "n-02", "to": "n-03", "relation": "qualifies", "label": "Q", "unit_refs": ["u-src"]},
        {"id": "e-3", "from": "n-03", "to": "n-01", "relation": "contradicts", "label": "C", "unit_refs": ["u-src"]},
    ]
    report = engine.validate_document(doc)
    assert report.is_valid, f"Expected mixed cycle to validate cleanly, got: {report.issues}"


# =============================================================================
# PART 3: Dangling Pointer Torture (§8 AC-08)
# =============================================================================


def test_dangling_unit_ref_in_node(make_rich_v3_doc: Callable[[], Dict[str, Any]], engine: IntegrityEngine):
    """Corrupted unit_ref in visual node."""
    doc = make_rich_v3_doc()
    doc["visuals"][0]["nodes"][0]["unit_refs"] = ["non-existent-unit-xyz"]
    report = engine.validate_document(doc)
    issue = find_issue(report.issues, "ERR_DANGLING_UNIT_REF", "/visuals/0/nodes/0/unit_refs/0")
    assert issue is not None, f"Expected ERR_DANGLING_UNIT_REF, got: {report.issues}"
    assert not report.is_valid


def test_dangling_unit_ref_in_edge(make_rich_v3_doc: Callable[[], Dict[str, Any]], engine: IntegrityEngine):
    """Corrupted unit_ref in visual edge."""
    doc = make_rich_v3_doc()
    doc["visuals"][0]["edges"][0]["unit_refs"] = ["phantom-unit-ref"]
    report = engine.validate_document(doc)
    issue = find_issue(report.issues, "ERR_DANGLING_UNIT_REF", "/visuals/0/edges/0/unit_refs/0")
    assert issue is not None, f"Expected ERR_DANGLING_UNIT_REF, got: {report.issues}"
    assert not report.is_valid


def test_dangling_author_ref_in_metadata(make_rich_v3_doc: Callable[[], Dict[str, Any]], engine: IntegrityEngine):
    """Corrupted author_ref in metadata."""
    doc = make_rich_v3_doc()
    doc["metadata"]["author_refs"] = ["ghost-author"]
    report = engine.validate_document(doc)
    issue = find_issue(report.issues, "ERR_DANGLING_AUTHOR_REF", "/metadata/author_refs/0")
    assert issue is not None, f"Expected ERR_DANGLING_AUTHOR_REF, got: {report.issues}"
    assert not report.is_valid


def test_dangling_author_ref_in_unit(make_rich_v3_doc: Callable[[], Dict[str, Any]], engine: IntegrityEngine):
    """Corrupted author_ref in unit."""
    doc = make_rich_v3_doc()
    doc["units"][0]["author_refs"] = ["ghost-author-2"]
    report = engine.validate_document(doc)
    issue = find_issue(report.issues, "ERR_DANGLING_AUTHOR_REF", "/units/0/author_refs/0")
    assert issue is not None, f"Expected ERR_DANGLING_AUTHOR_REF, got: {report.issues}"
    assert not report.is_valid


def test_dangling_author_ref_in_visual(make_rich_v3_doc: Callable[[], Dict[str, Any]], engine: IntegrityEngine):
    """Corrupted author_ref in visual."""
    doc = make_rich_v3_doc()
    doc["visuals"][0]["author_refs"] = ["ghost-author-3"]
    report = engine.validate_document(doc)
    issue = find_issue(report.issues, "ERR_DANGLING_AUTHOR_REF", "/visuals/0/author_refs/0")
    assert issue is not None, f"Expected ERR_DANGLING_AUTHOR_REF, got: {report.issues}"
    assert not report.is_valid


def test_dangling_author_ref_in_asset(make_rich_v3_doc: Callable[[], Dict[str, Any]], engine: IntegrityEngine):
    """Corrupted author_ref in asset."""
    doc = make_rich_v3_doc()
    doc["assets"][0]["author_refs"] = ["ghost-author-4"]
    report = engine.validate_document(doc)
    issue = find_issue(report.issues, "ERR_DANGLING_AUTHOR_REF", "/assets/0/author_refs/0")
    assert issue is not None, f"Expected ERR_DANGLING_AUTHOR_REF, got: {report.issues}"
    assert not report.is_valid


def test_dangling_asset_binding_in_unit(make_rich_v3_doc: Callable[[], Dict[str, Any]], engine: IntegrityEngine):
    """Corrupted asset binding: unit references non-existent asset ID."""
    doc = make_rich_v3_doc()
    doc["units"][3]["asset_ids"] = ["missing-ast-99"]
    report = engine.validate_document(doc)
    issue = find_issue(report.issues, "ERR_DANGLING_ASSET_REF", "/units/3/asset_ids/0")
    assert issue is not None, f"Expected ERR_DANGLING_ASSET_REF, got: {report.issues}"
    assert not report.is_valid


def test_dangling_visual_owner_unit_id(make_rich_v3_doc: Callable[[], Dict[str, Any]], engine: IntegrityEngine):
    """Corrupted visual owner: owner_unit_id points to non-existent unit."""
    doc = make_rich_v3_doc()
    doc["visuals"][0]["owner_unit_id"] = "non-existent-owner"
    report = engine.validate_document(doc)
    issue = find_issue(report.issues, "ERR_DANGLING_UNIT_REF", "/visuals/0/owner_unit_id")
    assert issue is not None, f"Expected ERR_DANGLING_UNIT_REF, got: {report.issues}"
    assert not report.is_valid


def test_visual_owner_unit_wrong_semantic_kind(make_rich_v3_doc: Callable[[], Dict[str, Any]], engine: IntegrityEngine):
    """Spec §8 line 422: owner_unit_id must point to a unit of kind='model'."""
    doc = make_rich_v3_doc()
    # u-src is kind: 'source', not 'model'
    doc["visuals"][0]["owner_unit_id"] = "u-src"
    report = engine.validate_document(doc)
    issue = find_issue(report.issues, "ERR_OWNER_UNIT_NON_MODEL_KIND", "/visuals/0/owner_unit_id")
    assert issue is not None, f"Expected ERR_OWNER_UNIT_NON_MODEL_KIND, got: {report.issues}"
    assert not report.is_valid


def test_source_refs_wrong_semantic_kind(make_rich_v3_doc: Callable[[], Dict[str, Any]], engine: IntegrityEngine):
    """Spec §8 line 423: source_refs must point only to kind='source'."""
    doc = make_rich_v3_doc()
    # u-mod is kind: 'model', not 'source'
    doc["units"][2]["source_refs"] = ["u-mod"]
    report = engine.validate_document(doc)
    issue = find_issue(report.issues, "ERR_SOURCE_REF_NON_SOURCE_KIND", "/units/2/source_refs/0")
    assert issue is not None, f"Expected ERR_SOURCE_REF_NON_SOURCE_KIND, got: {report.issues}"
    assert not report.is_valid


def test_corrupted_pointer_types_none_resilience(
    make_rich_v3_doc: Callable[[], Dict[str, Any]],
    engine: IntegrityEngine
):
    """
    Adversarial torture: What if reference fields are None instead of lists?
    E.g. metadata.author_refs = None.
    The validator must return an error report, NEVER crash with an unhandled TypeError!
    """
    doc = make_rich_v3_doc()
    doc["metadata"]["author_refs"] = None

    report = engine.validate_document(doc)
    assert not report.is_valid
    assert report.structure_state == "invalid"


def test_corrupted_unit_refs_none_in_node_resilience(
    make_rich_v3_doc: Callable[[], Dict[str, Any]],
    engine: IntegrityEngine
):
    """
    Adversarial torture: node.unit_refs is None instead of list.
    Validator must not raise TypeError: 'NoneType' object is not iterable.
    """
    doc = make_rich_v3_doc()
    doc["visuals"][0]["nodes"][0]["unit_refs"] = None

    report = engine.validate_document(doc)
    assert not report.is_valid


def test_corrupted_group_unit_refs_none_resilience(
    make_rich_v3_doc: Callable[[], Dict[str, Any]],
    engine: IntegrityEngine
):
    """
    Adversarial torture: group.unit_refs is None instead of list.
    Validator must not raise TypeError: 'NoneType' object is not iterable.
    """
    doc = make_rich_v3_doc()
    doc["groups"][0]["unit_refs"] = None

    report = engine.validate_document(doc)
    assert not report.is_valid


# =============================================================================
# PART 4: Orphan Unit Boundary Testing (§8 line 421, AC-08)
# =============================================================================


def test_orphan_boundary_0_percent_grouped_all_orphan(
    make_rich_v3_doc: Callable[[], Dict[str, Any]],
    engine: IntegrityEngine
):
    """
    Boundary condition: 0% grouped units (all units are orphans).
    Groups collection is empty ([]).
    Spec §8 line 421: All orphan units must be reconciled into synthetic group «Вне групп».
    Status must be 'partial'.
    """
    doc = make_rich_v3_doc()
    doc["groups"] = []  # No groups at all!

    report = engine.validate_document(doc)

    # 4 units in doc, all 4 must be recognized as orphans
    assert len(report.orphan_units) == 4
    assert set(report.orphan_units) == {"u-src", "u-mod", "u-ana", "u-act"}
    assert report.structure_state == "partial"
    assert report.document_status == "partial"

    # Synthetic orphan group must be formed
    synth_group = report.synthetic_orphan_group
    assert synth_group is not None
    assert synth_group["id"] == "builtin:orphan-group"
    assert synth_group["title"] == "Вне групп"
    assert set(synth_group["unit_refs"]) == {"u-src", "u-mod", "u-ana", "u-act"}
    assert synth_group.get("synthetic") is True

    # Reconciled groups list must contain exactly the synthetic orphan group
    assert len(report.reconciled_groups) == 1
    assert report.reconciled_groups[0]["id"] == "builtin:orphan-group"

    # Warning must be emitted
    warn_issue = find_issue(report.issues, "WARN_ORPHAN_UNITS")
    assert warn_issue is not None
    assert warn_issue.severity == IssueSeverity.WARNING


def test_orphan_boundary_100_percent_grouped(
    make_rich_v3_doc: Callable[[], Dict[str, Any]],
    engine: IntegrityEngine
):
    """
    Boundary condition: 100% grouped units (0 orphans).
    All units are assigned to groups with no leftovers.
    """
    doc = make_rich_v3_doc()
    # In make_rich_v3_doc, g-01 already includes all 4 units: ["u-src", "u-mod", "u-ana", "u-act"]

    report = engine.validate_document(doc)

    assert len(report.orphan_units) == 0
    assert report.synthetic_orphan_group is None
    assert report.structure_state == "valid"
    assert report.document_status == "valid"
    assert report.is_valid
    assert find_issue(report.issues, "WARN_ORPHAN_UNITS") is None


def test_orphan_boundary_empty_document(
    make_minimal_v3_doc: Callable[[], Dict[str, Any]],
    engine: IntegrityEngine
):
    """Boundary condition: Document with 0 units and 0 groups."""
    doc = make_minimal_v3_doc()
    doc["units"] = []
    doc["groups"] = []

    report = engine.validate_document(doc)

    assert len(report.orphan_units) == 0
    assert report.synthetic_orphan_group is None
    assert report.structure_state == "valid"
    assert report.document_status == "valid"
    assert report.is_valid


def test_orphan_boundary_partially_grouped(
    make_rich_v3_doc: Callable[[], Dict[str, Any]],
    engine: IntegrityEngine
):
    """Boundary condition: 1 of 4 units grouped (75% orphan)."""
    doc = make_rich_v3_doc()
    doc["groups"][0]["unit_refs"] = ["u-src"]

    report = engine.validate_document(doc)

    assert len(report.orphan_units) == 3
    assert set(report.orphan_units) == {"u-mod", "u-ana", "u-act"}
    assert report.structure_state == "partial"
    assert report.synthetic_orphan_group is not None
    assert set(report.synthetic_orphan_group["unit_refs"]) == {"u-mod", "u-ana", "u-act"}


def test_orphan_boundary_multi_group_overlap(
    make_rich_v3_doc: Callable[[], Dict[str, Any]],
    engine: IntegrityEngine
):
    """
    Spec §8 line 421: 'Каждая unit входит ровно в одну group'.
    If a unit is in multiple groups, a warning is raised and status is 'partial'.
    """
    doc = make_rich_v3_doc()
    # Add second group that also references u-src
    doc["groups"].append({
        "id": "g-02-overlap",
        "title": "Overlapping Group",
        "unit_refs": ["u-src"],
    })

    report = engine.validate_document(doc)

    assert len(report.orphan_units) == 0
    assert report.structure_state == "partial"
    overlap_issue = find_issue(report.issues, "WARN_MULTI_GROUPED_UNIT")
    assert overlap_issue is not None
    assert overlap_issue.severity == IssueSeverity.WARNING
