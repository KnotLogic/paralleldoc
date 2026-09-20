"""
ParallelDoc 3.0 (r2 / V3-ONLY) — Test Suite for V3 Loader, Raw SHA-256 & Rejection.
Strict compliance with Spec r2 §7, §8, §9, §11 (F06-F09, AC-02, AC-25, AC-26, AC-28).

Comprehensive test suite covering Tier 1 (Normative Features) and Tier 2 (Boundaries & Edge Cases).
"""

import hashlib
import json
from pathlib import Path
import subprocess
import sys
from typing import Any, Callable, Dict
import pytest

from loader import (
    ErrorType,
    IntegrityState,
    ManifestMatchStatus,
    REJECTION_DIAGNOSTIC_MESSAGE,
    StructureState,
    UTF8_BOM,
    compute_file_raw_sha256,
    compute_raw_sha256,
    generate_error_snippet,
    generate_raw_preview,
    load_document,
    locate_error_pointer,
    verify_manifest,
)
from validator import IntegrityEngine, IssueSeverity


# =============================================================================
# TIER 1: Normative Feature Verification (F06, F07, F08, F09, AC-02, AC-25, AC-26)
# =============================================================================


def test_raw_sha256_exact_bytes():
    """F06 / AC-25: SHA-256 must be computed over exact raw binary bytes without modification."""
    test_bytes = b'{"format": "paralleldoc", "version": "3.0"}'
    expected = hashlib.sha256(test_bytes).hexdigest().lower()
    computed = compute_raw_sha256(test_bytes)

    assert computed == expected
    assert len(computed) == 64
    assert computed.islower()

    # Distinct bytes produce distinct digests
    other_bytes = b'{"format": "paralleldoc", "version": "3.0" }'
    assert compute_raw_sha256(test_bytes) != compute_raw_sha256(other_bytes)


def test_raw_sha256_preserves_utf8_bom():
    """F06 / AC-25 / Spec §7 line 186: UTF-8 BOM (0xEF, 0xBB, 0xBF) is part of raw digest."""
    raw_content = b'{"format": "paralleldoc", "version": "3.0"}'
    raw_with_bom = UTF8_BOM + raw_content

    hash_without_bom = compute_raw_sha256(raw_content)
    hash_with_bom = compute_raw_sha256(raw_with_bom)

    assert hash_without_bom != hash_with_bom
    assert hash_with_bom == hashlib.sha256(raw_with_bom).hexdigest().lower()

    # When loaded, BOM is preserved in raw_sha256 and detected
    res = load_document(raw_with_bom)
    assert res.has_bom is True
    assert res.raw_sha256 == hash_with_bom


def test_raw_sha256_zero_crlf_lf_normalization():
    """F06 / AC-25 / Spec §7 line 186: Zero newline normalization before hashing."""
    lf_bytes = b'{\n  "format": "paralleldoc",\n  "version": "3.0"\n}'
    crlf_bytes = b'{\r\n  "format": "paralleldoc",\r\n  "version": "3.0"\r\n}'

    lf_hash = compute_raw_sha256(lf_bytes)
    crlf_hash = compute_raw_sha256(crlf_bytes)

    assert lf_hash != crlf_hash
    assert lf_hash == hashlib.sha256(lf_bytes).hexdigest().lower()
    assert crlf_hash == hashlib.sha256(crlf_bytes).hexdigest().lower()


def test_raw_sha256_empty_bytes():
    """F06 / AC-25 / Spec §9: Empty bytes yield standard empty digest and trigger rejection."""
    empty_bytes = b""
    expected_empty_hash = hashlib.sha256(b"").hexdigest().lower()
    assert compute_raw_sha256(empty_bytes) == expected_empty_hash

    res = load_document(empty_bytes)
    assert res.success is False
    assert res.error_type == ErrorType.EMPTY_INPUT
    assert res.diagnostic_message == REJECTION_DIAGNOSTIC_MESSAGE
    assert res.raw_sha256 == expected_empty_hash
    assert res.byte_length == 0


