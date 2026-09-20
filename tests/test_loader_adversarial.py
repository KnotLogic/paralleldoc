"""
Adversarial Stress Test Suite for ParallelDoc 3.0 Loader.
Focus: Raw SHA-256, BOM edge cases, mixed line endings, non-UTF-8, 0-byte, multi-megabyte, and byte immutability.
"""

import copy
import hashlib
import json
import os
import tempfile
import time
import pytest

from loader import (
    compute_raw_sha256,
    compute_file_raw_sha256,
    load_document,
    load_document_from_file,
    verify_manifest,
    generate_raw_preview,
    locate_error_pointer,
    generate_error_snippet,
    ErrorType,
    StructureState,
    IntegrityState,
    REJECTION_DIAGNOSTIC_MESSAGE,
    UTF8_BOM,
)


def get_minimal_valid_doc() -> dict:
    return {
        "format": "paralleldoc",
        "version": "3.0",
        "metadata": {
            "document_id": "doc-adv-001",
            "revision": "r1",
            "title": "Adversarial Test Doc",
            "author_refs": ["auth-1"],
        },
        "authors": [{"id": "auth-1", "kind": "human", "name": "Adversary"}],
        "units": [],
        "groups": [],
        "visuals": [],
        "assets": [],
        "profiles": [],
    }


# ==============================================================================
# 1. Byte Immutability & Non-Mutation Tests
# ==============================================================================

class TestByteImmutability:
    """Verify that hash calculation and loader pipeline NEVER mutate raw bytes or normalize newlines."""

    def test_compute_raw_sha256_does_not_mutate_bytes(self):
        original = b"{\r\n  \"format\": \"paralleldoc\",\r\n  \"version\": \"3.0\"\r\n}"
        bytes_copy = bytes(original)
        digest = compute_raw_sha256(original)
        assert original == bytes_copy, "Input bytes were mutated during hashing!"
        assert digest == hashlib.sha256(bytes_copy).hexdigest()

    def test_compute_raw_sha256_with_bytearray_not_mutated(self):
        original = bytearray(b"Hello \r\n World \n Mixed \r Endings")
        backup = bytearray(original)
        digest = compute_raw_sha256(original)
        assert original == backup, "bytearray was mutated during hashing!"
        assert digest == hashlib.sha256(backup).hexdigest()

    def test_load_document_does_not_mutate_input_buffer(self):
        doc = get_minimal_valid_doc()
        raw_bytes = json.dumps(doc, indent=2).replace("\n", "\r\n").encode("utf-8")
        backup = bytes(raw_bytes)

        result = load_document(raw_bytes)
        assert raw_bytes == backup, "load_document mutated input raw_bytes buffer!"
        assert result.raw_sha256 == hashlib.sha256(backup).hexdigest()

    def test_load_document_rejected_does_not_mutate_input_buffer(self):
        corrupted = b"\xef\xbb\xbf{\r\n  \"columns\": [], \"items\": []\r\n}"
        backup = bytes(corrupted)

        result = load_document(corrupted)
        assert corrupted == backup, "load_document mutated corrupted input buffer!"
        assert result.raw_sha256 == hashlib.sha256(backup).hexdigest()


# ==============================================================================
# 2. Line Ending Sensitivity & Zero-Normalization Tests
# ==============================================================================

class TestLineEndingPreservation:
    """Verify hash strictly differentiates line endings (no CRLF/LF normalization)."""

    def test_distinct_line_endings_produce_strictly_different_hashes(self):
        base_json = '{"format":"paralleldoc","version":"3.0","document_id":"test"}'
        
        lf_bytes = base_json.replace(",", ",\n").encode("utf-8")
        crlf_bytes = base_json.replace(",", ",\r\n").encode("utf-8")
        cr_bytes = base_json.replace(",", ",\r").encode("utf-8")
        mixed1 = base_json.replace(",", ",\r\n", 1).replace("3.0\"", "3.0\"\n").encode("utf-8")
        mixed2 = base_json.replace(",", ",\r", 1).replace("3.0\"", "3.0\"\r\n").encode("utf-8")

        hashes = {
            "lf": compute_raw_sha256(lf_bytes),
            "crlf": compute_raw_sha256(crlf_bytes),
            "cr": compute_raw_sha256(cr_bytes),
            "mixed1": compute_raw_sha256(mixed1),
            "mixed2": compute_raw_sha256(mixed2),
        }

        # All 5 hashes must be completely distinct!
        assert len(set(hashes.values())) == 5, f"Hash collision detected across line endings: {hashes}"

        # Each must exactly match hashlib
        assert hashes["lf"] == hashlib.sha256(lf_bytes).hexdigest()
        assert hashes["crlf"] == hashlib.sha256(crlf_bytes).hexdigest()
        assert hashes["cr"] == hashlib.sha256(cr_bytes).hexdigest()
        assert hashes["mixed1"] == hashlib.sha256(mixed1).hexdigest()
        assert hashes["mixed2"] == hashlib.sha256(mixed2).hexdigest()

    def test_cr_only_line_counting(self):
        # File with classic Mac \r line endings
        text = "{\r  \"format\": \"wrong\",\r  \"version\": \"3.0\"\r}"
        line, col = locate_error_pointer(text, r'"format"')
        # Note: locate_error_pointer uses split("\n"), so standalone \r without \n remains on line 1
        assert line == 1

    def test_strange_newlines_consecutive(self):
        doc = get_minimal_valid_doc()
        text = json.dumps(doc)
        weird = f"{text}\r\r\n\n\r\r".encode("utf-8")
        h = compute_raw_sha256(weird)
        assert h == hashlib.sha256(weird).hexdigest()
        res = load_document(weird)
        assert res.raw_sha256 == h


