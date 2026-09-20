"""
Suite 2: AC-07 Structural Schema Validation for ParallelDoc 3.0 documents and manifests.
Verifies all Draft 2020-12 constraints and exact RFC 6901 JSON Pointer diagnostics.
"""

from typing import Any, Callable, Dict, List
import pytest
from jsonschema import Draft202012Validator
from validator import to_json_pointer


def assert_has_error(
    errors: List[Any],
    expected_pointer: str,
    expected_validator: str,
):
    """Assert that at least one validation error matches the RFC 6901 pointer and validator."""
    assert len(errors) > 0, f"Expected validation error at '{expected_pointer}', but 0 errors returned."
    matched = False
    details = []
    for err in errors:
        ptr = to_json_pointer(err.absolute_path)
        v = err.validator
        details.append(f"({ptr}, validator={v})")
        if ptr == expected_pointer and v == expected_validator:
            matched = True
            break
    assert matched, (
        f"Could not find error matching pointer '{expected_pointer}' with validator '{expected_validator}'. "
        f"Found errors: {details}"
    )


# -----------------------------------------------------------------------------
# Group A: Positive Tests (Valid Inputs) — 8 tests
# -----------------------------------------------------------------------------


def test_valid_minimal_document(make_minimal_v3_doc: Callable[[], Dict[str, Any]], v3_validator: Draft202012Validator):
    doc = make_minimal_v3_doc()
    errors = list(v3_validator.iter_errors(doc))
    assert len(errors) == 0, f"Minimal doc failed schema validation: {errors}"


def test_valid_rich_document(make_rich_v3_doc: Callable[[], Dict[str, Any]], v3_validator: Draft202012Validator):
    doc = make_rich_v3_doc()
    errors = list(v3_validator.iter_errors(doc))
    assert len(errors) == 0, f"Rich doc failed schema validation: {errors}"


def test_valid_optional_metadata(make_minimal_v3_doc: Callable[[], Dict[str, Any]], v3_validator: Draft202012Validator):
    doc = make_minimal_v3_doc()
    doc["metadata"]["created_at"] = "2026-09-06T17:00:00Z"
    doc["metadata"]["language"] = "ru"
    doc["metadata"]["default_profile_id"] = "builtin:3"
    errors = list(v3_validator.iter_errors(doc))
    assert len(errors) == 0


def test_valid_text_formats(make_minimal_v3_doc: Callable[[], Dict[str, Any]], v3_validator: Draft202012Validator):
    doc = make_minimal_v3_doc()
    doc["units"] = [
        {
            "id": "u-plain",
            "kind": "analysis",
            "title": "Plain Text Unit",
            "text": "Regular text line.",
            "text_format": "plain",
            "author_refs": ["auth-01"],
            "epistemic": "hypothesis",
            "status": "draft",
            "source_refs": [],
            "asset_ids": [],
        },
        {
            "id": "u-md",
            "kind": "action",
            "title": "Markdown Unit",
            "text": "This is **bold** and `code`.",
            "text_format": "markdown-safe",
            "author_refs": ["auth-01"],
            "epistemic": "not-applicable",
            "status": "draft",
            "source_refs": [],
            "asset_ids": [],
        },
    ]
    errors = list(v3_validator.iter_errors(doc))
    assert len(errors) == 0


def test_valid_epistemic_and_status_values(
    make_minimal_v3_doc: Callable[[], Dict[str, Any]], v3_validator: Draft202012Validator
):
    doc = make_minimal_v3_doc()
    epistemic_statuses = [
        ("reported", "draft", []),
        ("supported", "reviewed", ["u-src"]),
        ("hypothesis", "blocked", []),
        ("unknown", "done", []),
        ("not-applicable", "draft", []),
    ]
    doc["units"] = [
        {
            "id": "u-src",
            "kind": "source",
            "title": "Source unit",
            "text": "Spec quote",
            "text_format": "plain",
            "author_refs": ["auth-01"],
            "epistemic": "reported",
            "status": "reviewed",
            "source_refs": [],
            "asset_ids": [],
            "provenance": {"label": "Direct source"},
        }
    ]
    for idx, (epistemic, status, sources) in enumerate(epistemic_statuses):
        doc["units"].append(
            {
                "id": f"u-test-{idx}",
                "kind": "analysis",
                "title": f"Unit {idx}",
                "text": f"Content {idx}",
                "text_format": "plain",
                "author_refs": ["auth-01"],
                "epistemic": epistemic,
                "status": status,
                "source_refs": sources,
                "asset_ids": [],
            }
        )
    errors = list(v3_validator.iter_errors(doc))
    assert len(errors) == 0


