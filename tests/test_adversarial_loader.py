"""
ParallelDoc 3.0 (r2 / V3-ONLY) — Adversarial Stress Test Suite for Loader & Manifest.
Author: Challenger M2-2 (Adversarial Stress on Format Guard & Manifest)
Scope:
  1. Spoofed v3 files with embedded legacy keys ("columns", "items")
  2. Non-dict root types (JSON arrays, booleans, numbers, null, strings)
  3. Corrupted JSON syntax with nested braces and strings to stress line/col locator
  4. Malformed manifests (extra properties, uppercase hex, wrong algorithm/format/scope)
  5. Manifest document_id / revision mismatches and simultaneous multi-error states
  6. Absolute prohibition of auto-migration and silent fallback under any input
"""

import hashlib
import json
from pathlib import Path
import re
from typing import Any, Callable, Dict, List
import pytest

from loader import (
    ErrorType,
    IntegrityState,
    ManifestMatchStatus,
    REJECTION_DIAGNOSTIC_MESSAGE,
    StructureState,
    UTF8_BOM,
    compute_raw_sha256,
    generate_error_snippet,
    generate_raw_preview,
    load_document,
    locate_error_pointer,
    verify_manifest,
)
from validator import IntegrityEngine, IssueSeverity


# =============================================================================
# 1. SPOOFED V3 FILES & EMBEDDED LEGACY KEYS (§9, F07, F09, AC-02)
# =============================================================================

class TestAdversarialFormatGuardSpoofing:
    """Stress-test strict V3-only format guard against deceptive inputs."""

    @pytest.mark.parametrize("legacy_key,legacy_val", [
        ("columns", []),
        ("columns", [{"key": "col1"}]),
        ("columns", None),
        ("columns", "legacy-columns"),
        ("columns", {}),
        ("columns", 123),
        ("items", []),
        ("items", [{"id": "item-1"}]),
        ("items", None),
        ("items", "legacy-items"),
        ("items", {}),
        ("items", 456),
    ])
    def test_reject_spoofed_v3_with_legacy_key(
        self,
        make_minimal_v3_doc: Callable[[], Dict[str, Any]],
        legacy_key: str,
        legacy_val: Any
    ):
        """Even if format='paralleldoc' and version='3.0' and valid collections exist,
        presence of root 'columns' or 'items' MUST be rejected immediately."""
        doc = make_minimal_v3_doc()
        doc[legacy_key] = legacy_val
        raw_bytes = json.dumps(doc).encode("utf-8")

        res = load_document(raw_bytes)
        assert res.success is False
        assert res.error_type == ErrorType.REJECTED_UNSUPPORTED
        assert res.diagnostic_message == REJECTION_DIAGNOSTIC_MESSAGE
        assert res.doc is None, "Violation: doc must be None on rejection (zero partial synthesis)"
        assert res.structure_state == StructureState.INVALID
        assert res.raw_preview is not None
        assert legacy_key in (res.snippet or res.raw_preview.snippet or "")

    def test_valid_v3_with_legacy_words_inside_strings(
        self,
        make_minimal_v3_doc: Callable[[], Dict[str, Any]],
        engine: IntegrityEngine
    ):
        """The substrings 'columns' or 'items' INSIDE text/title strings MUST NOT trigger rejection."""
        doc = make_minimal_v3_doc()
        doc["metadata"]["title"] = 'Document discussing "columns": [] and "items": []'
        doc["units"].append({
            "id": "u-test-01",
            "kind": "source",
            "title": "Clause with legacy keywords",
            "text": 'Quoting legacy spec: "columns": [{"key": "col1"}], "items": [{"id": "it1"}]',
            "text_format": "plain",
            "source_refs": [],
            "asset_ids": [],
            "author_refs": ["auth-01"],
            "epistemic": "reported",
            "status": "done",
            "provenance": {
                "label": "Legacy spec quote",
                "source_sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
            }
        })
        doc["groups"].append({
            "id": "grp-1",
            "title": "Group 1",
            "unit_refs": ["u-test-01"],
        })
        raw_bytes = json.dumps(doc).encode("utf-8")

        res = load_document(raw_bytes, engine=engine)
        assert res.success is True
        assert res.error_type == ErrorType.NONE
        assert res.doc is not None
        assert res.structure_state == StructureState.VALID

    @pytest.mark.parametrize("bad_format", [
        "paralleldoc-v2",
        "ParallelDoc",
        "PARALLELDOC",
        "paralleldoc-3",
        "paralleldoc ",
        " paralleldoc",
        "",
        None,
        123,
        False,
        ["paralleldoc"],
        {"name": "paralleldoc"},
    ])
    def test_reject_invalid_format_field(
        self,
        make_minimal_v3_doc: Callable[[], Dict[str, Any]],
        bad_format: Any
    ):
        """format field must be strictly 'paralleldoc'."""
        doc = make_minimal_v3_doc()
        if bad_format is None:
            del doc["format"]
        else:
            doc["format"] = bad_format
        raw_bytes = json.dumps(doc).encode("utf-8")

        res = load_document(raw_bytes)
        assert res.success is False
        assert res.error_type == ErrorType.REJECTED_UNSUPPORTED
        assert res.diagnostic_message == REJECTION_DIAGNOSTIC_MESSAGE
        assert res.doc is None

    @pytest.mark.parametrize("bad_version", [
        "2.1",
        "2.0",
        "3",
        "3.0.0",
        "4.0",
        "3.1",
        "v3.0",
        " 3.0",
        "3.0 ",
        3.0,
        3,
        "",
        None,
        False,
        ["3.0"],
    ])
    def test_reject_invalid_version_field(
        self,
        make_minimal_v3_doc: Callable[[], Dict[str, Any]],
        bad_version: Any
    ):
        """version field must be strictly string '3.0'."""
        doc = make_minimal_v3_doc()
        if bad_version is None:
            del doc["version"]
        else:
            doc["version"] = bad_version
        raw_bytes = json.dumps(doc).encode("utf-8")

        res = load_document(raw_bytes)
        assert res.success is False
        assert res.error_type == ErrorType.REJECTED_UNSUPPORTED
        assert res.diagnostic_message == REJECTION_DIAGNOSTIC_MESSAGE
        assert res.doc is None

    def test_reject_empty_dict(self):
        """Empty JSON object {} has no format or version and must be rejected."""
        res = load_document(b"{}")
        assert res.success is False
        assert res.error_type == ErrorType.REJECTED_UNSUPPORTED
        assert res.diagnostic_message == REJECTION_DIAGNOSTIC_MESSAGE
        assert res.doc is None