def test_v3_guard_reject_legacy_v21_columns():
    """F07 / AC-02 / Spec §9 line 460: Legacy v2.1 with columns rejected with exact message."""
    legacy_json = b"""{
        "metadata": { "title": "Legacy Doc" },
        "columns": [
            { "key": "col1", "title": "Source" },
            { "key": "col2", "title": "Model" }
        ],
        "items": []
    }"""
    res = load_document(legacy_json)

    assert res.success is False
    assert res.error_type == ErrorType.REJECTED_UNSUPPORTED
    assert res.diagnostic_message == REJECTION_DIAGNOSTIC_MESSAGE
    assert res.doc is None  # F09: absolute prohibition of auto-migration
    assert res.structure_state == StructureState.INVALID
    assert res.raw_preview is not None
    assert "columns" in (res.snippet or res.raw_preview.snippet or "")


def test_v3_guard_reject_legacy_v21_items():
    """F07 / AC-02 / Spec §9 line 460: Legacy items rejected with exact diagnostic message."""
    legacy_items_json = b"""{
        "metadata": { "title": "Doc with Items" },
        "items": [
            { "id": "it-1", "col1": "Text A", "col2": "Text B" }
        ]
    }"""
    res = load_document(legacy_items_json)

    assert res.success is False
    assert res.error_type == ErrorType.REJECTED_UNSUPPORTED
    assert res.diagnostic_message == REJECTION_DIAGNOSTIC_MESSAGE
    assert res.doc is None


def test_v3_guard_reject_spoofed_v3_with_columns():
    """F07 / F09 / Spec §9 line 461: Hybrid format/version with legacy columns strictly rejected."""
    spoofed = b"""{
        "format": "paralleldoc",
        "version": "3.0",
        "metadata": { "document_id": "spoofed-01" },
        "columns": [{ "key": "col1" }],
        "items": [{ "id": "1" }]
    }"""
    res = load_document(spoofed)

    assert res.success is False
    assert res.error_type == ErrorType.REJECTED_UNSUPPORTED
    assert res.diagnostic_message == REJECTION_DIAGNOSTIC_MESSAGE
    assert res.doc is None


def test_v3_guard_reject_missing_format():
    """F07 / AC-02 / Spec §9 line 460: Missing format field rejected with exact message."""
    missing_format = b"""{
        "version": "3.0",
        "metadata": { "document_id": "doc-01" }
    }"""
    res = load_document(missing_format)

    assert res.success is False
    assert res.error_type == ErrorType.REJECTED_UNSUPPORTED
    assert res.diagnostic_message == REJECTION_DIAGNOSTIC_MESSAGE
    assert res.doc is None


def test_v3_guard_reject_wrong_version():
    """F07 / AC-02 / Spec §9 line 460: Non-3.0 version rejected with exact message."""
    wrong_version_v2 = b"""{
        "format": "paralleldoc",
        "version": "2.1",
        "metadata": { "document_id": "doc-01" }
    }"""
    res_v2 = load_document(wrong_version_v2)
    assert res_v2.success is False
    assert res_v2.error_type == ErrorType.REJECTED_UNSUPPORTED
    assert res_v2.diagnostic_message == REJECTION_DIAGNOSTIC_MESSAGE

    wrong_version_v4 = b"""{
        "format": "paralleldoc",
        "version": "4.0",
        "metadata": { "document_id": "doc-01" }
    }"""
    res_v4 = load_document(wrong_version_v4)
    assert res_v4.success is False
    assert res_v4.error_type == ErrorType.REJECTED_UNSUPPORTED
    assert res_v4.diagnostic_message == REJECTION_DIAGNOSTIC_MESSAGE


def test_v3_guard_reject_non_object_json():
    """F07 / AC-02 / Spec §9: Non-dict JSON roots rejected with exact message."""
    array_json = b'["paralleldoc", "3.0", 123]'
    res_arr = load_document(array_json)
    assert res_arr.success is False
    assert res_arr.error_type == ErrorType.REJECTED_UNSUPPORTED
    assert res_arr.diagnostic_message == REJECTION_DIAGNOSTIC_MESSAGE

    scalar_json = b'"paralleldoc-v3"'
    res_scalar = load_document(scalar_json)
    assert res_scalar.success is False
    assert res_scalar.error_type == ErrorType.REJECTED_UNSUPPORTED
    assert res_scalar.diagnostic_message == REJECTION_DIAGNOSTIC_MESSAGE