def test_valid_asset_locator_modes(
    make_minimal_v3_doc: Callable[[], Dict[str, Any]], v3_validator: Draft202012Validator
):
    doc = make_minimal_v3_doc()
    doc["assets"] = [
        {
            "id": "a-embedded",
            "mime": "image/png",
            "sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
            "byte_length": 100,
            "width": 10,
            "height": 10,
            "alt": "Embedded image",
            "caption": "Embedded caption",
            "author_refs": ["auth-01"],
            "provenance": {"label": "Provenance embedded"},
            "locator": {
                "mode": "embedded",
                "data_uri": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==",
            },
        },
        {
            "id": "a-relative",
            "mime": "image/jpeg",
            "sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
            "byte_length": 200,
            "width": 20,
            "height": 20,
            "alt": "Relative image",
            "caption": "Relative caption",
            "author_refs": ["auth-01"],
            "provenance": {"label": "Provenance relative"},
            "locator": {
                "mode": "relative",
                "path": "assets/diagram.jpeg",
            },
        },
        {
            "id": "a-external",
            "mime": "image/webp",
            "sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
            "byte_length": 300,
            "width": 30,
            "height": 30,
            "alt": "External image",
            "caption": "External caption",
            "author_refs": ["auth-01"],
            "provenance": {"label": "Provenance external"},
            "locator": {
                "mode": "external",
                "url": "https://example.com/images/spec.webp",
            },
        },
    ]
    errors = list(v3_validator.iter_errors(doc))
    assert len(errors) == 0


def test_valid_namespaced_extensions(
    make_minimal_v3_doc: Callable[[], Dict[str, Any]], v3_validator: Draft202012Validator
):
    doc = make_minimal_v3_doc()
    doc["extensions"] = {
        "acme.corp/metric": {"sla_tier": "gold", "compliance_score": 99.95},
        "vendor.org/export-id": "V-12345",
    }
    errors = list(v3_validator.iter_errors(doc))
    assert len(errors) == 0


def test_valid_manifest_fixtures(manifest_validator: Draft202012Validator):
    manifest_min = {
        "format": "paralleldoc-integrity-1",
        "algorithm": "SHA-256",
        "scope": "raw-bytes",
        "expected_sha256": "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad",
    }
    assert len(list(manifest_validator.iter_errors(manifest_min))) == 0

    manifest_full = {
        "format": "paralleldoc-integrity-1",
        "algorithm": "SHA-256",
        "scope": "raw-bytes",
        "expected_sha256": "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad",
        "document_id": "doc-min-01",
        "revision": "rev-1",
    }
    assert len(list(manifest_validator.iter_errors(manifest_full))) == 0


# -----------------------------------------------------------------------------
# Group B: Root Structural Violations (Negative Tests) — 5 tests
# -----------------------------------------------------------------------------


@pytest.mark.parametrize(
    "prop",
    ["format", "version", "metadata", "authors", "units", "groups", "visuals", "assets", "profiles"],
)
def test_reject_missing_required_root_property(
    prop: str, make_minimal_v3_doc: Callable[[], Dict[str, Any]], v3_validator: Draft202012Validator
):
    doc = make_minimal_v3_doc()
    del doc[prop]
    errors = list(v3_validator.iter_errors(doc))
    assert_has_error(errors, expected_pointer="", expected_validator="required")


