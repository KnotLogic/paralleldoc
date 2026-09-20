"""
Suite 3: AC-08 Referential Integrity Tests for ParallelDoc 3.0.
Verifies cross-collection entity uniqueness, scoping, semantic kind rules,
topology constraints, cycle tolerance on depends_on, and orphan unit gathering under «Вне групп».
"""

from typing import Any, Callable, Dict, List
import pytest
from validator import IntegrityEngine, IssueSeverity, ValidationIssue


def find_issue(issues: List[ValidationIssue], code: str, path: str = None) -> ValidationIssue:
    """Helper to locate a specific issue by error code and optional pointer path."""
    for issue in issues:
        if issue.code == code:
            if path is None or issue.path == path:
                return issue
    return None


# -----------------------------------------------------------------------------
# Group 1: Entity ID Uniqueness (8 tests)
# -----------------------------------------------------------------------------


def test_duplicate_unit_id_rejected(make_minimal_v3_doc: Callable[[], Dict[str, Any]], engine: IntegrityEngine):
    doc = make_minimal_v3_doc()
    doc["units"] = [
        {
            "id": "u-01",
            "kind": "analysis",
            "title": "Unit 1",
            "text": "Text 1",
            "text_format": "plain",
            "author_refs": ["auth-01"],
            "epistemic": "hypothesis",
            "status": "draft",
            "source_refs": [],
            "asset_ids": [],
        },
        {
            "id": "u-01",
            "kind": "analysis",
            "title": "Unit 2 with duplicate ID",
            "text": "Text 2",
            "text_format": "plain",
            "author_refs": ["auth-01"],
            "epistemic": "hypothesis",
            "status": "draft",
            "source_refs": [],
            "asset_ids": [],
        },
    ]
    report = engine.validate_document(doc)
    issue = find_issue(report.issues, "ERR_DUPLICATE_ID", "/units/1/id")
    assert issue is not None, f"Expected ERR_DUPLICATE_ID at /units/1/id, got: {report.issues}"
    assert not report.is_valid


def test_duplicate_author_id_rejected(make_minimal_v3_doc: Callable[[], Dict[str, Any]], engine: IntegrityEngine):
    doc = make_minimal_v3_doc()
    doc["authors"] = [
        {"id": "auth-01", "kind": "human", "name": "Author 1"},
        {"id": "auth-01", "kind": "model", "name": "Author Duplicate"},
    ]
    report = engine.validate_document(doc)
    issue = find_issue(report.issues, "ERR_DUPLICATE_ID", "/authors/1/id")
    assert issue is not None, f"Expected duplicate author ID error, got: {report.issues}"


def test_duplicate_group_id_rejected(make_rich_v3_doc: Callable[[], Dict[str, Any]], engine: IntegrityEngine):
    doc = make_rich_v3_doc()
    doc["groups"].append(
        {
            "id": "g-01",
            "title": "Duplicate group ID",
            "unit_refs": ["u-src"],
        }
    )
    report = engine.validate_document(doc)
    issue = find_issue(report.issues, "ERR_DUPLICATE_ID", "/groups/1/id")
    assert issue is not None, f"Expected duplicate group ID error, got: {report.issues}"


def test_duplicate_visual_id_rejected(make_rich_v3_doc: Callable[[], Dict[str, Any]], engine: IntegrityEngine):
    doc = make_rich_v3_doc()
    dup_visual = dict(doc["visuals"][0])
    doc["visuals"].append(dup_visual)
    report = engine.validate_document(doc)
    issue = find_issue(report.issues, "ERR_DUPLICATE_ID", "/visuals/1/id")
    assert issue is not None, f"Expected duplicate visual ID error, got: {report.issues}"


def test_duplicate_asset_id_rejected(make_rich_v3_doc: Callable[[], Dict[str, Any]], engine: IntegrityEngine):
    doc = make_rich_v3_doc()
    dup_asset = dict(doc["assets"][0])
    doc["assets"].append(dup_asset)
    report = engine.validate_document(doc)
    issue = find_issue(report.issues, "ERR_DUPLICATE_ID", "/assets/1/id")
    assert issue is not None, f"Expected duplicate asset ID error, got: {report.issues}"