# =============================================================================
# 2. NON-DICT ROOT TYPES (§9, AC-02)
# =============================================================================

class TestAdversarialRootTypes:
    """Stress-test rejection of non-object JSON roots."""

    @pytest.mark.parametrize("raw_input,desc", [
        (b"[]", "Empty array"),
        (b"[1, 2, 3]", "Integer array"),
        (b'["paralleldoc", "3.0"]', "String array with v3 tokens"),
        (b'[{"format": "paralleldoc", "version": "3.0"}]', "Array containing valid v3 doc"),
        (b"true", "Boolean true"),
        (b"false", "Boolean false"),
        (b"null", "Null value"),
        (b"0", "Integer zero"),
        (b"42", "Integer 42"),
        (b"-100", "Negative integer"),
        (b"3.1415926535", "Float number"),
        (b"1e10", "Scientific notation number"),
        (b'"paralleldoc"', "Bare string"),
        (b'"{\\"format\\": \\"paralleldoc\\", \\"version\\": \\"3.0\\"}"', "JSON-encoded string"),
    ])
    def test_non_dict_root_rejected_with_exact_diagnostic(self, raw_input: bytes, desc: str):
        """Every non-dict root must produce REJECTED_UNSUPPORTED with exact diagnostic message."""
        res = load_document(raw_input)
        assert res.success is False, f"Failed for {desc}"
        assert res.error_type == ErrorType.REJECTED_UNSUPPORTED, f"Failed for {desc}"
        assert res.diagnostic_message == REJECTION_DIAGNOSTIC_MESSAGE, f"Failed for {desc}"
        assert res.doc is None, f"Failed for {desc}"
        assert res.structure_state == StructureState.INVALID
        assert res.integrity_state == IntegrityState.COMPUTED
        assert res.raw_sha256 == hashlib.sha256(raw_input).hexdigest().lower()
        assert res.raw_preview is not None
        assert res.raw_preview.text is not None


