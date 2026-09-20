"""
Adversarial test harness for ParallelDoc 3.0 schema.v3.json and manifest.schema.json.
Milestone 1 (M1) — Empirical verification by Challenger M1-1.

Targeting stress edge cases:
1. Extra undocumented root or nested fields (must fail additionalProperties=false)
2. Invalid datetime formats & missing timezone offsets
3. Malformed IDs (empty strings, whitespace-only, illegal chars, length bounds)
4. Missing required fields across all $defs and root
5. Invalid manifest scope (anything other than "raw-bytes" must fail)
6. Hash field formatting (non-hex, wrong lengths, casing, whitespace)
7. Collection bounds and numeric constraints
"""

import copy
from datetime import datetime
import json
from pathlib import Path
import re
from typing import Any, Callable, Dict, List
import pytest

from jsonschema import Draft202012Validator
import jsonschema

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from validator import IntegrityEngine, get_default_format_checker, to_json_pointer


# RFC 3339 strict pattern requiring full date, 'T', full time, and timezone offset (Z or +/-HH:MM)
RFC3339_STRICT_PATTERN = re.compile(
    r"^\d{4}-(?:0[1-9]|1[0-2])-(?:0[1-9]|[12]\d|3[01])"
    r"T(?:[01]\d|2[0-3]):[0-5]\d:[0-5]\d(?:\.\d+)?"
    r"(?:Z|[+-](?:[01]\d|2[0-3]):[0-5]\d)$"
)


def make_strict_rfc3339_format_checker() -> jsonschema.FormatChecker:
    """Format checker enforcing RFC 3339 date-time with mandatory timezone offset."""
    checker = jsonschema.FormatChecker()

    @checker.checks("date-time")
    def _validate_datetime(val: Any) -> bool:
        if not isinstance(val, str):
            return True
        if not RFC3339_STRICT_PATTERN.match(val):
            return False
        # Verify calendar day validity (e.g. leap years, Feb 30)
        try:
            # Normalize trailing Z to +00:00 for python fromisoformat
            norm = val[:-1] + "+00:00" if val.endswith("Z") else val
            datetime.fromisoformat(norm)
            return True
        except (ValueError, TypeError):
            return False

    return checker


# -----------------------------------------------------------------------------
# 1. Extra Undocumented Root or Nested Fields (additionalProperties: false)
# -----------------------------------------------------------------------------