def test_cross_collection_id_collision(make_minimal_v3_doc: Callable[[], Dict[str, Any]], engine: IntegrityEngine):
    doc = make_minimal_v3_doc()
    # author has id "auth-01", give unit the same ID
    doc["units"] = [
        {
            "id": "auth-01",
            "kind": "analysis",
            "title": "Colliding ID unit",
            "text": "Text",
            "text_format": "plain",
            "author_refs": ["auth-01"],
            "epistemic": "hypothesis",
            "status": "draft",
            "source_refs": [],
            "asset_ids": [],
        }
    ]
    report = engine.validate_document(doc)
    issue = find_issue(report.issues, "ERR_CROSS_COLLECTION_ID_COLLISION", "/units/0/id")
    assert issue is not None, f"Expected ERR_CROSS_COLLECTION_ID_COLLISION, got: {report.issues}"


def test_visual_node_edge_id_collision(make_rich_v3_doc: Callable[[], Dict[str, Any]], engine: IntegrityEngine):
    doc = make_rich_v3_doc()
    # In visual 0, set edge id to match node id "n-01"
    doc["visuals"][0]["edges"][0]["id"] = "n-01"
    report = engine.validate_document(doc)
    issue = find_issue(report.issues, "ERR_VISUAL_ID_COLLISION", "/visuals/0/edges/0/id")
    assert issue is not None, f"Expected ERR_VISUAL_ID_COLLISION, got: {report.issues}"


def test_reserved_builtin_id_prefix_rejected(make_minimal_v3_doc: Callable[[], Dict[str, Any]], engine: IntegrityEngine):
    doc = make_minimal_v3_doc()
    doc["units"] = [
        {
            "id": "builtin:custom-unit",
            "kind": "analysis",
            "title": "Unit with reserved prefix",
            "text": "Text",
            "text_format": "plain",
            "author_refs": ["auth-01"],
            "epistemic": "hypothesis",
            "status": "draft",
            "source_refs": [],
            "asset_ids": [],
        }
    ]
    report = engine.validate_document(doc)
    issue = find_issue(report.issues, "ERR_RESERVED_BUILTIN_PREFIX", "/units/0/id")
    assert issue is not None, f"Expected ERR_RESERVED_BUILTIN_PREFIX, got: {report.issues}"


# -----------------------------------------------------------------------------
# Group 2: Reference Existence & Scoping (10 tests)
# -----------------------------------------------------------------------------


def test_dangling_author_in_metadata(make_minimal_v3_doc: Callable[[], Dict[str, Any]], engine: IntegrityEngine):
    doc = make_minimal_v3_doc()
    doc["metadata"]["author_refs"] = ["missing-author-id"]
    report = engine.validate_document(doc)
    issue = find_issue(report.issues, "ERR_DANGLING_AUTHOR_REF", "/metadata/author_refs/0")
    assert issue is not None, f"Expected ERR_DANGLING_AUTHOR_REF, got: {report.issues}"


def test_dangling_author_in_unit(make_rich_v3_doc: Callable[[], Dict[str, Any]], engine: IntegrityEngine):
    doc = make_rich_v3_doc()
    doc["units"][0]["author_refs"] = ["missing-author-id"]
    report = engine.validate_document(doc)
    issue = find_issue(report.issues, "ERR_DANGLING_AUTHOR_REF", "/units/0/author_refs/0")
    assert issue is not None, f"Expected ERR_DANGLING_AUTHOR_REF, got: {report.issues}"


def test_dangling_author_in_visual(make_rich_v3_doc: Callable[[], Dict[str, Any]], engine: IntegrityEngine):
    doc = make_rich_v3_doc()
    doc["visuals"][0]["author_refs"] = ["missing-author-id"]
    report = engine.validate_document(doc)
    issue = find_issue(report.issues, "ERR_DANGLING_AUTHOR_REF", "/visuals/0/author_refs/0")
    assert issue is not None, f"Expected ERR_DANGLING_AUTHOR_REF, got: {report.issues}"


def test_dangling_author_in_asset(make_rich_v3_doc: Callable[[], Dict[str, Any]], engine: IntegrityEngine):
    doc = make_rich_v3_doc()
    doc["assets"][0]["author_refs"] = ["missing-author-id"]
    report = engine.validate_document(doc)
    issue = find_issue(report.issues, "ERR_DANGLING_AUTHOR_REF", "/assets/0/author_refs/0")
    assert issue is not None, f"Expected ERR_DANGLING_AUTHOR_REF, got: {report.issues}"