# =============================================================================
# 3. CORRUPTED JSON SYNTAX & LINE/COL LOCATOR STRESS (§9, F08, AC-02)
# =============================================================================

class TestAdversarialSyntaxStress:
    """Stress-test JSON parse errors with nested braces, strings, and line/col accuracy."""

    def test_syntax_error_nested_braces_and_brackets(self):
        """Syntax error deeply inside nested braces and arrays."""
        corrupted = b"""{
  "format": "paralleldoc",
  "version": "3.0",
  "metadata": {
    "nested_level_1": {
      "nested_level_2": [
        1,
        2,
        {
          "bad_syntax_here": [
            "valid string",
            "another string",
            BROKEN_TOKEN_UNQUOTED
          ]
        }
      ]
    }
  }
}"""
        res = load_document(corrupted)
        assert res.success is False
        assert res.error_type == ErrorType.PARSE_ERROR
        assert res.line is not None and res.line == 13
        assert res.column is not None and res.column >= 1
        assert res.snippet is not None
        assert "^" in res.snippet
        assert "BROKEN_TOKEN_UNQUOTED" in res.snippet

    def test_syntax_error_escaped_quotes_and_braces_in_strings(self):
        """String containing escaped quotes and braces prior to a syntax error."""
        corrupted = b"""{
  "format": "paralleldoc",
  "version": "3.0",
  "metadata": {
    "title": "String with \\" escaped \\" quotes { and } braces [ and ] brackets",
    "notes": "Another line with \\\\ escaped backslash and \\" inner quote"
  },
  "trailing_comma_error": true,
}"""
        res = load_document(corrupted)
        assert res.success is False
        assert res.error_type == ErrorType.PARSE_ERROR
        assert res.line is not None and res.line == 9
        assert "^" in res.snippet

    def test_syntax_error_unclosed_string_at_end(self):
        """Unclosed string literal at end of file."""
        corrupted = b'{\n  "format": "paralleldoc",\n  "version": "3.0",\n  "unclosed": "missing quote\n}'
        res = load_document(corrupted)
        assert res.success is False
        assert res.error_type == ErrorType.PARSE_ERROR
        assert res.line is not None and res.line >= 4

    def test_syntax_error_unclosed_brace_at_eof(self):
        """Unclosed top-level object."""
        corrupted = b'{\n  "format": "paralleldoc",\n  "version": "3.0"'
        res = load_document(corrupted)
        assert res.success is False
        assert res.error_type == ErrorType.PARSE_ERROR
        assert res.line is not None

    def test_syntax_error_control_chars_in_string(self):
        """Unescaped newline inside string literal (RFC 8259 violation)."""
        corrupted = b'{\n  "format": "paralleldoc",\n  "version": "3.0",\n  "title": "Line 1\nLine 2"\n}'
        res = load_document(corrupted)
        assert res.success is False
        assert res.error_type == ErrorType.PARSE_ERROR
        assert res.line is not None and res.line == 4

    def test_utf8_decode_error_corrupted_multibyte(self):
        """Corrupted multibyte UTF-8 sequence triggers UTF8_DECODE_ERROR safely."""
        # \xc3\x28 is an invalid 2-byte sequence
        bad_utf8 = b'{\n  "format": "paralleldoc",\n  "version": "3.0",\n  "broken": "\xc3\x28"\n}'
        res = load_document(bad_utf8)
        assert res.success is False
        assert res.error_type == ErrorType.UTF8_DECODE_ERROR
        assert "Ошибка декодирования UTF-8" in res.diagnostic_message
        assert res.raw_preview is not None
        assert res.raw_preview.text is not None


# =============================================================================
# 4. MALFORMED DETACHED MANIFESTS (§8, AC-26)
# =============================================================================

