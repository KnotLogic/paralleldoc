"""
Suite 1: Draft 2020-12 Meta-Schema Validation for schema.v3.json & manifest.schema.json.
Strict compliance with Spec r2 §8.
"""

from typing import Any, Dict, Set
import pytest
from jsonschema import Draft202012Validator


def test_schema_v3_meta_validation(schema_v3_dict: Dict[str, Any]):
    """Verify schema.v3.json passes Draft 2020-12 meta-validation."""
    Draft202012Validator.check_schema(schema_v3_dict)
    assert schema_v3_dict.get("$schema") == "https://json-schema.org/draft/2020-12/schema"
    assert schema_v3_dict.get("title") == "ParallelDoc 3.0 portable semantic document"
    assert schema_v3_dict.get("type") == "object"
    assert schema_v3_dict.get("additionalProperties") is False


def test_manifest_schema_meta_validation(manifest_schema_dict: Dict[str, Any]):
    """Verify manifest.schema.json passes Draft 2020-12 meta-validation."""
    Draft202012Validator.check_schema(manifest_schema_dict)
    assert manifest_schema_dict.get("$schema") == "https://json-schema.org/draft/2020-12/schema"
    assert manifest_schema_dict.get("title") == "ParallelDoc detached digest"
    assert manifest_schema_dict.get("type") == "object"
    assert manifest_schema_dict.get("additionalProperties") is False


def test_schema_v3_definitions_inventory(schema_v3_dict: Dict[str, Any]):
    """Verify schema.v3.json contains all 18 definitions under $defs."""
    expected_defs = {
        "id",
        "text",
        "hash",
        "ids",
        "refs",
        "kind",
        "extensions",
        "metadata",
        "author",
        "provenance",
        "unit",
        "group",
        "visual",
        "node",
        "edge",
        "asset",
        "profile",
        "panel",
    }
    defs = set(schema_v3_dict.get("$defs", {}).keys())
    assert defs == expected_defs, f"Missing or unexpected definitions: {expected_defs ^ defs}"


def test_schema_v3_internal_refs_resolvable(schema_v3_dict: Dict[str, Any]):
    """Verify that all internal $ref pointers in schema.v3.json resolve to existing definitions."""
    found_refs: Set[str] = set()

    def _collect_refs(sub_schema: Any):
        if isinstance(sub_schema, dict):
            for k, v in sub_schema.items():
                if k == "$ref" and isinstance(v, str):
                    found_refs.add(v)
                else:
                    _collect_refs(v)
        elif isinstance(sub_schema, list):
            for item in sub_schema:
                _collect_refs(item)

    _collect_refs(schema_v3_dict)

    defs = schema_v3_dict.get("$defs", {})
    for ref_str in found_refs:
        prefix = "#/$defs/"
        assert ref_str.startswith(prefix), f"Non-local ref detected: {ref_str}"
        def_name = ref_str[len(prefix):]
        assert def_name in defs, f"Dangling schema $ref: {ref_str}"

    # Verify constructor builds resolver without exception
    validator = Draft202012Validator(schema_v3_dict)
    assert validator is not None


def test_manifest_schema_const_constraints(manifest_schema_dict: Dict[str, Any]):
    """Verify manifest.schema.json specifies exact required const constraints."""
    props = manifest_schema_dict.get("properties", {})
    assert props.get("format") == {"const": "paralleldoc-integrity-1"}
    assert props.get("algorithm") == {"const": "SHA-256"}
    assert props.get("scope") == {"const": "raw-bytes"}
    assert props.get("expected_sha256") == {"type": "string", "pattern": "^[a-f0-9]{64}$"}
    assert manifest_schema_dict.get("additionalProperties") is False
    assert set(manifest_schema_dict.get("required", [])) == {"format", "algorithm", "scope", "expected_sha256"}