def test_dangling_asset_in_unit(make_rich_v3_doc: Callable[[], Dict[str, Any]], engine: IntegrityEngine):
    doc = make_rich_v3_doc()
    doc["units"][3]["asset_ids"] = ["missing-asset-id"]
    report = engine.validate_document(doc)
    issue = find_issue(report.issues, "ERR_DANGLING_ASSET_REF", "/units/3/asset_ids/0")
    assert issue is not None, f"Expected ERR_DANGLING_ASSET_REF, got: {report.issues}"


def test_dangling_unit_in_group(make_rich_v3_doc: Callable[[], Dict[str, Any]], engine: IntegrityEngine):
    doc = make_rich_v3_doc()
    doc["groups"][0]["unit_refs"].append("missing-unit-id")
    report = engine.validate_document(doc)
    issue = find_issue(report.issues, "ERR_DANGLING_UNIT_REF", "/groups/0/unit_refs/4")
    assert issue is not None, f"Expected ERR_DANGLING_UNIT_REF, got: {report.issues}"


def test_dangling_unit_in_node(make_rich_v3_doc: Callable[[], Dict[str, Any]], engine: IntegrityEngine):
    doc = make_rich_v3_doc()
    doc["visuals"][0]["nodes"][0]["unit_refs"] = ["missing-unit-id"]
    report = engine.validate_document(doc)
    issue = find_issue(report.issues, "ERR_DANGLING_UNIT_REF", "/visuals/0/nodes/0/unit_refs/0")
    assert issue is not None, f"Expected ERR_DANGLING_UNIT_REF, got: {report.issues}"


def test_dangling_unit_in_edge(make_rich_v3_doc: Callable[[], Dict[str, Any]], engine: IntegrityEngine):
    doc = make_rich_v3_doc()
    doc["visuals"][0]["edges"][0]["unit_refs"] = ["missing-unit-id"]
    report = engine.validate_document(doc)
    issue = find_issue(report.issues, "ERR_DANGLING_UNIT_REF", "/visuals/0/edges/0/unit_refs/0")
    assert issue is not None, f"Expected ERR_DANGLING_UNIT_REF, got: {report.issues}"


def test_dangling_node_in_edge_from_or_to(make_rich_v3_doc: Callable[[], Dict[str, Any]], engine: IntegrityEngine):
    doc = make_rich_v3_doc()
    doc["visuals"][0]["edges"][0]["from"] = "missing-node-id"
    report = engine.validate_document(doc)
    issue = find_issue(report.issues, "ERR_DANGLING_NODE_REF", "/visuals/0/edges/0/from")
    assert issue is not None, f"Expected ERR_DANGLING_NODE_REF, got: {report.issues}"


def test_cross_visual_node_reference_rejected(make_rich_v3_doc: Callable[[], Dict[str, Any]], engine: IntegrityEngine):
    doc = make_rich_v3_doc()
    # Add a second visual whose edge points to node "n-01" from the first visual
    v2 = {
        "id": "v-02",
        "type": "relationship-graph",
        "title": "Second visual",
        "question": "Q",
        "fallback": "F",
        "owner_unit_id": "u-mod",
        "author_refs": ["auth-01"],
        "nodes": [
            {"id": "v2-n1", "label": "V2 Node 1", "unit_refs": ["u-src"]},
            {"id": "v2-n2", "label": "V2 Node 2", "unit_refs": ["u-ana"]},
        ],
        "edges": [
            {
                "id": "v2-e1",
                "from": "n-01",  # From visual 0!
                "to": "v2-n2",
                "relation": "supports",
                "label": "Cross visual edge",
                "unit_refs": ["u-src"],
            }
        ],
    }
    doc["visuals"].append(v2)
    report = engine.validate_document(doc)
    issue = find_issue(report.issues, "ERR_DANGLING_NODE_REF", "/visuals/1/edges/0/from")
    assert issue is not None, f"Expected ERR_DANGLING_NODE_REF for cross-visual edge, got: {report.issues}"


# -----------------------------------------------------------------------------
# Group 3: Semantic Kind Constraints (3 tests)
# -----------------------------------------------------------------------------