def test_reject_invalid_format_string(
    make_minimal_v3_doc: Callable[[], Dict[str, Any]], v3_validator: Draft202012Validator
):
    doc = make_minimal_v3_doc()
    doc["format"] = "paralleldoc-legacy"
    errors = list(v3_validator.iter_errors(doc))
    assert_has_error(errors, expected_pointer="/format", expected_validator="const")


def test_reject_invalid_version_string(
    make_minimal_v3_doc: Callable[[], Dict[str, Any]], v3_validator: Draft202012Validator
):
    doc = make_minimal_v3_doc()
    doc["version"] = "2.1"
    errors = list(v3_validator.iter_errors(doc))
    assert_has_error(errors, expected_pointer="/version", expected_validator="const")


def test_reject_legacy_top_level_keys(
    make_minimal_v3_doc: Callable[[], Dict[str, Any]], v3_validator: Draft202012Validator
):
    doc = make_minimal_v3_doc()
    doc["columns"] = []
    errors = list(v3_validator.iter_errors(doc))
    assert_has_error(errors, expected_pointer="", expected_validator="additionalProperties")


def test_reject_empty_authors_array(
    make_minimal_v3_doc: Callable[[], Dict[str, Any]], v3_validator: Draft202012Validator
):
    doc = make_minimal_v3_doc()
    doc["authors"] = []
    errors = list(v3_validator.iter_errors(doc))
    assert_has_error(errors, expected_pointer="/authors", expected_validator="minItems")


# -----------------------------------------------------------------------------
# Group C: Metadata & Author Violations — 5 tests
# -----------------------------------------------------------------------------


@pytest.mark.parametrize("meta_prop", ["document_id", "revision", "title", "author_refs"])
def test_reject_missing_metadata_fields(
    meta_prop: str, make_minimal_v3_doc: Callable[[], Dict[str, Any]], v3_validator: Draft202012Validator
):
    doc = make_minimal_v3_doc()
    del doc["metadata"][meta_prop]
    errors = list(v3_validator.iter_errors(doc))
    assert_has_error(errors, expected_pointer="/metadata", expected_validator="required")


def test_reject_empty_metadata_author_refs(
    make_minimal_v3_doc: Callable[[], Dict[str, Any]], v3_validator: Draft202012Validator
):
    doc = make_minimal_v3_doc()
    doc["metadata"]["author_refs"] = []
    errors = list(v3_validator.iter_errors(doc))
    assert_has_error(errors, expected_pointer="/metadata/author_refs", expected_validator="minItems")


@pytest.mark.parametrize(
    "invalid_dt",
    [
        "invalid-datetime-string",
        "2026-09-06T17:00:00",       # Missing timezone offset (naive)
        "2026-09-06",                # Date only
        "2026-09-06 17:00:00Z",      # Space instead of T
        "2026-09-06T17:00:00+03",    # Incomplete offset
        "2026-02-30T10:00:00Z",      # Non-existent calendar day
    ],
)
def test_reject_invalid_date_time_format(
    invalid_dt: str, make_minimal_v3_doc: Callable[[], Dict[str, Any]], v3_validator: Draft202012Validator
):
    doc = make_minimal_v3_doc()
    doc["metadata"]["created_at"] = invalid_dt
    errors = list(v3_validator.iter_errors(doc))
    assert_has_error(errors, expected_pointer="/metadata/created_at", expected_validator="format")



def test_reject_metadata_additional_properties(
    make_minimal_v3_doc: Callable[[], Dict[str, Any]], v3_validator: Draft202012Validator
):
    doc = make_minimal_v3_doc()
    doc["metadata"]["forbidden_extra"] = True
    errors = list(v3_validator.iter_errors(doc))
    assert_has_error(errors, expected_pointer="/metadata", expected_validator="additionalProperties")