def test_raw_preview_on_syntax_error():
    """F08 / AC-02 / Spec §9 line 460: Malformed JSON produces line/col coordinates and snippet."""
    corrupted_json = b"""{
        "format": "paralleldoc",
        "version": "3.0",
        "metadata": {
            "document_id": "doc-01"
        },
        "bad_trailing_comma": true,
    }"""
    res = load_document(corrupted_json)

    assert res.success is False
    assert res.error_type == ErrorType.PARSE_ERROR
    assert "Синтаксическая ошибка JSON" in (res.diagnostic_message or "")
    assert res.line is not None and res.line >= 1
    assert res.column is not None and res.column >= 1
    assert res.snippet is not None
    assert "^" in res.snippet
    assert res.raw_preview is not None
    assert res.raw_preview.text is not None


def test_raw_preview_on_rejection():
    """F08 / AC-02 / Spec §9 line 460: Rejection produces safe preview without executing content."""
    rejected_content = b"""{
        "metadata": { "note": "<script>alert(1)</script>" },
        "columns": [1, 2, 3]
    }"""
    res = load_document(rejected_content)

    assert res.success is False
    assert res.error_type == ErrorType.REJECTED_UNSUPPORTED
    assert res.raw_preview is not None
    assert "<script>alert(1)</script>" in res.raw_preview.text
    # Snippet points to offending 'columns' key
    assert res.line is not None
    assert res.column is not None


def test_prohibit_auto_migration():
    """F09 / AC-02 / Spec §1, §9: Zero auto-migration from v2.1 to v3.0."""
    legacy_file = b"""{
        "metadata": { "document_id": "v2-001" },
        "columns": [{ "key": "c1" }],
        "items": [{ "id": "it-1", "col1": "Source quote", "col2": "Analysis text" }]
    }"""
    res = load_document(legacy_file)

    assert res.success is False
    assert res.doc is None
    # No units should be synthesized or converted
    assert "units" not in res.stats or res.stats.get("units_count", 0) == 0


def test_prohibit_silent_fallback_to_demo():
    """F09 / AC-02 / Spec §9 line 463: Loading failure does not substitute demo document."""
    broken_bytes = b'{"not_paralleldoc": true}'
    res = load_document(broken_bytes)

    assert res.success is False
    assert res.doc is None
    assert res.error_type == ErrorType.REJECTED_UNSUPPORTED
    # Must not hold demo metadata
    assert res.stats.get("units_count", 0) == 0


def test_integrity_state_computed(make_minimal_v3_doc: Callable[[], Dict[str, Any]]):
    """AC-25 / Spec §7 line 186: Without expected hash, integrity state is 'computed'."""
    doc = make_minimal_v3_doc()
    raw_bytes = json.dumps(doc).encode("utf-8")

    res = load_document(raw_bytes)
    assert res.success is True
    assert res.structure_state == StructureState.VALID
    assert res.integrity_state == IntegrityState.COMPUTED
    assert res.raw_sha256 == hashlib.sha256(raw_bytes).hexdigest().lower()
    assert res.manifest_result is None


def test_integrity_state_matched(make_minimal_v3_doc: Callable[[], Dict[str, Any]]):
    """AC-25 / AC-26 / Spec §7, §8: Matching manifest or expected_sha256 yields 'matched'."""
    doc = make_minimal_v3_doc()
    raw_bytes = json.dumps(doc).encode("utf-8")
    actual_hash = compute_raw_sha256(raw_bytes)

    # 1. Via expected_sha256 string
    res_direct = load_document(raw_bytes, expected_sha256=actual_hash)
    assert res_direct.success is True
    assert res_direct.integrity_state == IntegrityState.MATCHED

    # 2. Via detached manifest
    manifest = {
        "format": "paralleldoc-integrity-1",
        "algorithm": "SHA-256",
        "scope": "raw-bytes",
        "expected_sha256": actual_hash,
        "document_id": doc["metadata"]["document_id"],
        "revision": doc["metadata"]["revision"],
    }
    res_man = load_document(raw_bytes, manifest_input=manifest)
    assert res_man.success is True
    assert res_man.integrity_state == IntegrityState.MATCHED
    assert res_man.manifest_result is not None
    assert res_man.manifest_result.status == ManifestMatchStatus.MATCHED
    assert res_man.manifest_result.message == "Хэш совпадает с эталоном"