class TestAdversarialAdditionalProperties:
    """Verify additionalProperties: false on all root and nested schemas."""

    def test_root_rejects_extra_fields(self, make_rich_v3_doc: Callable[[], Dict[str, Any]], v3_validator: Draft202012Validator):
        doc = make_rich_v3_doc()
        doc["unapproved_root_field"] = "adversarial_payload"
        errs = list(v3_validator.iter_errors(doc))
        assert len(errs) > 0
        assert any(e.validator == "additionalProperties" and to_json_pointer(e.absolute_path) == "" for e in errs)

    def test_metadata_rejects_extra_fields(self, make_rich_v3_doc: Callable[[], Dict[str, Any]], v3_validator: Draft202012Validator):
        doc = make_rich_v3_doc()
        doc["metadata"]["extra_meta_prop"] = 42
        errs = list(v3_validator.iter_errors(doc))
        assert any(e.validator == "additionalProperties" and to_json_pointer(e.absolute_path) == "/metadata" for e in errs)

    def test_author_rejects_extra_fields(self, make_rich_v3_doc: Callable[[], Dict[str, Any]], v3_validator: Draft202012Validator):
        doc = make_rich_v3_doc()
        doc["authors"][0]["unauthorized_affiliation"] = "Secret Org"
        errs = list(v3_validator.iter_errors(doc))
        assert any(e.validator == "additionalProperties" and to_json_pointer(e.absolute_path) == "/authors/0" for e in errs)

    def test_provenance_rejects_extra_fields(self, make_rich_v3_doc: Callable[[], Dict[str, Any]], v3_validator: Draft202012Validator):
        doc = make_rich_v3_doc()
        doc["units"][0]["provenance"]["unauthorized_cert"] = "X509"
        errs = list(v3_validator.iter_errors(doc))
        assert any(e.validator == "additionalProperties" and to_json_pointer(e.absolute_path) == "/units/0/provenance" for e in errs)

    def test_unit_rejects_extra_fields(self, make_rich_v3_doc: Callable[[], Dict[str, Any]], v3_validator: Draft202012Validator):
        doc = make_rich_v3_doc()
        doc["units"][0]["columns"] = [1, 2, 3]  # legacy v2 artifact
        errs = list(v3_validator.iter_errors(doc))
        assert any(e.validator == "additionalProperties" and to_json_pointer(e.absolute_path) == "/units/0" for e in errs)

    def test_group_rejects_extra_fields(self, make_rich_v3_doc: Callable[[], Dict[str, Any]], v3_validator: Draft202012Validator):
        doc = make_rich_v3_doc()
        doc["groups"][0]["order_index"] = 99
        errs = list(v3_validator.iter_errors(doc))
        assert any(e.validator == "additionalProperties" and to_json_pointer(e.absolute_path) == "/groups/0" for e in errs)

    def test_visual_rejects_extra_fields(self, make_rich_v3_doc: Callable[[], Dict[str, Any]], v3_validator: Draft202012Validator):
        doc = make_rich_v3_doc()
        doc["visuals"][0]["theme_palette"] = "dark"
        errs = list(v3_validator.iter_errors(doc))
        assert any(e.validator == "additionalProperties" and to_json_pointer(e.absolute_path) == "/visuals/0" for e in errs)

    def test_node_rejects_extra_fields(self, make_rich_v3_doc: Callable[[], Dict[str, Any]], v3_validator: Draft202012Validator):
        doc = make_rich_v3_doc()
        doc["visuals"][0]["nodes"][0]["x_coord"] = 150.0  # authored coords forbidden in P0
        errs = list(v3_validator.iter_errors(doc))
        assert any(e.validator == "additionalProperties" and to_json_pointer(e.absolute_path) == "/visuals/0/nodes/0" for e in errs)

    def test_edge_rejects_extra_fields(self, make_rich_v3_doc: Callable[[], Dict[str, Any]], v3_validator: Draft202012Validator):
        doc = make_rich_v3_doc()
        doc["visuals"][0]["edges"][0]["curved"] = True
        errs = list(v3_validator.iter_errors(doc))
        assert any(e.validator == "additionalProperties" and to_json_pointer(e.absolute_path) == "/visuals/0/edges/0" for e in errs)

    def test_asset_rejects_extra_fields(self, make_rich_v3_doc: Callable[[], Dict[str, Any]], v3_validator: Draft202012Validator):
        doc = make_rich_v3_doc()
        doc["assets"][0]["exif_data"] = {"ISO": 100}
        errs = list(v3_validator.iter_errors(doc))
        assert any(e.validator == "additionalProperties" and to_json_pointer(e.absolute_path) == "/assets/0" for e in errs)

    def test_embedded_locator_rejects_extra_fields(self, make_rich_v3_doc: Callable[[], Dict[str, Any]], v3_validator: Draft202012Validator):
        doc = make_rich_v3_doc()
        doc["assets"][0]["locator"]["extra_blob"] = "leak"
        errs = list(v3_validator.iter_errors(doc))
        assert len(errs) > 0

    def test_relative_locator_rejects_extra_fields(self, make_rich_v3_doc: Callable[[], Dict[str, Any]], v3_validator: Draft202012Validator):
        doc = make_rich_v3_doc()
        doc["assets"][0]["locator"] = {"mode": "relative", "path": "images/pic.png", "extra_token": "leak"}
        errs = list(v3_validator.iter_errors(doc))
        assert len(errs) > 0

    def test_external_locator_rejects_extra_fields(self, make_rich_v3_doc: Callable[[], Dict[str, Any]], v3_validator: Draft202012Validator):
        doc = make_rich_v3_doc()
        doc["assets"][0]["locator"] = {"mode": "external", "url": "https://example.com/pic.png", "extra_token": "leak"}
        errs = list(v3_validator.iter_errors(doc))
        assert len(errs) > 0

    def test_profile_rejects_extra_fields(self, make_rich_v3_doc: Callable[[], Dict[str, Any]], v3_validator: Draft202012Validator):
        doc = make_rich_v3_doc()
        doc["profiles"][0]["custom_css_class"] = "theme-blue"
        errs = list(v3_validator.iter_errors(doc))
        assert any(e.validator == "additionalProperties" and to_json_pointer(e.absolute_path) == "/profiles/0" for e in errs)

    def test_panel_rejects_extra_fields(self, make_rich_v3_doc: Callable[[], Dict[str, Any]], v3_validator: Draft202012Validator):
        doc = make_rich_v3_doc()
        doc["profiles"][0]["panels"][0]["collapsible"] = True
        errs = list(v3_validator.iter_errors(doc))
        assert any(e.validator == "additionalProperties" and to_json_pointer(e.absolute_path) == "/profiles/0/panels/0" for e in errs)

    def test_manifest_rejects_extra_fields(self, manifest_validator: Draft202012Validator):
        man = {
            "format": "paralleldoc-integrity-1",
            "algorithm": "SHA-256",
            "scope": "raw-bytes",
            "expected_sha256": "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad",
            "salt": "adversarial_salt",
        }
        errs = list(manifest_validator.iter_errors(man))
        assert any(e.validator == "additionalProperties" and to_json_pointer(e.absolute_path) == "" for e in errs)


# -----------------------------------------------------------------------------
# 2. Datetime Formats & Missing Timezone Offsets
# -----------------------------------------------------------------------------