def test_visual_owner_unit_must_be_model_kind(make_rich_v3_doc: Callable[[], Dict[str, Any]], engine: IntegrityEngine):
    doc = make_rich_v3_doc()
    # u-ana is kind: "analysis"
    doc["visuals"][0]["owner_unit_id"] = "u-ana"
    report = engine.validate_document(doc)
    issue = find_issue(report.issues, "ERR_OWNER_UNIT_NON_MODEL_KIND", "/visuals/0/owner_unit_id")
    assert issue is not None, f"Expected ERR_OWNER_UNIT_NON_MODEL_KIND, got: {report.issues}"

    # Restore to model kind
    doc["visuals"][0]["owner_unit_id"] = "u-mod"
    report_valid = engine.validate_document(doc)
    assert find_issue(report_valid.issues, "ERR_OWNER_UNIT_NON_MODEL_KIND") is None


def test_unit_source_refs_must_be_source_kind(make_rich_v3_doc: Callable[[], Dict[str, Any]], engine: IntegrityEngine):
    doc = make_rich_v3_doc()
    # u-act is kind: "action", not "source"
    doc["units"][2]["source_refs"] = ["u-act"]
    report = engine.validate_document(doc)
    issue = find_issue(report.issues, "ERR_SOURCE_REF_NON_SOURCE_KIND", "/units/2/source_refs/0")
    assert issue is not None, f"Expected ERR_SOURCE_REF_NON_SOURCE_KIND, got: {report.issues}"

    # Target points to genuine source unit
    doc["units"][2]["source_refs"] = ["u-src"]
    report_valid = engine.validate_document(doc)
    assert find_issue(report_valid.issues, "ERR_SOURCE_REF_NON_SOURCE_KIND") is None


def test_supersedes_historical_id_non_strict(make_rich_v3_doc: Callable[[], Dict[str, Any]], engine: IntegrityEngine):
    doc = make_rich_v3_doc()
    doc["units"][0]["supersedes"] = ["historical-legacy-id-v2"]
    report = engine.validate_document(doc)
    assert report.is_valid
    assert find_issue(report.issues, "ERR_DANGLING_UNIT_REF") is None


# -----------------------------------------------------------------------------
# Group 4: Graph Topology & Cycle Tolerance (3 tests)
# -----------------------------------------------------------------------------


def test_self_loop_rejected(make_rich_v3_doc: Callable[[], Dict[str, Any]], engine: IntegrityEngine):
    doc = make_rich_v3_doc()
    doc["visuals"][0]["edges"][0]["from"] = "n-01"
    doc["visuals"][0]["edges"][0]["to"] = "n-01"
    report = engine.validate_document(doc)
    issue = find_issue(report.issues, "ERR_SELF_LOOP", "/visuals/0/edges/0")
    assert issue is not None, f"Expected ERR_SELF_LOOP, got: {report.issues}"
    assert not report.is_valid


def test_six_typed_relations_accepted(make_rich_v3_doc: Callable[[], Dict[str, Any]], engine: IntegrityEngine):
    doc = make_rich_v3_doc()
    # Build a visual with all 6 relation types
    nodes = [{"id": f"n-{i}", "label": f"Node {i}", "unit_refs": ["u-src"]} for i in range(7)]
    relations = ["supports", "qualifies", "contradicts", "depends_on", "precedes", "compares"]
    edges = [
        {
            "id": f"e-rel-{idx}",
            "from": f"n-{idx}",
            "to": f"n-{idx+1}",
            "relation": rel,
            "label": f"Relation {rel}",
            "unit_refs": ["u-src"],
        }
        for idx, rel in enumerate(relations)
    ]
    doc["visuals"][0]["nodes"] = nodes
    doc["visuals"][0]["edges"] = edges
    report = engine.validate_document(doc)
    assert report.is_valid, f"Expected document to be valid with 6 relation types, got: {report.issues}"