def test_integrity_state_mismatch_single_byte(make_minimal_v3_doc: Callable[[], Dict[str, Any]]):
    """AC-25 / Spec §7 line 197: Altering single byte yields 'mismatch' state."""
    doc = make_minimal_v3_doc()
    raw_bytes = json.dumps(doc).encode("utf-8")
    correct_hash = compute_raw_sha256(raw_bytes)

    # Mutate 1 character in the JSON bytes
    mutated_bytes = raw_bytes.replace(b"Minimal", b"minimal")
    assert mutated_bytes != raw_bytes

    res = load_document(mutated_bytes, expected_sha256=correct_hash)
    assert res.integrity_state == IntegrityState.MISMATCH

    manifest = {
        "format": "paralleldoc-integrity-1",
        "algorithm": "SHA-256",
        "scope": "raw-bytes",
        "expected_sha256": correct_hash,
        "document_id": doc["metadata"]["document_id"],
        "revision": doc["metadata"]["revision"],
    }
    res_manifest = load_document(mutated_bytes, manifest_input=manifest)
    assert res_manifest.integrity_state == IntegrityState.MISMATCH
    assert res_manifest.manifest_result.status == ManifestMatchStatus.MISMATCH


def test_manifest_different_document(make_minimal_v3_doc: Callable[[], Dict[str, Any]]):
    """AC-26 / Spec §8 line 453: Manifest with mismatched document_id or revision -> different_document."""
    doc = make_minimal_v3_doc()
    raw_bytes = json.dumps(doc).encode("utf-8")
    actual_hash = compute_raw_sha256(raw_bytes)

    # Mismatched document_id
    manifest_diff_id = {
        "format": "paralleldoc-integrity-1",
        "algorithm": "SHA-256",
        "scope": "raw-bytes",
        "expected_sha256": actual_hash,
        "document_id": "completely-different-doc-id",
        "revision": doc["metadata"]["revision"],
    }
    res_diff_id = load_document(raw_bytes, manifest_input=manifest_diff_id)
    assert res_diff_id.manifest_result.status == ManifestMatchStatus.DIFFERENT_DOCUMENT
    assert res_diff_id.integrity_state == IntegrityState.COMPUTED  # Doesn't verify active doc

    # Mismatched revision
    manifest_diff_rev = {
        "format": "paralleldoc-integrity-1",
        "algorithm": "SHA-256",
        "scope": "raw-bytes",
        "expected_sha256": actual_hash,
        "document_id": doc["metadata"]["document_id"],
        "revision": "rev-999-unrelated",
    }
    res_diff_rev = load_document(raw_bytes, manifest_input=manifest_diff_rev)
    assert res_diff_rev.manifest_result.status == ManifestMatchStatus.DIFFERENT_DOCUMENT
    assert res_diff_rev.integrity_state == IntegrityState.COMPUTED


def test_manifest_invalid_scope(make_minimal_v3_doc: Callable[[], Dict[str, Any]]):
    """AC-26 / Spec §8 line 445: Manifest with scope != 'raw-bytes' is rejected by schema."""
    doc = make_minimal_v3_doc()
    raw_bytes = json.dumps(doc).encode("utf-8")

    invalid_scope_manifest = {
        "format": "paralleldoc-integrity-1",
        "algorithm": "SHA-256",
        "scope": "normalized-text",  # Forbidden!
        "expected_sha256": compute_raw_sha256(raw_bytes),
    }
    res = load_document(raw_bytes, manifest_input=invalid_scope_manifest)
    assert res.manifest_result.is_valid_manifest is False
    assert res.manifest_result.status == ManifestMatchStatus.INVALID_MANIFEST
    assert res.integrity_state == IntegrityState.COMPUTED