class TestAdversarialDatetimeAndOffsets:
    """Empirical investigation of datetime formatting and timezone enforcement."""

    @pytest.mark.parametrize(
        "valid_dt",
        [
            "2026-09-06T17:00:00Z",
            "2026-09-06T17:00:00.000Z",
            "2026-09-06T17:00:00+03:00",
            "2026-09-06T17:00:00-05:00",
            "2026-12-31T23:59:59.999999+00:00",
            "2026-02-28T12:00:00Z",
        ],
    )
    def test_valid_rfc3339_accepted(
        self, valid_dt: str, make_minimal_v3_doc: Callable[[], Dict[str, Any]], schema_v3_dict: Dict[str, Any]
    ):
        validator = Draft202012Validator(schema_v3_dict, format_checker=make_strict_rfc3339_format_checker())
        doc = make_minimal_v3_doc()
        doc["metadata"]["created_at"] = valid_dt
        errs = list(validator.iter_errors(doc))
        assert len(errs) == 0, f"Valid RFC 3339 date-time rejected: {valid_dt}"

    @pytest.mark.parametrize(
        "invalid_dt,reason",
        [
            ("2026-09-06T17:00:00", "Missing timezone offset"),
            ("2026-09-06 17:00:00", "Space instead of T separator"),
            ("2026-09-06", "Date only, missing time and offset"),
            ("17:00:00Z", "Time only, missing date"),
            ("2026-09-06T17:00:00+03", "Incomplete offset (missing minute)"),
            ("2026-09-06T17:00:00+0300", "Military offset without colon"),
            ("2026-02-30T10:00:00Z", "Invalid calendar day (Feb 30)"),
            ("2026-13-01T00:00:00Z", "Invalid month (13)"),
            ("2026-09-06T25:00:00Z", "Invalid hour (25)"),
            ("2026-09-06T12:60:00Z", "Invalid minute (60)"),
            ("2026-09-06T12:00:61Z", "Invalid second (61)"),
            ("not-a-datetime", "Arbitrary text"),
        ],
    )
    def test_invalid_or_missing_timezone_rfc3339_rejected_by_strict_checker(
        self, invalid_dt: str, reason: str, make_minimal_v3_doc: Callable[[], Dict[str, Any]], schema_v3_dict: Dict[str, Any]
    ):
        validator = Draft202012Validator(schema_v3_dict, format_checker=make_strict_rfc3339_format_checker())
        doc = make_minimal_v3_doc()
        doc["metadata"]["created_at"] = invalid_dt
        errs = list(validator.iter_errors(doc))
        assert len(errs) > 0, f"Expected rejection for '{invalid_dt}' ({reason}), but validator passed."
        assert any(e.validator == "format" for e in errs)

    def test_strict_default_checker_rejects_missing_timezone(
        self, make_minimal_v3_doc: Callable[[], Dict[str, Any]]
    ):
        """Verify that default format checker in src/validator.py strictly rejects naive
        datetimes lacking timezone offsets and date-only strings per RFC 3339 Section 5.6.
        """
        checker = get_default_format_checker()
        assert checker is not None
        fn = checker.checkers["date-time"][0]
        is_valid_naive = fn("2026-09-06T17:00:00")
        is_valid_date_only = fn("2026-09-06")

        assert is_valid_naive is False, "Default checker must reject naive datetime"
        assert is_valid_date_only is False, "Default checker must reject date-only string"



# -----------------------------------------------------------------------------
# 3. Malformed IDs across all entities
# -----------------------------------------------------------------------------