# ==============================================================================
# 3. Partial BOM & BOM Boundary Stress Tests
# ==============================================================================

class TestBOMStress:
    """Stress test partial, multiple, and malformed BOM markers."""

    def test_partial_bom_2_bytes(self):
        # \xef\xbb without \xbf
        doc = get_minimal_valid_doc()
        valid_json = json.dumps(doc).encode("utf-8")
        corrupted = b"\xef\xbb" + valid_json

        h = compute_raw_sha256(corrupted)
        assert h == hashlib.sha256(corrupted).hexdigest()

        res = load_document(corrupted)
        assert res.raw_sha256 == h
        assert res.has_bom is False, "Partial BOM must NOT be reported as has_bom=True"
        assert res.success is False
        assert res.error_type == ErrorType.UTF8_DECODE_ERROR
        assert res.structure_state == StructureState.INVALID
        assert res.integrity_state == IntegrityState.COMPUTED

    def test_partial_bom_1_byte(self):
        doc = get_minimal_valid_doc()
        corrupted = b"\xef" + json.dumps(doc).encode("utf-8")
        h = compute_raw_sha256(corrupted)
        res = load_document(corrupted)
        assert res.raw_sha256 == h
        assert res.has_bom is False
        assert res.error_type == ErrorType.UTF8_DECODE_ERROR

    def test_reversed_or_mutated_bom_bytes(self):
        # \xbb\xef\xbf, \xef\xbf\xbb, \xbf\xbb\xef
        doc = get_minimal_valid_doc()
        body = json.dumps(doc).encode("utf-8")
        for bad_bom in [b"\xbb\xef\xbf", b"\xef\xbf\xbb", b"\xbf\xbb\xef", b"\xef\xbb\x00"]:
            corrupted = bad_bom + body
            h = compute_raw_sha256(corrupted)
            res = load_document(corrupted)
            assert res.raw_sha256 == h
            assert res.has_bom is False
            assert res.success is False

    def test_exact_bom_alone_3_bytes(self):
        # Just the BOM: \xef\xbb\xbf
        bom_alone = b"\xef\xbb\xbf"
        h = compute_raw_sha256(bom_alone)
        assert h == hashlib.sha256(bom_alone).hexdigest()

        res = load_document(bom_alone)
        assert res.raw_sha256 == h
        assert res.has_bom is True
        assert res.byte_length == 3
        assert res.success is False
        # When BOM is stripped, remaining is empty -> PARSE_ERROR or EMPTY_INPUT
        # In loader.py: bytes_to_decode is b"", text is "", json.loads("") raises JSONDecodeError -> PARSE_ERROR
        assert res.error_type == ErrorType.PARSE_ERROR
        assert res.structure_state == StructureState.INVALID
        assert res.integrity_state == IntegrityState.COMPUTED

    def test_double_bom(self):
        # \xef\xbb\xbf\xef\xbb\xbf + valid doc
        doc = get_minimal_valid_doc()
        double_bom_bytes = b"\xef\xbb\xbf\xef\xbb\xbf" + json.dumps(doc).encode("utf-8")
        h = compute_raw_sha256(double_bom_bytes)
        assert h == hashlib.sha256(double_bom_bytes).hexdigest()

        res = load_document(double_bom_bytes)
        assert res.raw_sha256 == h
        assert res.has_bom is True
        # The first BOM is stripped, second BOM decoded as '\ufeff'
        # In JSON, leading '\ufeff' before '{' is illegal syntax per RFC 8259
        assert res.success is False
        assert res.error_type == ErrorType.PARSE_ERROR
        assert res.structure_state == StructureState.INVALID
        assert res.integrity_state == IntegrityState.COMPUTED

    def test_triple_bom(self):
        doc = get_minimal_valid_doc()
        triple = (b"\xef\xbb\xbf" * 3) + json.dumps(doc).encode("utf-8")
        h = compute_raw_sha256(triple)
        res = load_document(triple)
        assert res.raw_sha256 == h
        assert res.has_bom is True
        assert res.success is False
        assert res.error_type == ErrorType.PARSE_ERROR

    def test_bom_inside_json_string(self):
        # BOM bytes embedded inside a string value (valid UTF-8 character \ufeff)
        doc = get_minimal_valid_doc()
        doc["metadata"]["title"] = "Title with \ufeff BOM inside"
        raw_bytes = json.dumps(doc).encode("utf-8")
        
        h = compute_raw_sha256(raw_bytes)
        res = load_document(raw_bytes)
        assert res.raw_sha256 == h
        assert res.has_bom is False
        assert res.success is True
        assert res.doc["metadata"]["title"] == "Title with \ufeff BOM inside"