def test_reject_author_invalid_kind(
    make_minimal_v3_doc: Callable[[], Dict[str, Any]], v3_validator: Draft202012Validator
):
    doc = make_minimal_v3_doc()
    doc["authors"][0]["kind"] = "cyborg"
    errors = list(v3_validator.iter_errors(doc))
    assert_has_error(errors, expected_pointer="/authors/0/kind", expected_validator="enum")


# -----------------------------------------------------------------------------
# Group D: Unit Violations & Conditional Constraints — 6 tests
# -----------------------------------------------------------------------------


def test_reject_unit_invalid_kind(
    make_minimal_v3_doc: Callable[[], Dict[str, Any]], v3_validator: Draft202012Validator
):
    doc = make_minimal_v3_doc()
    doc["units"] = [
        {
            "id": "u-bad-kind",
            "kind": "opinion",
            "title": "Bad unit",
            "text": "Some text",
            "text_format": "plain",
            "author_refs": ["auth-01"],
            "epistemic": "hypothesis",
            "status": "draft",
            "source_refs": [],
            "asset_ids": [],
        }
    ]
    errors = list(v3_validator.iter_errors(doc))
    assert_has_error(errors, expected_pointer="/units/0/kind", expected_validator="enum")


def test_reject_unit_invalid_epistemic(
    make_minimal_v3_doc: Callable[[], Dict[str, Any]], v3_validator: Draft202012Validator
):
    doc = make_minimal_v3_doc()
    doc["units"] = [
        {
            "id": "u-bad-ep",
            "kind": "analysis",
            "title": "Bad unit",
            "text": "Some text",
            "text_format": "plain",
            "author_refs": ["auth-01"],
            "epistemic": "certain",
            "status": "draft",
            "source_refs": [],
            "asset_ids": [],
        }
    ]
    errors = list(v3_validator.iter_errors(doc))
    assert_has_error(errors, expected_pointer="/units/0/epistemic", expected_validator="enum")


def test_reject_unit_invalid_text_format(
    make_minimal_v3_doc: Callable[[], Dict[str, Any]], v3_validator: Draft202012Validator
):
    doc = make_minimal_v3_doc()
    doc["units"] = [
        {
            "id": "u-bad-fmt",
            "kind": "analysis",
            "title": "Bad unit",
            "text": "Some text",
            "text_format": "raw-html",
            "author_refs": ["auth-01"],
            "epistemic": "hypothesis",
            "status": "draft",
            "source_refs": [],
            "asset_ids": [],
        }
    ]
    errors = list(v3_validator.iter_errors(doc))
    assert_has_error(errors, expected_pointer="/units/0/text_format", expected_validator="enum")


def test_reject_unit_conditional_supported_without_sources(
    make_minimal_v3_doc: Callable[[], Dict[str, Any]], v3_validator: Draft202012Validator
):
    doc = make_minimal_v3_doc()
    doc["units"] = [
        {
            "id": "u-unsup",
            "kind": "analysis",
            "title": "Claim without sources",
            "text": "Asserted claim without proof",
            "text_format": "plain",
            "author_refs": ["auth-01"],
            "epistemic": "supported",
            "status": "reviewed",
            "source_refs": [],
            "asset_ids": [],
        }
    ]
    errors = list(v3_validator.iter_errors(doc))
    assert_has_error(errors, expected_pointer="/units/0/source_refs", expected_validator="minItems")


def test_reject_unit_conditional_source_without_provenance(
    make_minimal_v3_doc: Callable[[], Dict[str, Any]], v3_validator: Draft202012Validator
):
    doc = make_minimal_v3_doc()
    doc["units"] = [
        {
            "id": "u-src-noprov",
            "kind": "source",
            "title": "Source without provenance",
            "text": "Quote text",
            "text_format": "plain",
            "author_refs": ["auth-01"],
            "epistemic": "reported",
            "status": "reviewed",
            "source_refs": [],
            "asset_ids": [],
        }
    ]
    errors = list(v3_validator.iter_errors(doc))
    assert_has_error(errors, expected_pointer="/units/0", expected_validator="required")