class TestAdversarialMalformedIDs:
    """Stress-test regex pattern: ^[A-Za-z0-9][A-Za-z0-9._:-]*$ and length bounds."""

    ADVERSARIAL_IDS = [
        ("", "Empty string"),
        ("   ", "Whitespace only"),
        (" leading-space", "Leading space"),
        ("trailing-space ", "Trailing space"),
        ("internal space", "Internal space"),
        (".dot-prefix", "Dot prefix (non-alphanumeric first char)"),
        ("-dash-prefix", "Dash prefix (non-alphanumeric first char)"),
        ("_underscore-prefix", "Underscore prefix (non-alphanumeric first char)"),
        (":colon-prefix", "Colon prefix (non-alphanumeric first char)"),
        ("slash/forbidden", "Forward slash"),
        ("backslash\\forbidden", "Backslash"),
        ("question?mark", "Question mark"),
        ("hash#forbidden", "Hash symbol"),
        ("at@forbidden", "At symbol"),
        ("excl!forbidden", "Exclamation mark"),
        ("id_\u044e\u043d\u0438\u043a\u043e\u0434", "Cyrillic unicode"),
        ("newline\nid", "Newline control character"),
        ("x" * 129, "129 characters (exceeds maxLength 128)"),
    ]

    @pytest.mark.parametrize("bad_id,desc", ADVERSARIAL_IDS)
    def test_reject_malformed_metadata_document_id(
        self, bad_id: str, desc: str, make_minimal_v3_doc: Callable[[], Dict[str, Any]], v3_validator: Draft202012Validator
    ):
        doc = make_minimal_v3_doc()
        doc["metadata"]["document_id"] = bad_id
        errs = list(v3_validator.iter_errors(doc))
        assert len(errs) > 0, f"Failed to reject malformed ID: {desc}"

    @pytest.mark.parametrize("bad_id,desc", ADVERSARIAL_IDS)
    def test_reject_malformed_metadata_revision(
        self, bad_id: str, desc: str, make_minimal_v3_doc: Callable[[], Dict[str, Any]], v3_validator: Draft202012Validator
    ):
        doc = make_minimal_v3_doc()
        doc["metadata"]["revision"] = bad_id
        errs = list(v3_validator.iter_errors(doc))
        assert len(errs) > 0, f"Failed to reject malformed revision: {desc}"

    @pytest.mark.parametrize("bad_id,desc", ADVERSARIAL_IDS)
    def test_reject_malformed_author_id(
        self, bad_id: str, desc: str, make_minimal_v3_doc: Callable[[], Dict[str, Any]], v3_validator: Draft202012Validator
    ):
        doc = make_minimal_v3_doc()
        doc["authors"][0]["id"] = bad_id
        errs = list(v3_validator.iter_errors(doc))
        assert len(errs) > 0, f"Failed to reject malformed author.id: {desc}"

    @pytest.mark.parametrize("bad_id,desc", ADVERSARIAL_IDS)
    def test_reject_malformed_unit_id(
        self, bad_id: str, desc: str, make_rich_v3_doc: Callable[[], Dict[str, Any]], v3_validator: Draft202012Validator
    ):
        doc = make_rich_v3_doc()
        doc["units"][0]["id"] = bad_id
        errs = list(v3_validator.iter_errors(doc))
        assert len(errs) > 0, f"Failed to reject malformed unit.id: {desc}"

    @pytest.mark.parametrize("bad_id,desc", ADVERSARIAL_IDS)
    def test_reject_malformed_group_id(
        self, bad_id: str, desc: str, make_rich_v3_doc: Callable[[], Dict[str, Any]], v3_validator: Draft202012Validator
    ):
        doc = make_rich_v3_doc()
        doc["groups"][0]["id"] = bad_id
        errs = list(v3_validator.iter_errors(doc))
        assert len(errs) > 0, f"Failed to reject malformed group.id: {desc}"

    @pytest.mark.parametrize("bad_id,desc", ADVERSARIAL_IDS)
    def test_reject_malformed_visual_id(
        self, bad_id: str, desc: str, make_rich_v3_doc: Callable[[], Dict[str, Any]], v3_validator: Draft202012Validator
    ):
        doc = make_rich_v3_doc()
        doc["visuals"][0]["id"] = bad_id
        errs = list(v3_validator.iter_errors(doc))
        assert len(errs) > 0, f"Failed to reject malformed visual.id: {desc}"

    @pytest.mark.parametrize("bad_id,desc", ADVERSARIAL_IDS)
    def test_reject_malformed_node_id(
        self, bad_id: str, desc: str, make_rich_v3_doc: Callable[[], Dict[str, Any]], v3_validator: Draft202012Validator
    ):
        doc = make_rich_v3_doc()
        doc["visuals"][0]["nodes"][0]["id"] = bad_id
        errs = list(v3_validator.iter_errors(doc))
        assert len(errs) > 0, f"Failed to reject malformed node.id: {desc}"

    @pytest.mark.parametrize("bad_id,desc", ADVERSARIAL_IDS)
    def test_reject_malformed_edge_id(
        self, bad_id: str, desc: str, make_rich_v3_doc: Callable[[], Dict[str, Any]], v3_validator: Draft202012Validator
    ):
        doc = make_rich_v3_doc()
        doc["visuals"][0]["edges"][0]["id"] = bad_id
        errs = list(v3_validator.iter_errors(doc))
        assert len(errs) > 0, f"Failed to reject malformed edge.id: {desc}"

    @pytest.mark.parametrize("bad_id,desc", ADVERSARIAL_IDS)
    def test_reject_malformed_asset_id(
        self, bad_id: str, desc: str, make_rich_v3_doc: Callable[[], Dict[str, Any]], v3_validator: Draft202012Validator
    ):
        doc = make_rich_v3_doc()
        doc["assets"][0]["id"] = bad_id
        errs = list(v3_validator.iter_errors(doc))
        assert len(errs) > 0, f"Failed to reject malformed asset.id: {desc}"

    @pytest.mark.parametrize("bad_id,desc", ADVERSARIAL_IDS)
    def test_reject_malformed_profile_id(
        self, bad_id: str, desc: str, make_rich_v3_doc: Callable[[], Dict[str, Any]], v3_validator: Draft202012Validator
    ):
        doc = make_rich_v3_doc()
        doc["profiles"][0]["id"] = bad_id
        errs = list(v3_validator.iter_errors(doc))
        assert len(errs) > 0, f"Failed to reject malformed profile.id: {desc}"

    @pytest.mark.parametrize("bad_id,desc", ADVERSARIAL_IDS)
    def test_reject_malformed_panel_id(
        self, bad_id: str, desc: str, make_rich_v3_doc: Callable[[], Dict[str, Any]], v3_validator: Draft202012Validator
    ):
        doc = make_rich_v3_doc()
        doc["profiles"][0]["panels"][0]["id"] = bad_id
        errs = list(v3_validator.iter_errors(doc))
        assert len(errs) > 0, f"Failed to reject malformed panel.id: {desc}"

    def test_valid_ids_accepted(self, make_minimal_v3_doc: Callable[[], Dict[str, Any]], v3_validator: Draft202012Validator):
        doc = make_minimal_v3_doc()
        # Max length 128 exactly
        doc["metadata"]["document_id"] = "A" + "x" * 127
        # Mixed allowed punctuation: . _ : -
        doc["metadata"]["revision"] = "Rev.1_Alpha:build-99"
        errs = list(v3_validator.iter_errors(doc))
        assert len(errs) == 0