class TestAdversarialDetachedManifest:
    """Stress-test detached manifest verification against malformed structures."""

    def test_manifest_reject_uppercase_hex(
        self,
        make_minimal_v3_doc: Callable[[], Dict[str, Any]],
        engine: IntegrityEngine
    ):
        """AC-26 / Spec §8 line 446: expected_sha256 pattern is ^[a-f0-9]{64}$ (strictly lowercase).
        Uppercase hex MUST be rejected as invalid manifest by schema."""
        doc = make_minimal_v3_doc()
        raw_bytes = json.dumps(doc).encode("utf-8")
        actual_hash = compute_raw_sha256(raw_bytes)
        uppercase_hash = actual_hash.upper()

        manifest = {
            "format": "paralleldoc-integrity-1",
            "algorithm": "SHA-256",
            "scope": "raw-bytes",
            "expected_sha256": uppercase_hash,
        }
        res = verify_manifest(raw_bytes, manifest, engine=engine)
        assert res.is_valid_manifest is False, (
            "Vulnerability / Flaw: Manifest with uppercase expected_sha256 was accepted, "
            "violating manifest.schema.json pattern ^[a-f0-9]{64}$"
        )
        assert res.status == ManifestMatchStatus.INVALID_MANIFEST

    def test_manifest_reject_mixed_case_hex(
        self,
        make_minimal_v3_doc: Callable[[], Dict[str, Any]],
        engine: IntegrityEngine
    ):
        """Mixed-case hex in expected_sha256 MUST be rejected."""
        doc = make_minimal_v3_doc()
        raw_bytes = json.dumps(doc).encode("utf-8")
        actual_hash = compute_raw_sha256(raw_bytes)
        mixed_hash = actual_hash[:32].upper() + actual_hash[32:].lower()

        manifest = {
            "format": "paralleldoc-integrity-1",
            "algorithm": "SHA-256",
            "scope": "raw-bytes",
            "expected_sha256": mixed_hash,
        }
        res = verify_manifest(raw_bytes, manifest, engine=engine)
        assert res.is_valid_manifest is False
        assert res.status == ManifestMatchStatus.INVALID_MANIFEST

    @pytest.mark.parametrize("bad_hash,desc", [
        ("a" * 63, "63 chars (too short)"),
        ("a" * 65, "65 chars (too long)"),
        ("a" * 32, "32 chars (MD5 length)"),
        ("", "Empty string"),
        ("g" * 64, "Non-hex character 'g'"),
        ("z" * 64, "Non-hex character 'z'"),
        (" " * 64, "64 spaces"),
        (" " + "a" * 63, "Leading space"),
        ("a" * 63 + " ", "Trailing space"),
        ("0x" + "a" * 62, "0x hex prefix"),
        ("a" * 63 + "\n", "Trailing newline"),
    ])
    def test_manifest_reject_malformed_hashes(
        self,
        make_minimal_v3_doc: Callable[[], Dict[str, Any]],
        engine: IntegrityEngine,
        bad_hash: str,
        desc: str
    ):
        """Manifests with non-64 lowercase hex hashes must be rejected."""
        doc = make_minimal_v3_doc()
        raw_bytes = json.dumps(doc).encode("utf-8")

        manifest = {
            "format": "paralleldoc-integrity-1",
            "algorithm": "SHA-256",
            "scope": "raw-bytes",
            "expected_sha256": bad_hash,
        }
        res = verify_manifest(raw_bytes, manifest, engine=engine)
        assert res.is_valid_manifest is False, f"Failed for {desc}"
        assert res.status == ManifestMatchStatus.INVALID_MANIFEST, f"Failed for {desc}"

    @pytest.mark.parametrize("extra_key,extra_val", [
        ("signature", "unauthorized_sig"),
        ("created_at", "2026-09-07T00:00:00Z"),
        ("author", "Eve"),
        ("comment", "Manifest note"),
        ("extra_properties", {"allowed": False}),
    ])
    def test_manifest_reject_additional_properties(
        self,
        make_minimal_v3_doc: Callable[[], Dict[str, Any]],
        engine: IntegrityEngine,
        extra_key: str,
        extra_val: Any
    ):
        """manifest.schema.json has additionalProperties: false. Extra fields MUST be rejected."""
        doc = make_minimal_v3_doc()
        raw_bytes = json.dumps(doc).encode("utf-8")
        actual_hash = compute_raw_sha256(raw_bytes)

        manifest = {
            "format": "paralleldoc-integrity-1",
            "algorithm": "SHA-256",
            "scope": "raw-bytes",
            "expected_sha256": actual_hash,
            extra_key: extra_val,
        }
        res = verify_manifest(raw_bytes, manifest, engine=engine)
        assert res.is_valid_manifest is False, f"Failed for extra property {extra_key}"
        assert res.status == ManifestMatchStatus.INVALID_MANIFEST

    @pytest.mark.parametrize("bad_algo", [
        "sha-256",  # lowercase forbidden
        "SHA256",
        "SHA-512",
        "MD5",
        "BLAKE3",
        "",
        None,
        123,
    ])
    def test_manifest_reject_wrong_algorithm(
        self,
        make_minimal_v3_doc: Callable[[], Dict[str, Any]],
        engine: IntegrityEngine,
        bad_algo: Any
    ):
        """algorithm must be const 'SHA-256'."""
        doc = make_minimal_v3_doc()
        raw_bytes = json.dumps(doc).encode("utf-8")
        actual_hash = compute_raw_sha256(raw_bytes)

        manifest = {
            "format": "paralleldoc-integrity-1",
            "algorithm": bad_algo,
            "scope": "raw-bytes",
            "expected_sha256": actual_hash,
        }
        res = verify_manifest(raw_bytes, manifest, engine=engine)
        assert res.is_valid_manifest is False
        assert res.status == ManifestMatchStatus.INVALID_MANIFEST

    @pytest.mark.parametrize("bad_scope", [
        "normalized-text",
        "raw_bytes",  # underscore forbidden
        "raw-byte",
        "canonical-json",
        "bytes",
        "",
        None,
        False,
    ])
    def test_manifest_reject_wrong_scope(
        self,
        make_minimal_v3_doc: Callable[[], Dict[str, Any]],
        engine: IntegrityEngine,
        bad_scope: Any
    ):
        """scope must be const 'raw-bytes'."""
        doc = make_minimal_v3_doc()
        raw_bytes = json.dumps(doc).encode("utf-8")
        actual_hash = compute_raw_sha256(raw_bytes)

        manifest = {
            "format": "paralleldoc-integrity-1",
            "algorithm": "SHA-256",
            "scope": bad_scope,
            "expected_sha256": actual_hash,
        }
        res = verify_manifest(raw_bytes, manifest, engine=engine)
        assert res.is_valid_manifest is False
        assert res.status == ManifestMatchStatus.INVALID_MANIFEST

    @pytest.mark.parametrize("bad_format", [
        "paralleldoc-integrity-0",
        "paralleldoc-integrity-2",
        "paralleldoc",
        "paralleldoc-integrity-1 ",
        "",
        None,
    ])
    def test_manifest_reject_wrong_format(
        self,
        make_minimal_v3_doc: Callable[[], Dict[str, Any]],
        engine: IntegrityEngine,
        bad_format: Any
    ):
        """format must be const 'paralleldoc-integrity-1'."""
        doc = make_minimal_v3_doc()
        raw_bytes = json.dumps(doc).encode("utf-8")
        actual_hash = compute_raw_sha256(raw_bytes)

        manifest = {
            "format": bad_format,
            "algorithm": "SHA-256",
            "scope": "raw-bytes",
            "expected_sha256": actual_hash,
        }
        res = verify_manifest(raw_bytes, manifest, engine=engine)
        assert res.is_valid_manifest is False
        assert res.status == ManifestMatchStatus.INVALID_MANIFEST

    @pytest.mark.parametrize("missing_prop", ["format", "algorithm", "scope", "expected_sha256"])
    def test_manifest_reject_missing_required_property(
        self,
        make_minimal_v3_doc: Callable[[], Dict[str, Any]],
        engine: IntegrityEngine,
        missing_prop: str
    ):
        """Manifest missing any required field must be rejected."""
        doc = make_minimal_v3_doc()
        raw_bytes = json.dumps(doc).encode("utf-8")
        actual_hash = compute_raw_sha256(raw_bytes)

        manifest = {
            "format": "paralleldoc-integrity-1",
            "algorithm": "SHA-256",
            "scope": "raw-bytes",
            "expected_sha256": actual_hash,
        }
        del manifest[missing_prop]
        res = verify_manifest(raw_bytes, manifest, engine=engine)
        assert res.is_valid_manifest is False
        assert res.status == ManifestMatchStatus.INVALID_MANIFEST