# ==============================================================================
# 4. Non-UTF-8 & Malformed Sequences
# ==============================================================================

class TestNonUTF8Sequences:
    """Verify robust handling of arbitrary non-UTF-8 bytes."""

    def test_lone_surrogate(self):
        # 0xED 0xA0 0x80 is U+D800 (high surrogate) - invalid in UTF-8
        bad_bytes = b'{"format":"paralleldoc","version":"3.0","text":"\xed\xa0\x80"}'
        h = compute_raw_sha256(bad_bytes)
        assert h == hashlib.sha256(bad_bytes).hexdigest()

        res = load_document(bad_bytes)
        assert res.raw_sha256 == h
        assert res.success is False
        assert res.error_type == ErrorType.UTF8_DECODE_ERROR
        assert res.raw_preview is not None
        assert not res.raw_preview.text.startswith("ERROR")

    def test_overlong_null(self):
        # 0xC0 0x80 is overlong encoding of 0x00
        bad_bytes = b'{"format":"paralleldoc","version":"3.0","val":"\xc0\x80"}'
        res = load_document(bad_bytes)
        assert res.success is False
        assert res.error_type == ErrorType.UTF8_DECODE_ERROR

    def test_truncated_4byte_sequence(self):
        # Emoji 0xF0 0x9F 0x98 (missing 4th byte)
        bad_bytes = b'{"format":"paralleldoc","version":"3.0","emoji":"\xf0\x9f\x98"}'
        res = load_document(bad_bytes)
        assert res.success is False
        assert res.error_type == ErrorType.UTF8_DECODE_ERROR

    def test_random_binary_garbage(self):
        # 1000 bytes of 0xFF
        garbage = b"\xff" * 1000
        h = compute_raw_sha256(garbage)
        res = load_document(garbage)
        assert res.raw_sha256 == h
        assert res.success is False
        assert res.error_type == ErrorType.UTF8_DECODE_ERROR
        assert res.structure_state == StructureState.INVALID
        assert res.integrity_state == IntegrityState.COMPUTED


# ==============================================================================
# 5. 0-Byte Input
# ==============================================================================

class TestZeroByteInput:
    """Verify 0-byte input handling."""

    def test_empty_bytes(self):
        empty = b""
        empty_sha = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
        assert compute_raw_sha256(empty) == empty_sha

        res = load_document(empty)
        assert res.raw_sha256 == empty_sha
        assert res.byte_length == 0
        assert res.has_bom is False
        assert res.success is False
        assert res.error_type == ErrorType.EMPTY_INPUT
        assert res.diagnostic_message == REJECTION_DIAGNOSTIC_MESSAGE
        assert res.structure_state == StructureState.INVALID
        assert res.integrity_state == IntegrityState.COMPUTED


# ==============================================================================
# 6. Multi-Megabyte Stress Tests
# ==============================================================================