def test_directed_cycle_in_depends_on_tolerated(make_rich_v3_doc: Callable[[], Dict[str, Any]], engine: IntegrityEngine):
    doc = make_rich_v3_doc()
    # Node 1 depends_on Node 2, and Node 2 depends_on Node 1
    doc["visuals"][0]["edges"] = [
        {
            "id": "e-dep-1",
            "from": "n-01",
            "to": "n-02",
            "relation": "depends_on",
            "label": "Dep 1",
            "unit_refs": ["u-src"],
        },
        {
            "id": "e-dep-2",
            "from": "n-02",
            "to": "n-01",
            "relation": "depends_on",
            "label": "Dep 2",
            "unit_refs": ["u-src"],
        },
    ]
    report = engine.validate_document(doc)
    # Per Spec r2 §8, cycles in depends_on are permitted:
    assert report.is_valid, f"Cycle in depends_on should not fail validation: {report.issues}"
    cycle_issue = find_issue(report.issues, "INFO_CYCLE_DETECTED")
    assert cycle_issue is not None, "Expected INFO_CYCLE_DETECTED to be logged"
    assert cycle_issue.severity == IssueSeverity.INFO


# -----------------------------------------------------------------------------
# Group 5: Orphan Unit Reconciliation & Partial Status (4 tests)
# -----------------------------------------------------------------------------


def test_orphan_unit_reconciliation(make_rich_v3_doc: Callable[[], Dict[str, Any]], engine: IntegrityEngine):
    doc = make_rich_v3_doc()
    # Add a 5th unit not included in any group
    orphan_unit = {
        "id": "u-orphan",
        "kind": "action",
        "title": "Orphan Action Unit",
        "text": "Unassigned action item",
        "text_format": "plain",
        "author_refs": ["auth-01"],
        "epistemic": "not-applicable",
        "status": "draft",
        "source_refs": [],
        "asset_ids": [],
    }
    doc["units"].append(orphan_unit)

    report = engine.validate_document(doc)
    assert "u-orphan" in report.orphan_units
    assert report.document_status == "partial"
    assert report.structure_state == "partial"
    assert report.synthetic_orphan_group is not None
    assert report.synthetic_orphan_group["title"] == "Вне групп"
    assert "u-orphan" in report.synthetic_orphan_group["unit_refs"]
    assert find_issue(report.issues, "WARN_ORPHAN_UNITS") is not None


def test_zero_orphans_in_fully_grouped_doc(make_rich_v3_doc: Callable[[], Dict[str, Any]], engine: IntegrityEngine):
    doc = make_rich_v3_doc()
    report = engine.validate_document(doc)
    assert len(report.orphan_units) == 0
    assert report.document_status == "valid"
    assert report.structure_state == "valid"
    assert report.synthetic_orphan_group is None


def test_multi_grouped_unit_warning(make_rich_v3_doc: Callable[[], Dict[str, Any]], engine: IntegrityEngine):
    doc = make_rich_v3_doc()
    # Add a second group referencing unit u-src (already in g-01)
    doc["groups"].append(
        {
            "id": "g-02",
            "title": "Second Group",
            "unit_refs": ["u-src"],
        }
    )
    report = engine.validate_document(doc)
    issue = find_issue(report.issues, "WARN_MULTI_GROUPED_UNIT", "/groups/1/unit_refs/0")
    assert issue is not None, f"Expected WARN_MULTI_GROUPED_UNIT, got: {report.issues}"
    assert issue.severity == IssueSeverity.WARNING


def test_whitespace_only_text_rejected(make_minimal_v3_doc: Callable[[], Dict[str, Any]], engine: IntegrityEngine):
    doc = make_minimal_v3_doc()
    doc["units"] = [
        {
            "id": "u-spaces",
            "kind": "analysis",
            "title": "Valid title",
            "text": "    \t\n   ",  # Whitespace-only
            "text_format": "plain",
            "author_refs": ["auth-01"],
            "epistemic": "hypothesis",
            "status": "draft",
            "source_refs": [],
            "asset_ids": [],
        }
    ]
    report = engine.validate_document(doc)
    issue = find_issue(report.issues, "ERR_EMPTY_WHITESPACE_ONLY", "/units/0/text")
    assert issue is not None, f"Expected ERR_EMPTY_WHITESPACE_ONLY, got: {report.issues}"
    assert not report.is_valid


def test_duplicate_panel_id_in_profile_rejected(
    make_rich_v3_doc: Callable[[], Dict[str, Any]], engine: IntegrityEngine
):
    """Spec r2 §8 Rule 1: Panel IDs must be unique within a profile."""
    doc = make_rich_v3_doc()
    doc["profiles"][0]["panels"][1]["id"] = doc["profiles"][0]["panels"][0]["id"]
    report = engine.validate_document(doc)
    issue = find_issue(report.issues, "ERR_DUPLICATE_PANEL_ID", "/profiles/0/panels/1/id")
    assert issue is not None, f"Expected ERR_DUPLICATE_PANEL_ID, got: {report.issues}"
    assert not report.is_valid