# =============================================================================
# 5. MANIFEST TARGET BINDING & MULTI-ERROR STATES (§8, §11, AC-26, AC-28)
# =============================================================================

class TestAdversarialManifestBindingAndMultiError:
    """Stress-test target binding (document_id, revision) and simultaneous multi-error states."""

    def test_manifest_target_binding_precedence_over_hash_mismatch(
        self,
        make_minimal_v3_doc: Callable[[], Dict[str, Any]],
        engine: IntegrityEngine
    ):
        """If manifest document_id does NOT match active doc, status is DIFFERENT_DOCUMENT
        even if the hash ALSO differs, and active document remains in 'computed' integrity state."""
        doc = make_minimal_v3_doc()
        raw_bytes = json.dumps(doc).encode("utf-8")

        manifest = {
            "format": "paralleldoc-integrity-1",
            "algorithm": "SHA-256",
            "scope": "raw-bytes",
            "expected_sha256": "0" * 64,  # Also mismatched!
            "document_id": "other-doc-id-entirely",
            "revision": doc["metadata"]["revision"],
        }
        res = load_document(raw_bytes, manifest_input=manifest, engine=engine)
        assert res.success is True
        assert res.manifest_result is not None
        assert res.manifest_result.status == ManifestMatchStatus.DIFFERENT_DOCUMENT
        # Active document integrity state is computed, not mismatch, because manifest was for another doc
        assert res.integrity_state == IntegrityState.COMPUTED

    def test_manifest_target_revision_mismatch_with_matching_hash(
        self,
        make_minimal_v3_doc: Callable[[], Dict[str, Any]],
        engine: IntegrityEngine
    ):
        """If manifest revision differs from document metadata, status is DIFFERENT_DOCUMENT."""
        doc = make_minimal_v3_doc()
        raw_bytes = json.dumps(doc).encode("utf-8")
        actual_hash = compute_raw_sha256(raw_bytes)

        manifest = {
            "format": "paralleldoc-integrity-1",
            "algorithm": "SHA-256",
            "scope": "raw-bytes",
            "expected_sha256": actual_hash,
            "document_id": doc["metadata"]["document_id"],
            "revision": "rev-999-mismatched",
        }
        res = load_document(raw_bytes, manifest_input=manifest, engine=engine)
        assert res.success is True
        assert res.manifest_result.status == ManifestMatchStatus.DIFFERENT_DOCUMENT
        assert res.integrity_state == IntegrityState.COMPUTED

    def test_simultaneous_referential_error_and_manifest_mismatch(
        self,
        make_minimal_v3_doc: Callable[[], Dict[str, Any]],
        engine: IntegrityEngine
    ):
        """AC-28: Referential error (dangling author_ref) + Manifest hash mismatch
        occur simultaneously without masking each other."""
        doc = make_minimal_v3_doc()
        doc["metadata"]["author_refs"] = ["auth-nonexistent"]  # Referential error!
        raw_bytes = json.dumps(doc).encode("utf-8")

        manifest = {
            "format": "paralleldoc-integrity-1",
            "algorithm": "SHA-256",
            "scope": "raw-bytes",
            "expected_sha256": "f" * 64,  # SHA mismatch!
            "document_id": doc["metadata"]["document_id"],
            "revision": doc["metadata"]["revision"],
        }
        res = load_document(raw_bytes, manifest_input=manifest, engine=engine)

        assert res.success is False
        assert res.error_type == ErrorType.REFERENTIAL_INTEGRITY_ERROR
        assert res.structure_state == StructureState.INVALID
        assert res.integrity_state == IntegrityState.MISMATCH
        assert res.manifest_result.status == ManifestMatchStatus.MISMATCH
        assert any(i.code == "ERR_DANGLING_AUTHOR_REF" for i in res.issues)

    def test_simultaneous_schema_violation_and_manifest_matched(
        self,
        make_minimal_v3_doc: Callable[[], Dict[str, Any]],
        engine: IntegrityEngine
    ):
        """AC-28: Structural schema violation (missing profiles collection) + Manifest hash MATCHED.
        Digest consistency does NOT mask structural failure."""
        doc = make_minimal_v3_doc()
        del doc["profiles"]  # Schema violation!
        raw_bytes = json.dumps(doc).encode("utf-8")
        actual_hash = compute_raw_sha256(raw_bytes)

        manifest = {
            "format": "paralleldoc-integrity-1",
            "algorithm": "SHA-256",
            "scope": "raw-bytes",
            "expected_sha256": actual_hash,
            "document_id": doc["metadata"]["document_id"],
            "revision": doc["metadata"]["revision"],
        }
        res = load_document(raw_bytes, manifest_input=manifest, engine=engine)

        assert res.success is False
        assert res.error_type == ErrorType.SCHEMA_VIOLATION
        assert res.structure_state == StructureState.INVALID
        assert res.integrity_state == IntegrityState.MATCHED
        assert res.manifest_result.status == ManifestMatchStatus.MATCHED

    def test_simultaneous_format_rejection_and_manifest_provided(
        self,
        engine: IntegrityEngine
    ):
        """When document is rejected at format guard (legacy columns), format rejection takes precedence,
        doc is None, and manifest does not promote document."""
        legacy_bytes = b'{"format": "paralleldoc", "version": "3.0", "columns": []}'
        actual_hash = compute_raw_sha256(legacy_bytes)

        manifest = {
            "format": "paralleldoc-integrity-1",
            "algorithm": "SHA-256",
            "scope": "raw-bytes",
            "expected_sha256": actual_hash,
        }
        res = load_document(legacy_bytes, manifest_input=manifest, engine=engine)
        assert res.success is False
        assert res.error_type == ErrorType.REJECTED_UNSUPPORTED
        assert res.diagnostic_message == REJECTION_DIAGNOSTIC_MESSAGE
        assert res.doc is None