class TestMultiMegabyteStress:
    """Stress test scaling and multi-megabyte payloads."""

    def test_1mb_valid_document(self):
        doc = get_minimal_valid_doc()
        # Add 1 MB of characters in title
        large_text = "А" * 500_000  # 1_000_000 UTF-8 bytes
        doc["metadata"]["title"] = f"Title {large_text}"
        raw_bytes = json.dumps(doc, ensure_ascii=False).encode("utf-8")
        assert len(raw_bytes) > 1_000_000, f"Expected > 1MB, got {len(raw_bytes)}"

        t0 = time.perf_counter()
        h = compute_raw_sha256(raw_bytes)
        t_hash = time.perf_counter() - t0

        assert h == hashlib.sha256(raw_bytes).hexdigest()
        assert t_hash < 0.5, f"1MB SHA-256 took too long: {t_hash:.3f}s"

        t0 = time.perf_counter()
        res = load_document(raw_bytes)
        t_load = time.perf_counter() - t0

        assert res.success is True
        assert res.raw_sha256 == h
        assert res.byte_length == len(raw_bytes)
        assert t_load < 2.0, f"1MB load_document took too long: {t_load:.3f}s"
        assert res.raw_preview.is_truncated is True

    def test_10mb_binary_stream(self):
        # 10 MB payload of cyclic patterns
        pattern = b"0123456789abcdef" * 64  # 1024 bytes
        large_bytes = pattern * (10 * 1024)  # 10 MB
        assert len(large_bytes) == 10 * 1024 * 1024

        t0 = time.perf_counter()
        h = compute_raw_sha256(large_bytes)
        t_hash = time.perf_counter() - t0

        assert h == hashlib.sha256(large_bytes).hexdigest()
        assert t_hash < 1.0, f"10MB hash took {t_hash:.3f}s"

        # load_document should handle it safely (reject as non-json / parse error)
        res = load_document(large_bytes)
        assert res.raw_sha256 == h
        assert res.success is False
        assert res.error_type in (ErrorType.PARSE_ERROR, ErrorType.REJECTED_UNSUPPORTED)
        assert res.raw_preview.is_truncated is True
        assert len(res.raw_preview.text) <= 5500


# ==============================================================================
# 7. Manifest Verification Adversarial Edge Cases
# ==============================================================================

class TestManifestAdversarial:
    """Stress test detached manifest validation with weird inputs."""

    def test_manifest_bom_preservation(self):
        doc_bytes = b'{"format":"paralleldoc","version":"3.0","metadata":{"document_id":"d1","revision":"r1"}}'
        doc_sha = compute_raw_sha256(doc_bytes)

        # Manifest with UTF-8 BOM
        manifest_data = {
            "format": "paralleldoc-integrity-1",
            "scope": "raw-bytes",
            "algorithm": "SHA-256",
            "expected_sha256": doc_sha,
            "document_id": "d1",
            "revision": "r1",
        }
        manifest_bytes = UTF8_BOM + json.dumps(manifest_data).encode("utf-8")

        res = verify_manifest(doc_bytes, manifest_bytes, doc_metadata={"document_id": "d1", "revision": "r1"})
        assert res.is_valid_manifest is True
        assert res.status.value == "matched"
        assert res.actual_sha256 == doc_sha

    def test_manifest_case_insensitivity_expected_sha(self):
        doc = get_minimal_valid_doc()
        doc_bytes = json.dumps(doc).encode("utf-8")
        doc_sha = compute_raw_sha256(doc_bytes)

        # Direct expected_sha256 parameter is case-insensitive for v3 docs
        res_direct = load_document(doc_bytes, expected_sha256=doc_sha.upper())
        assert res_direct.integrity_state == IntegrityState.MATCHED

        # In manifest, manifest.schema.json requires ^[a-f0-9]{64}$ (lowercase hex),
        # so uppercase hex properly triggers schema validation failure
        manifest_data = {
            "format": "paralleldoc-integrity-1",
            "scope": "raw-bytes",
            "algorithm": "SHA-256",
            "expected_sha256": doc_sha.upper(),
        }
        res = verify_manifest(doc_bytes, manifest_data)
        assert res.is_valid_manifest is False
        assert any("pattern" in issue.context.get("validator", "") or "expected_sha256" in issue.path for issue in res.issues)

    def test_manifest_invalid_scope_or_algo(self):
        doc_bytes = b'{"test":1}'
        # Scope != raw-bytes
        res1 = verify_manifest(doc_bytes, {
            "format": "paralleldoc-integrity-1",
            "scope": "normalized-text",
            "algorithm": "SHA-256",
            "expected_sha256": "0" * 64,
        })
        assert res1.is_valid_manifest is False
        assert any("scope" in issue.path or "raw-bytes" in issue.message for issue in res1.issues)

        # Algo != SHA-256
        res2 = verify_manifest(doc_bytes, {
            "format": "paralleldoc-integrity-1",
            "scope": "raw-bytes",
            "algorithm": "MD5",
            "expected_sha256": "0" * 64,
        })
        assert res2.is_valid_manifest is False
        assert any("algorithm" in issue.path or "SHA-256" in issue.message for issue in res2.issues)