# -----------------------------------------------------------------------------
# 4. Missing Required Fields Across $defs and Root
# -----------------------------------------------------------------------------

class TestAdversarialRequiredFields:
    """Parametric adversarial tests deleting required fields across all entities."""

    ROOT_REQUIRED = ["format", "version", "metadata", "authors", "units", "groups", "visuals", "assets", "profiles"]
    METADATA_REQUIRED = ["document_id", "revision", "title", "author_refs"]
    AUTHOR_REQUIRED = ["id", "kind", "name"]
    PROVENANCE_REQUIRED = ["label"]
    UNIT_REQUIRED = ["id", "kind", "title", "text", "text_format", "author_refs", "epistemic", "status", "source_refs", "asset_ids"]
    GROUP_REQUIRED = ["id", "title", "unit_refs"]
    VISUAL_REQUIRED = ["id", "type", "title", "question", "fallback", "owner_unit_id", "author_refs", "nodes", "edges"]
    NODE_REQUIRED = ["id", "label", "unit_refs"]
    EDGE_REQUIRED = ["id", "from", "to", "relation", "label", "unit_refs"]
    ASSET_REQUIRED = ["id", "mime", "sha256", "byte_length", "width", "height", "alt", "caption", "author_refs", "provenance", "locator"]
    PROFILE_REQUIRED = ["id", "title", "density", "panels"]
    PANEL_REQUIRED = ["id", "title", "kinds", "weight"]

    @pytest.mark.parametrize("prop", ROOT_REQUIRED)
    def test_missing_root_field(self, prop: str, make_rich_v3_doc: Callable[[], Dict[str, Any]], v3_validator: Draft202012Validator):
        doc = make_rich_v3_doc()
        del doc[prop]
        errs = list(v3_validator.iter_errors(doc))
        assert any(e.validator == "required" and to_json_pointer(e.absolute_path) == "" for e in errs)

    @pytest.mark.parametrize("prop", METADATA_REQUIRED)
    def test_missing_metadata_field(self, prop: str, make_rich_v3_doc: Callable[[], Dict[str, Any]], v3_validator: Draft202012Validator):
        doc = make_rich_v3_doc()
        del doc["metadata"][prop]
        errs = list(v3_validator.iter_errors(doc))
        assert any(e.validator == "required" and to_json_pointer(e.absolute_path) == "/metadata" for e in errs)

    @pytest.mark.parametrize("prop", AUTHOR_REQUIRED)
    def test_missing_author_field(self, prop: str, make_rich_v3_doc: Callable[[], Dict[str, Any]], v3_validator: Draft202012Validator):
        doc = make_rich_v3_doc()
        del doc["authors"][0][prop]
        errs = list(v3_validator.iter_errors(doc))
        assert any(e.validator == "required" and to_json_pointer(e.absolute_path) == "/authors/0" for e in errs)

    @pytest.mark.parametrize("prop", PROVENANCE_REQUIRED)
    def test_missing_provenance_field(self, prop: str, make_rich_v3_doc: Callable[[], Dict[str, Any]], v3_validator: Draft202012Validator):
        doc = make_rich_v3_doc()
        del doc["units"][0]["provenance"][prop]
        errs = list(v3_validator.iter_errors(doc))
        assert any(e.validator == "required" and to_json_pointer(e.absolute_path) == "/units/0/provenance" for e in errs)

    @pytest.mark.parametrize("prop", UNIT_REQUIRED)
    def test_missing_unit_field(self, prop: str, make_rich_v3_doc: Callable[[], Dict[str, Any]], v3_validator: Draft202012Validator):
        doc = make_rich_v3_doc()
        del doc["units"][0][prop]
        errs = list(v3_validator.iter_errors(doc))
        assert any(e.validator == "required" and to_json_pointer(e.absolute_path) == "/units/0" for e in errs)

    @pytest.mark.parametrize("prop", GROUP_REQUIRED)
    def test_missing_group_field(self, prop: str, make_rich_v3_doc: Callable[[], Dict[str, Any]], v3_validator: Draft202012Validator):
        doc = make_rich_v3_doc()
        del doc["groups"][0][prop]
        errs = list(v3_validator.iter_errors(doc))
        assert any(e.validator == "required" and to_json_pointer(e.absolute_path) == "/groups/0" for e in errs)

    @pytest.mark.parametrize("prop", VISUAL_REQUIRED)
    def test_missing_visual_field(self, prop: str, make_rich_v3_doc: Callable[[], Dict[str, Any]], v3_validator: Draft202012Validator):
        doc = make_rich_v3_doc()
        del doc["visuals"][0][prop]
        errs = list(v3_validator.iter_errors(doc))
        assert any(e.validator == "required" and to_json_pointer(e.absolute_path) == "/visuals/0" for e in errs)

    @pytest.mark.parametrize("prop", NODE_REQUIRED)
    def test_missing_node_field(self, prop: str, make_rich_v3_doc: Callable[[], Dict[str, Any]], v3_validator: Draft202012Validator):
        doc = make_rich_v3_doc()
        del doc["visuals"][0]["nodes"][0][prop]
        errs = list(v3_validator.iter_errors(doc))
        assert any(e.validator == "required" and to_json_pointer(e.absolute_path) == "/visuals/0/nodes/0" for e in errs)

    @pytest.mark.parametrize("prop", EDGE_REQUIRED)
    def test_missing_edge_field(self, prop: str, make_rich_v3_doc: Callable[[], Dict[str, Any]], v3_validator: Draft202012Validator):
        doc = make_rich_v3_doc()
        del doc["visuals"][0]["edges"][0][prop]
        errs = list(v3_validator.iter_errors(doc))
        assert any(e.validator == "required" and to_json_pointer(e.absolute_path) == "/visuals/0/edges/0" for e in errs)

    @pytest.mark.parametrize("prop", ASSET_REQUIRED)
    def test_missing_asset_field(self, prop: str, make_rich_v3_doc: Callable[[], Dict[str, Any]], v3_validator: Draft202012Validator):
        doc = make_rich_v3_doc()
        del doc["assets"][0][prop]
        errs = list(v3_validator.iter_errors(doc))
        assert any(e.validator == "required" and to_json_pointer(e.absolute_path) == "/assets/0" for e in errs)

    @pytest.mark.parametrize("prop", PROFILE_REQUIRED)
    def test_missing_profile_field(self, prop: str, make_rich_v3_doc: Callable[[], Dict[str, Any]], v3_validator: Draft202012Validator):
        doc = make_rich_v3_doc()
        del doc["profiles"][0][prop]
        errs = list(v3_validator.iter_errors(doc))
        assert any(e.validator == "required" and to_json_pointer(e.absolute_path) == "/profiles/0" for e in errs)

    @pytest.mark.parametrize("prop", PANEL_REQUIRED)
    def test_missing_panel_field(self, prop: str, make_rich_v3_doc: Callable[[], Dict[str, Any]], v3_validator: Draft202012Validator):
        doc = make_rich_v3_doc()
        del doc["profiles"][0]["panels"][0][prop]
        errs = list(v3_validator.iter_errors(doc))
        assert any(e.validator == "required" and to_json_pointer(e.absolute_path) == "/profiles/0/panels/0" for e in errs)

    @pytest.mark.parametrize("prop", ["format", "algorithm", "scope", "expected_sha256"])
    def test_missing_manifest_field(self, prop: str, manifest_validator: Draft202012Validator):
        man = {
            "format": "paralleldoc-integrity-1",
            "algorithm": "SHA-256",
            "scope": "raw-bytes",
            "expected_sha256": "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad",
        }
        del man[prop]
        errs = list(manifest_validator.iter_errors(man))
        assert any(e.validator == "required" and to_json_pointer(e.absolute_path) == "" for e in errs)

    def test_conditional_supported_unit_requires_source_refs(
        self, make_rich_v3_doc: Callable[[], Dict[str, Any]], v3_validator: Draft202012Validator
    ):
        doc = make_rich_v3_doc()
        # u-ana has epistemic: "supported"
        doc["units"][2]["source_refs"] = []
        errs = list(v3_validator.iter_errors(doc))
        assert len(errs) > 0
        assert any(e.validator == "minItems" and to_json_pointer(e.absolute_path) == "/units/2/source_refs" for e in errs)

    def test_conditional_source_unit_requires_provenance(
        self, make_rich_v3_doc: Callable[[], Dict[str, Any]], v3_validator: Draft202012Validator
    ):
        doc = make_rich_v3_doc()
        # u-src has kind: "source"
        del doc["units"][0]["provenance"]
        errs = list(v3_validator.iter_errors(doc))
        assert len(errs) > 0
        assert any(e.validator == "required" and to_json_pointer(e.absolute_path) == "/units/0" for e in errs)