# =============================================================================
# 6. ZERO AUTO-MIGRATION & ZERO SILENT FALLBACK (§9, F09, AC-02)
# =============================================================================

class TestAdversarialZeroAutoMigration:
    """Stress-test prohibition of automatic migration and silent fallback under any input."""

    def test_legacy_v21_three_columns_never_migrated(self):
        """Legacy v2.1 document with 3 columns (source, model, analysis) must never be converted."""
        legacy_3col = """{
  "metadata": { "title": "Old Spec 2.1 Doc", "revision": "1" },
  "columns": [
    { "key": "col1", "title": "Оригинал" },
    { "key": "col2", "title": "Смысловой перевод" },
    { "key": "col3", "title": "Анализ и риски" }
  ],
  "items": [
    {
      "id": "row-1",
      "col1": "Clause 1.1 Original tender text",
      "col2": "Translated meaning of clause 1.1",
      "col3": "Risk assessment: Penalty clause high"
    }
  ]
}""".encode("utf-8")
        res = load_document(legacy_3col)
        assert res.success is False
        assert res.error_type == ErrorType.REJECTED_UNSUPPORTED
        assert res.diagnostic_message == REJECTION_DIAGNOSTIC_MESSAGE
        assert res.doc is None
        assert res.stats.get("units_count", 0) == 0

    def test_empty_input_never_substitutes_demo(self):
        """Empty input file must never substitute a demo document."""
        res = load_document(b"")
        assert res.success is False
        assert res.error_type == ErrorType.EMPTY_INPUT
        assert res.diagnostic_message == REJECTION_DIAGNOSTIC_MESSAGE
        assert res.doc is None
        assert res.stats.get("units_count", 0) == 0

    def test_corrupted_input_never_substitutes_demo(self):
        """Corrupted JSON must never substitute a demo document."""
        res = load_document(b'{"corrupted": true, broken}')
        assert res.success is False
        assert res.error_type == ErrorType.PARSE_ERROR
        assert res.doc is None
        assert res.stats.get("units_count", 0) == 0