def test_reject_unit_additional_properties(
    make_minimal_v3_doc: Callable[[], Dict[str, Any]], v3_validator: Draft202012Validator
):
    doc = make_minimal_v3_doc()
    doc["units"] = [
        {
            "id": "u-extra",
            "kind": "analysis",
            "title": "Unit with foreign property",
            "text": "Text",
            "text_format": "plain",
            "author_refs": ["auth-01"],
            "epistemic": "hypothesis",
            "status": "draft",
            "source_refs": [],
            "asset_ids": [],
            "foreign_property": "illegal",
        }
    ]
    errors = list(v3_validator.iter_errors(doc))
    assert_has_error(errors, expected_pointer="/units/0", expected_validator="additionalProperties")


# -----------------------------------------------------------------------------
# Group E: Visual, Node, Edge Violations — 4 tests
# -----------------------------------------------------------------------------


def test_reject_visual_invalid_type(
    make_minimal_v3_doc: Callable[[], Dict[str, Any]], v3_validator: Draft202012Validator
):
    doc = make_minimal_v3_doc()
    doc["visuals"] = [
        {
            "id": "v-01",
            "type": "unsupported-chart",
            "title": "Chart",
            "question": "Q",
            "fallback": "F",
            "owner_unit_id": "u-01",
            "author_refs": ["auth-01"],
            "nodes": [
                {"id": "n1", "label": "L1", "unit_refs": ["u-01"]},
                {"id": "n2", "label": "L2", "unit_refs": ["u-01"]},
            ],
            "edges": [
                {
                    "id": "e1",
                    "from": "n1",
                    "to": "n2",
                    "relation": "supports",
                    "label": "E1",
                    "unit_refs": ["u-01"],
                }
            ],
        }
    ]
    errors = list(v3_validator.iter_errors(doc))
    assert_has_error(errors, expected_pointer="/visuals/0/type", expected_validator="const")


def test_reject_visual_insufficient_nodes(
    make_minimal_v3_doc: Callable[[], Dict[str, Any]], v3_validator: Draft202012Validator
):
    doc = make_minimal_v3_doc()
    doc["visuals"] = [
        {
            "id": "v-01",
            "type": "relationship-graph",
            "title": "Graph with only 1 node",
            "question": "Q",
            "fallback": "F",
            "owner_unit_id": "u-01",
            "author_refs": ["auth-01"],
            "nodes": [
                {"id": "n1", "label": "Single Node", "unit_refs": ["u-01"]}
            ],
            "edges": [],
        }
    ]
    errors = list(v3_validator.iter_errors(doc))
    assert_has_error(errors, expected_pointer="/visuals/0/nodes", expected_validator="minItems")


def test_reject_visual_insufficient_edges(
    make_minimal_v3_doc: Callable[[], Dict[str, Any]], v3_validator: Draft202012Validator
):
    doc = make_minimal_v3_doc()
    doc["visuals"] = [
        {
            "id": "v-01",
            "type": "relationship-graph",
            "title": "Graph without edges",
            "question": "Q",
            "fallback": "F",
            "owner_unit_id": "u-01",
            "author_refs": ["auth-01"],
            "nodes": [
                {"id": "n1", "label": "N1", "unit_refs": ["u-01"]},
                {"id": "n2", "label": "N2", "unit_refs": ["u-01"]},
            ],
            "edges": [],
        }
    ]
    errors = list(v3_validator.iter_errors(doc))
    assert_has_error(errors, expected_pointer="/visuals/0/edges", expected_validator="minItems")