# =============================================================================
# TIER 2: Boundaries, Edge Cases & Multi-Error Torture
# =============================================================================


def test_boundary_utf8_invalid_bytes():
    """Tier 2 / F06 / F08: Invalid UTF-8 bytes trigger UTF8_DECODE_ERROR safely."""
    invalid_bytes = b"\xff\xfe\xfd\x80\x81\x82 corrupted byte sequence"
    res = load_document(invalid_bytes)

    assert res.success is False
    assert res.error_type == ErrorType.UTF8_DECODE_ERROR
    assert "Ошибка декодирования UTF-8" in (res.diagnostic_message or "")
    assert res.structure_state == StructureState.INVALID
    assert res.raw_preview is not None
    # Ensure raw preview handled errors safely with replacement
    assert "\ufffd" in res.raw_preview.text


def test_boundary_raw_preview_truncation():
    """Tier 2 / F08: Oversized files (>5000 chars) are safely truncated with notification."""
    large_invalid_text = '{"format": "invalid", "data": "' + ("A" * 6000) + '"}'
    raw_bytes = large_invalid_text.encode("utf-8")
    res = load_document(raw_bytes)

    assert res.raw_preview is not None
    assert res.raw_preview.is_truncated is True
    assert res.raw_preview.total_length > 5000
    assert "Показаны первые" in res.raw_preview.text
    assert "Полный файл сохранен" in res.raw_preview.text


def test_boundary_simultaneous_mismatch_and_error():
    """Tier 2 / AC-28: Simultaneous SHA mismatch and schema error tracked without masking."""
    broken_schema_doc = {
        "format": "paralleldoc",
        "version": "3.0",
        "metadata": {
            "document_id": "doc-broken",
            "revision": "r1",
            "title": "Broken Doc",
            "author_refs": ["auth-1"],
        },
        # Missing authors, units, groups, visuals, assets, profiles!
    }
    raw_bytes = json.dumps(broken_schema_doc).encode("utf-8")
    actual_hash = compute_raw_sha256(raw_bytes)
    wrong_hash = "0" * 64

    manifest = {
        "format": "paralleldoc-integrity-1",
        "algorithm": "SHA-256",
        "scope": "raw-bytes",
        "expected_sha256": wrong_hash,
        "document_id": "doc-broken",
        "revision": "r1",
    }

    res = load_document(raw_bytes, manifest_input=manifest)

    # Both axes fail simultaneously and cleanly:
    assert res.structure_state == StructureState.INVALID
    assert res.integrity_state == IntegrityState.MISMATCH
    assert res.error_type == ErrorType.SCHEMA_VIOLATION
    assert res.manifest_result.status == ManifestMatchStatus.MISMATCH
    # Structural error does not hide SHA mismatch; SHA mismatch does not hide structural error
    assert any(i.code == "ERR_SCHEMA_V3_VIOLATION" for i in res.issues)


def test_manifest_invalid_algorithm(make_minimal_v3_doc: Callable[[], Dict[str, Any]]):
    """Tier 2 / AC-26: Manifest with algorithm != 'SHA-256' rejected."""
    doc = make_minimal_v3_doc()
    raw_bytes = json.dumps(doc).encode("utf-8")

    manifest = {
        "format": "paralleldoc-integrity-1",
        "algorithm": "SHA-512",  # Forbidden!
        "scope": "raw-bytes",
        "expected_sha256": compute_raw_sha256(raw_bytes),
    }
    res = load_document(raw_bytes, manifest_input=manifest)
    assert res.manifest_result.is_valid_manifest is False
    assert res.manifest_result.status == ManifestMatchStatus.INVALID_MANIFEST