# -----------------------------------------------------------------------------
# 5. Manifest Scope Invalidation
# -----------------------------------------------------------------------------

class TestAdversarialManifestScope:
    """Stress-test scope: const 'raw-bytes'. Anything else must fail."""

    @pytest.mark.parametrize(
        "invalid_scope,desc",
        [
            ("normalized-text", "Normalized text scope (legacy r1 concept)"),
            ("raw_bytes", "Underscore instead of hyphen"),
            ("RAW-BYTES", "Uppercase raw-bytes"),
            ("source-only", "Source-only partial scope"),
            ("raw-bytes-bom", "Alternative scope variant"),
            ("", "Empty string scope"),
            ("   ", "Whitespace scope"),
            (123, "Integer type instead of string"),
            (None, "Null value"),
            (True, "Boolean value"),
            (["raw-bytes"], "Array wrapping scope"),
            ({"scope": "raw-bytes"}, "Object wrapping scope"),
        ],
    )
    def test_reject_invalid_manifest_scopes(self, invalid_scope: Any, desc: str, manifest_validator: Draft202012Validator):
        man = {
            "format": "paralleldoc-integrity-1",
            "algorithm": "SHA-256",
            "scope": invalid_scope,
            "expected_sha256": "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad",
        }
        errs = list(manifest_validator.iter_errors(man))
        assert len(errs) > 0, f"Expected manifest to reject invalid scope: {desc}"
        assert any(e.validator in ("const", "type") and to_json_pointer(e.absolute_path) == "/scope" for e in errs)

    def test_accept_exact_raw_bytes_scope(self, manifest_validator: Draft202012Validator):
        man = {
            "format": "paralleldoc-integrity-1",
            "algorithm": "SHA-256",
            "scope": "raw-bytes",
            "expected_sha256": "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad",
        }
        errs = list(manifest_validator.iter_errors(man))
        assert len(errs) == 0