def test_reject_edge_invalid_relation(
    make_minimal_v3_doc: Callable[[], Dict[str, Any]], v3_validator: Draft202012Validator
):
    doc = make_minimal_v3_doc()
    doc["visuals"] = [
        {
            "id": "v-01",
            "type": "relationship-graph",
            "title": "Graph with bad relation",
            "question": "Q",
            "fallback": "F",
            "owner_unit_id": "u-01",
            "author_refs": ["auth-01"],
            "nodes": [
                {"id": "n1", "label": "N1", "unit_refs": ["u-01"]},
                {"id": "n2", "label": "N2", "unit_refs": ["u-01"]},
            ],
            "edges": [
                {
                    "id": "e1",
                    "from": "n1",
                    "to": "n2",
                    "relation": "causes_damage",
                    "label": "Bad Relation",
                    "unit_refs": ["u-01"],
                }
            ],
        }
    ]
    errors = list(v3_validator.iter_errors(doc))
    assert_has_error(errors, expected_pointer="/visuals/0/edges/0/relation", expected_validator="enum")


# -----------------------------------------------------------------------------
# Group F: Asset, Extension & Manifest Violations — 4 tests
# -----------------------------------------------------------------------------


def test_reject_asset_invalid_mime(
    make_minimal_v3_doc: Callable[[], Dict[str, Any]], v3_validator: Draft202012Validator
):
    doc = make_minimal_v3_doc()
    doc["assets"] = [
        {
            "id": "a-bad-mime",
            "mime": "image/gif",
            "sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
            "byte_length": 10,
            "width": 10,
            "height": 10,
            "alt": "Gif alt",
            "caption": "Gif caption",
            "author_refs": ["auth-01"],
            "provenance": {"label": "Provenance"},
            "locator": {
                "mode": "embedded",
                "data_uri": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==",
            },
        }
    ]
    errors = list(v3_validator.iter_errors(doc))
    assert_has_error(errors, expected_pointer="/assets/0/mime", expected_validator="enum")


def test_reject_asset_invalid_sha256(
    make_minimal_v3_doc: Callable[[], Dict[str, Any]], v3_validator: Draft202012Validator
):
    doc = make_minimal_v3_doc()
    doc["assets"] = [
        {
            "id": "a-bad-sha",
            "mime": "image/png",
            "sha256": "INVALID_UPPERCASE_AND_SHORT_SHA",
            "byte_length": 10,
            "width": 10,
            "height": 10,
            "alt": "Alt",
            "caption": "Caption",
            "author_refs": ["auth-01"],
            "provenance": {"label": "Provenance"},
            "locator": {
                "mode": "embedded",
                "data_uri": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==",
            },
        }
    ]
    errors = list(v3_validator.iter_errors(doc))
    assert_has_error(errors, expected_pointer="/assets/0/sha256", expected_validator="pattern")


def test_reject_non_namespaced_extension_keys(
    make_minimal_v3_doc: Callable[[], Dict[str, Any]], v3_validator: Draft202012Validator
):
    doc = make_minimal_v3_doc()
    doc["extensions"] = {
        "unnamespaced_key_without_slash": "val"
    }
    errors = list(v3_validator.iter_errors(doc))
    assert len(errors) > 0
    err = errors[0]
    assert to_json_pointer(err.absolute_path) == "/extensions"
    assert err.validator in ("propertyNames", "pattern")


def test_reject_manifest_invalid_scope_or_consts(manifest_validator: Draft202012Validator):
    # Invalid scope
    m1 = {
        "format": "paralleldoc-integrity-1",
        "algorithm": "SHA-256",
        "scope": "normalized-text",
        "expected_sha256": "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad",
    }
    errs1 = list(manifest_validator.iter_errors(m1))
    assert_has_error(errs1, expected_pointer="/scope", expected_validator="const")

    # Invalid format
    m2 = {
        "format": "wrong-format",
        "algorithm": "SHA-256",
        "scope": "raw-bytes",
        "expected_sha256": "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad",
    }
    errs2 = list(manifest_validator.iter_errors(m2))
    assert_has_error(errs2, expected_pointer="/format", expected_validator="const")

    # Invalid algorithm
    m3 = {
        "format": "paralleldoc-integrity-1",
        "algorithm": "SHA-1",
        "scope": "raw-bytes",
        "expected_sha256": "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad",
    }
    errs3 = list(manifest_validator.iter_errors(m3))
    assert_has_error(errs3, expected_pointer="/algorithm", expected_validator="const")