def test_manifest_schema_additional_properties(make_minimal_v3_doc: Callable[[], Dict[str, Any]]):
    """Tier 2 / AC-26: Manifest rejects additional properties per Draft 2020-12 schema."""
    doc = make_minimal_v3_doc()
    raw_bytes = json.dumps(doc).encode("utf-8")

    manifest = {
        "format": "paralleldoc-integrity-1",
        "algorithm": "SHA-256",
        "scope": "raw-bytes",
        "expected_sha256": compute_raw_sha256(raw_bytes),
        "signature": "unauthorized_signature_block",  # Forbidden!
    }
    res = load_document(raw_bytes, manifest_input=manifest)
    assert res.manifest_result.is_valid_manifest is False
    assert res.manifest_result.status == ManifestMatchStatus.INVALID_MANIFEST


def test_clean_state_reset_simulation(
    make_minimal_v3_doc: Callable[[], Dict[str, Any]], make_rich_v3_doc: Callable[[], Dict[str, Any]]
):
    """Tier 2 / AC-02 / AC-26: Ingesting doc B cleanly resets doc A manifest state."""
    doc_a = make_minimal_v3_doc()
    bytes_a = json.dumps(doc_a).encode("utf-8")
    hash_a = compute_raw_sha256(bytes_a)

    manifest_a = {
        "format": "paralleldoc-integrity-1",
        "algorithm": "SHA-256",
        "scope": "raw-bytes",
        "expected_sha256": hash_a,
    }
    res_a = load_document(bytes_a, manifest_input=manifest_a)
    assert res_a.integrity_state == IntegrityState.MATCHED

    # Document B loaded independently
    doc_b = make_rich_v3_doc()
    bytes_b = json.dumps(doc_b).encode("utf-8")
    res_b = load_document(bytes_b)

    # State for B is cleanly computed; no residual manifest from A
    assert res_b.integrity_state == IntegrityState.COMPUTED
    assert res_b.manifest_result is None
    assert res_b.raw_sha256 == compute_raw_sha256(bytes_b)


def test_load_document_from_file(tmp_path: Path, make_minimal_v3_doc: Callable[[], Dict[str, Any]]):
    """Tier 2: Direct file loader from filesystem path."""
    doc = make_minimal_v3_doc()
    file_path = tmp_path / "valid_v3.json"
    file_path.write_bytes(json.dumps(doc).encode("utf-8"))

    res = compute_file_raw_sha256(file_path)
    assert len(res) == 64

    load_res = load_document(file_path.read_bytes())
    assert load_res.success is True
    assert load_res.raw_sha256 == res


def test_python_and_js_hash_parity():
    """Tier 2 / AC-21 / AC-25: Verify bit-for-bit SHA-256 parity between Python and JS loader."""
    test_vectors = [
        b"",
        b"ParallelDoc 3.0",
        UTF8_BOM + b'{"format": "paralleldoc", "version": "3.0"}',
        b"Line1\r\nLine2\r\nLine3",
        b"Line1\nLine2\nLine3",
        "Привет, мир! 🚀 12345".encode("utf-8"),
    ]

    for tv in test_vectors:
        py_hash = compute_raw_sha256(tv)

        # Run node script with hex input to verify JS implementation
        tv_hex = tv.hex()
        node_code = f"""
        const loader = require('./src/loader.js');
        const buf = Buffer.from('{tv_hex}', 'hex');
        const jsHash = loader.computeRawSha256Sync(new Uint8Array(buf));
        process.stdout.write(jsHash);
        """
        proc = subprocess.run(
            ["node", "-e", node_code],
            capture_output=True,
            text=True,
            cwd=str(Path(__file__).resolve().parent.parent),
            check=True,
        )
        js_hash = proc.stdout.strip()
        assert py_hash == js_hash, f"Hash mismatch for vector {tv!r}: py={py_hash}, js={js_hash}"


def test_js_loader_node_full_suite():
    """Tier 2: Verify full JavaScript loader execution in Node.js runtime."""
    js_test_path = Path(__file__).resolve().parent / "test_loader_node.cjs"
    proc = subprocess.run(
        ["node", str(js_test_path)],
        capture_output=True,
        text=True,
        cwd=str(Path(__file__).resolve().parent.parent),
    )
    assert proc.returncode == 0, f"Node.js test suite failed:\nSTDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}"
    assert "All Node.js loader tests PASSED successfully!" in proc.stdout