def test_reserved_builtin_panel_id_rejected(
    make_rich_v3_doc: Callable[[], Dict[str, Any]], engine: IntegrityEngine
):
    """Spec r2 §8 Rule 6: User panel IDs with 'builtin:' prefix are forbidden."""
    doc = make_rich_v3_doc()
    doc["profiles"][0]["panels"][0]["id"] = "builtin:custom-panel"
    report = engine.validate_document(doc)
    issue = find_issue(report.issues, "ERR_RESERVED_BUILTIN_PREFIX", "/profiles/0/panels/0/id")
    assert issue is not None, f"Expected ERR_RESERVED_BUILTIN_PREFIX, got: {report.issues}"
    assert not report.is_valid


def test_distinct_profiles_can_share_panel_ids(
    make_rich_v3_doc: Callable[[], Dict[str, Any]], engine: IntegrityEngine
):
    """Spec r2 §8 Rule 1: Panel IDs are scoped within profile; two profiles can reuse panel IDs."""
    doc = make_rich_v3_doc()
    p2 = {
        "id": "prof-02",
        "title": "2-Panel Compare",
        "density": "dense",
        "panels": [
            {"id": "p-src", "title": "Sources & Model", "kinds": ["source", "model"], "weight": 50},
            {"id": "p-ana", "title": "Analysis & Action", "kinds": ["analysis", "action"], "weight": 50},
        ],
    }
    doc["profiles"].append(p2)
    report = engine.validate_document(doc)
    panel_id_issues = [i for i in report.issues if i.code in ("ERR_DUPLICATE_PANEL_ID", "ERR_DUPLICATE_ID")]
    assert len(panel_id_issues) == 0, f"Unexpected panel ID collision between distinct profiles: {panel_id_issues}"
    assert report.is_valid


@pytest.mark.parametrize(
    "entity,field_name,ptr",
    [
        ("metadata", "title", "/metadata/title"),
        ("group", "title", "/groups/0/title"),
        ("visual", "title", "/visuals/0/title"),
        ("visual", "question", "/visuals/0/question"),
        ("visual", "fallback", "/visuals/0/fallback"),
        ("asset", "alt", "/assets/0/alt"),
        ("asset", "caption", "/assets/0/caption"),
        ("profile", "title", "/profiles/0/title"),
        ("panel", "title", "/profiles/0/panels/0/title"),
    ],
)
def test_whitespace_only_required_text_fields_rejected(
    entity: str, field_name: str, ptr: str, make_rich_v3_doc: Callable[[], Dict[str, Any]], engine: IntegrityEngine
):
    """Spec r2 §8 Rule 5: Non-empty text/title/fallback/alt/caption/question after whitespace strip."""
    doc = make_rich_v3_doc()
    if entity == "metadata":
        doc["metadata"][field_name] = "   \t \n "
    elif entity == "group":
        doc["groups"][0][field_name] = "   "
    elif entity == "visual":
        doc["visuals"][0][field_name] = "   "
    elif entity == "asset":
        doc["assets"][0][field_name] = "   "
    elif entity == "profile":
        doc["profiles"][0][field_name] = "   "
    elif entity == "panel":
        doc["profiles"][0]["panels"][0][field_name] = "   "

    report = engine.validate_document(doc)
    issue = find_issue(report.issues, "ERR_EMPTY_WHITESPACE_ONLY", ptr)
    assert issue is not None, f"Expected ERR_EMPTY_WHITESPACE_ONLY at {ptr}, got: {report.issues}"
    assert not report.is_valid


def test_malformed_null_collections_graceful_handling(engine: IntegrityEngine):
    """Reviewer M1-2 Finding 1: None collections must return invalid report, never crash with TypeError."""
    bad_doc = {
        "format": "paralleldoc",
        "version": "3.0",
        "metadata": {"document_id": "d-1", "revision": "r-1", "title": "T", "author_refs": None},
        "authors": None,
        "units": None,
        "groups": None,
        "visuals": None,
        "assets": None,
        "profiles": None,
    }
    report = engine.validate_document(bad_doc)
    assert not report.is_valid
    assert report.structure_state == "invalid"