# -----------------------------------------------------------------------------
# 6. Hash Field Formatting
# -----------------------------------------------------------------------------

class TestAdversarialHashFormatting:
    """Stress-test regex pattern: ^[a-f0-9]{64}$ on manifest and doc hashes."""

    MALFORMED_HASHES = [
        ("A" * 64, "All uppercase 64 chars"),
        ("a" * 63 + "A", "Single uppercase char at end"),
        ("a" * 63, "63 characters (too short)"),
        ("a" * 65, "65 characters (too long)"),
        ("a" * 32, "MD5 length (32 chars)"),
        ("", "Empty string"),
        ("g" * 64, "Non-hex character 'g'"),
        ("z" * 64, "Non-hex character 'z'"),
        (" " * 64, "64 spaces"),
        (" " + "a" * 63, "Leading space"),
        ("a" * 63 + " ", "Trailing space"),
        ("a" * 32 + " " + "a" * 31, "Internal space"),
        ("a" * 63 + "\n", "Trailing newline"),
        ("0x" + "a" * 62, "0x hex prefix"),
    ]

    @pytest.mark.parametrize("bad_hash,desc", MALFORMED_HASHES)
    def test_reject_manifest_malformed_expected_sha256(
        self, bad_hash: str, desc: str, manifest_validator: Draft202012Validator
    ):
        man = {
            "format": "paralleldoc-integrity-1",
            "algorithm": "SHA-256",
            "scope": "raw-bytes",
            "expected_sha256": bad_hash,
        }
        errs = list(manifest_validator.iter_errors(man))
        assert len(errs) > 0, f"Expected manifest to reject hash: {desc}"
        assert any(e.validator == "pattern" and to_json_pointer(e.absolute_path) == "/expected_sha256" for e in errs)

    @pytest.mark.parametrize("bad_hash,desc", MALFORMED_HASHES)
    def test_reject_asset_malformed_sha256(
        self, bad_hash: str, desc: str, make_rich_v3_doc: Callable[[], Dict[str, Any]], v3_validator: Draft202012Validator
    ):
        doc = make_rich_v3_doc()
        doc["assets"][0]["sha256"] = bad_hash
        errs = list(v3_validator.iter_errors(doc))
        assert len(errs) > 0, f"Expected asset to reject hash: {desc}"
        assert any(e.validator == "pattern" and to_json_pointer(e.absolute_path) == "/assets/0/sha256" for e in errs)

    @pytest.mark.parametrize("bad_hash,desc", MALFORMED_HASHES)
    def test_reject_provenance_malformed_source_sha256(
        self, bad_hash: str, desc: str, make_rich_v3_doc: Callable[[], Dict[str, Any]], v3_validator: Draft202012Validator
    ):
        doc = make_rich_v3_doc()
        doc["units"][0]["provenance"]["source_sha256"] = bad_hash
        errs = list(v3_validator.iter_errors(doc))
        assert len(errs) > 0, f"Expected provenance to reject hash: {desc}"
        assert any(e.validator == "pattern" and to_json_pointer(e.absolute_path) == "/units/0/provenance/source_sha256" for e in errs)


# -----------------------------------------------------------------------------
# 7. Collection Bounds, Empty Strings & Numeric Constraints
# -----------------------------------------------------------------------------

class TestAdversarialCollectionBoundsAndNumbers:
    """Stress-test collection bounds (minItems, maxItems) and numeric bounds."""

    def test_visual_nodes_less_than_two_rejected(
        self, make_rich_v3_doc: Callable[[], Dict[str, Any]], v3_validator: Draft202012Validator
    ):
        doc = make_rich_v3_doc()
        # Single node in visual
        doc["visuals"][0]["nodes"] = [{"id": "n-01", "label": "Sole Node", "unit_refs": ["u-src"]}]
        errs = list(v3_validator.iter_errors(doc))
        assert any(e.validator == "minItems" and to_json_pointer(e.absolute_path) == "/visuals/0/nodes" for e in errs)

    def test_visual_edges_empty_rejected(
        self, make_rich_v3_doc: Callable[[], Dict[str, Any]], v3_validator: Draft202012Validator
    ):
        doc = make_rich_v3_doc()
        doc["visuals"][0]["edges"] = []
        errs = list(v3_validator.iter_errors(doc))
        assert any(e.validator == "minItems" and to_json_pointer(e.absolute_path) == "/visuals/0/edges" for e in errs)

    def test_profile_panels_less_than_two_rejected(
        self, make_rich_v3_doc: Callable[[], Dict[str, Any]], v3_validator: Draft202012Validator
    ):
        doc = make_rich_v3_doc()
        doc["profiles"][0]["panels"] = [
            {"id": "p-1", "title": "Single Panel", "kinds": ["source", "model"], "weight": 50}
        ]
        errs = list(v3_validator.iter_errors(doc))
        assert any(e.validator == "minItems" and to_json_pointer(e.absolute_path) == "/profiles/0/panels" for e in errs)

    def test_profile_panels_greater_than_four_rejected(
        self, make_rich_v3_doc: Callable[[], Dict[str, Any]], v3_validator: Draft202012Validator
    ):
        doc = make_rich_v3_doc()
        doc["profiles"][0]["panels"] = [
            {"id": f"p-{i}", "title": f"Panel {i}", "kinds": ["source"], "weight": 20}
            for i in range(5)
        ]
        errs = list(v3_validator.iter_errors(doc))
        assert any(e.validator == "maxItems" and to_json_pointer(e.absolute_path) == "/profiles/0/panels" for e in errs)

    def test_panel_weight_zero_or_negative_rejected(
        self, make_rich_v3_doc: Callable[[], Dict[str, Any]], v3_validator: Draft202012Validator
    ):
        doc = make_rich_v3_doc()
        doc["profiles"][0]["panels"][0]["weight"] = 0
        errs = list(v3_validator.iter_errors(doc))
        assert any(e.validator == "exclusiveMinimum" and to_json_pointer(e.absolute_path) == "/profiles/0/panels/0/weight" for e in errs)

        doc["profiles"][0]["panels"][0]["weight"] = -5.5
        errs2 = list(v3_validator.iter_errors(doc))
        assert any(e.validator == "exclusiveMinimum" and to_json_pointer(e.absolute_path) == "/profiles/0/panels/0/weight" for e in errs2)

    def test_asset_zero_or_negative_dimensions_rejected(
        self, make_rich_v3_doc: Callable[[], Dict[str, Any]], v3_validator: Draft202012Validator
    ):
        doc = make_rich_v3_doc()
        doc["assets"][0]["width"] = 0
        errs = list(v3_validator.iter_errors(doc))
        assert any(e.validator == "minimum" and to_json_pointer(e.absolute_path) == "/assets/0/width" for e in errs)

        doc["assets"][0]["height"] = -1
        errs2 = list(v3_validator.iter_errors(doc))
        assert any(e.validator == "minimum" and to_json_pointer(e.absolute_path) == "/assets/0/height" for e in errs2)

        doc["assets"][0]["byte_length"] = 0
        errs3 = list(v3_validator.iter_errors(doc))
        assert any(e.validator == "minimum" and to_json_pointer(e.absolute_path) == "/assets/0/byte_length" for e in errs3)

    def test_empty_text_fields_rejected_by_min_length(
        self, make_rich_v3_doc: Callable[[], Dict[str, Any]], v3_validator: Draft202012Validator
    ):
        doc = make_rich_v3_doc()
        doc["units"][0]["text"] = ""
        errs = list(v3_validator.iter_errors(doc))
        assert any(e.validator == "minLength" and to_json_pointer(e.absolute_path) == "/units/0/text" for e in errs)

        doc["metadata"]["title"] = ""
        errs2 = list(v3_validator.iter_errors(doc))
        assert any(e.validator == "minLength" and to_json_pointer(e.absolute_path) == "/metadata/title" for e in errs2)
