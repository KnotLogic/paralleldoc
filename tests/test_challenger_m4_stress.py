"""
tests/test_challenger_m4_stress.py — Adversarial Stress Test Suite for Milestone 4.
Author: challenger_m4 (Empirical Challenger)
Focus:
  1. Media corruption & spoofing (corrupted base64, truncated headers, bit flips, MIME spoofing)
  2. Animated WebP detection (VP8X bit 1 variations, multi-frame ANIM/ANMF payloads)
  3. Budget edge cases (8 MiB boundary, 32 MiB boundary, 50 assets boundary, 16 MP boundary, side 8192px)
  4. Locator attacks (Windows drive paths, UNC shares, file:, traversal .., encoded %2e%2e, credentials)
  5. Detached manifest permutations (valid, mismatched, invalid format/algo/scope, extra fields, bad SHA)
"""

import base64
import hashlib
from typing import Any, Dict, List
import pytest
import unicodedata

from validator import (
    IntegrityEngine,
    ValidationIssue,
    parse_image_header,
    validate_asset_locator,
    validate_media_contract,
    MAX_ASSET_BYTES,
    MAX_DOC_MEDIA_BYTES,
    MAX_DOC_ASSET_COUNT,
    MAX_IMAGE_PIXELS,
    MAX_IMAGE_SIDE,
)

# Reference valid 1x1 PNG bytes
PNG_1X1 = bytes([
    0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A,
    0x00, 0x00, 0x00, 0x0D, 0x49, 0x48, 0x44, 0x52,
    0x00, 0x00, 0x00, 0x01,  # width: 1
    0x00, 0x00, 0x00, 0x01,  # height: 1
    0x08, 0x06, 0x00, 0x00, 0x00,
    0x1F, 0x15, 0xC4, 0x89,
    0x00, 0x00, 0x00, 0x0A, 0x49, 0x44, 0x41, 0x54,
    0x78, 0x9C, 0x63, 0x00, 0x01, 0x00, 0x00, 0x05,
    0x00, 0x01, 0x0D, 0x0A, 0x2D, 0xB4,
    0x00, 0x00, 0x00, 0x00, 0x49, 0x45, 0x4E, 0x44,
    0xAE, 0x42, 0x60, 0x82
])

# Reference valid 1x1 JPEG bytes
JPEG_1X1 = bytes([
    0xFF, 0xD8,
    0xFF, 0xE0, 0x00, 0x10, 0x4A, 0x46, 0x49, 0x46, 0x00, 0x01, 0x01, 0x01, 0x00, 0x48, 0x00, 0x48, 0x00, 0x00,
    0xFF, 0xC0, 0x00, 0x0B, 0x08,
    0x00, 0x01,  # height: 1
    0x00, 0x01,  # width: 1
    0x01, 0x01, 0x11, 0x00,
    0xFF, 0xD9
])

# Reference valid 1x1 static WebP VP8X bytes
WEBP_VP8X_STATIC = bytes([
    0x52, 0x49, 0x46, 0x46,
    0x1E, 0x00, 0x00, 0x00,  # 30 bytes total file size - 8 = 22
    0x57, 0x45, 0x42, 0x50,
    0x56, 0x50, 0x38, 0x58,  # 'VP8X'
    0x0A, 0x00, 0x00, 0x00,  # 10 bytes chunk
    0x00, 0x00, 0x00, 0x00,  # flags: animation bit 1 = 0
    0x00, 0x00, 0x00,        # width - 1 = 0
    0x00, 0x00, 0x00         # height - 1 = 0
])


def make_asset_dict(data_bytes: bytes, mime: str, asset_id: str = "ast-test", declared_w: int = 1, declared_h: int = 1) -> Dict[str, Any]:
    b64 = base64.b64encode(data_bytes).decode("ascii")
    sha = hashlib.sha256(data_bytes).hexdigest()
    return {
        "id": asset_id,
        "mime": mime,
        "sha256": sha,
        "byte_length": len(data_bytes),
        "width": declared_w,
        "height": declared_h,
        "caption": "Adversarial test asset",
        "alt": "Adversarial test alt",
        "author_refs": ["auth-01"],
        "provenance": {"label": "Adversarial suite"},
        "locator": {
            "mode": "embedded",
            "data_uri": f"data:{mime};base64,{b64}"
        }
    }


# =============================================================================
# 1. MEDIA CORRUPTION & SPOOFING
# =============================================================================

class TestMediaCorruptionAndSpoofing:
    """Stress-test base64 decoding, byte header parsing, and MIME integrity."""

    @pytest.mark.parametrize("corrupt_b64, expected_code", [
        ("data:image/png;base64,invalid!@#$%^&*()", "ERR_ASSET_CORRUPTED_BASE64"),
        ("data:image/png;base64,AAA", "ERR_ASSET_CORRUPTED_BASE64"),           # length % 4 != 0
        ("data:image/png;base64,AAAAA", "ERR_ASSET_CORRUPTED_BASE64"),         # length % 4 != 0
        ("data:image/png;base64,AA===", "ERR_ASSET_CORRUPTED_BASE64"),         # too many =
        ("data:image/png;base64,A===", "ERR_ASSET_CORRUPTED_BASE64"),          # invalid padding
        ("data:image/png;base64,AA AA", "ERR_ASSET_CORRUPTED_BASE64"),         # whitespace inside
        ("data:image/png;base64,", "ERR_ASSET_CORRUPTED_BASE64"),              # empty base64
        ("data:image/png;base64", "ERR_ASSET_CORRUPTED_BASE64"),               # missing comma
        ("data:image/png,iVBORw0KGgoAAAANSUhEUgAAAAE=", "ERR_ASSET_CORRUPTED_BASE64"), # missing ;base64
        ("not_a_data_uri_at_all", "ERR_ASSET_CORRUPTED_BASE64"),
    ])
    def test_corrupted_base64_strings(self, corrupt_b64, expected_code):
        ok, code, msg, info = validate_asset_locator({"mode": "embedded", "data_uri": corrupt_b64})
        assert not ok
        assert code == expected_code

    @pytest.mark.parametrize("trunc_bytes", [
        bytes([]),
        bytes([0x89]),
        bytes([0x89, 0x50, 0x4E, 0x47]),
        bytes([0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A]),
        bytes([0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A]),                                    # 8 bytes: magic only, no chunk
        bytes([0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A, 0x00, 0x00, 0x00, 0x0D, 0x49, 0x48, 0x44]), # 15 bytes: truncated chunk header
        PNG_1X1[:23], # 23 bytes: 1 byte short of width+height
        bytes([0xFF]),
        bytes([0xFF, 0xD8]),                                                     # SOI only
        bytes([0xFF, 0xD8, 0xFF]),
        JPEG_1X1[:20], # SOI + APP0, but no SOF
        b"RIFF",
        b"RIFF\x00\x00\x00\x00",
        b"RIFF\x00\x00\x00\x00WEB",
        b"RIFF\x00\x00\x00\x00WEBP",                               # WEBP header, no chunks
        b"RIFF\x10\x00\x00\x00WEBPVP8 \x02\x00\x00\x00\x00\x00",          # VP8 truncated
        b"RIFF\x10\x00\x00\x00WEBPVP8L\x02\x00\x00\x00\x2F\x00",          # VP8L truncated
        b"RIFF\x10\x00\x00\x00WEBPVP8X\x04\x00\x00\x00\x00\x00\x00\x00",  # VP8X truncated
    ])
    def test_truncated_byte_headers(self, trunc_bytes):
        for mime in ["image/png", "image/jpeg", "image/webp"]:
            ok, hdr = parse_image_header(trunc_bytes, mime)
            assert not ok
            assert "error" in hdr or "code" in hdr

    @pytest.mark.parametrize("corrupt_png_bytes", [
        bytes([0x88]) + PNG_1X1[1:],                       # Byte 0 flip 0x89 -> 0x88
        PNG_1X1[:1] + bytes([0x51]) + PNG_1X1[2:],         # Byte 1 flip 'P' -> 'Q'
        PNG_1X1[:7] + bytes([0x0B]) + PNG_1X1[8:],         # Byte 7 flip 0x0A -> 0x0B
        PNG_1X1[:12] + b"JHDR" + PNG_1X1[16:],            # Chunk tag 'IHDR' -> 'JHDR'
        PNG_1X1[:16] + bytes(4) + PNG_1X1[20:],             # Width = 0 in IHDR chunk
        PNG_1X1[:20] + bytes(4) + PNG_1X1[24:],             # Height = 0 in IHDR chunk
    ])
    def test_png_magic_and_header_corruption(self, corrupt_png_bytes):
        ok, hdr = parse_image_header(corrupt_png_bytes, "image/png")
        assert not ok

    @pytest.mark.parametrize("corrupt_jpeg_bytes", [
        bytes([0xFE]) + JPEG_1X1[1:],                      # Byte 0 flip
        JPEG_1X1[:1] + bytes([0xD7]) + JPEG_1X1[2:],       # Byte 1 flip
        JPEG_1X1[:2] + bytes([0xFE]) + JPEG_1X1[3:],       # Byte 2 flip
        JPEG_1X1[:25] + bytes(2) + JPEG_1X1[27:],          # Height = 0 in SOF
        JPEG_1X1[:27] + bytes(2) + JPEG_1X1[29:],          # Width = 0 in SOF
    ])
    def test_jpeg_magic_and_header_corruption(self, corrupt_jpeg_bytes):
        ok, hdr = parse_image_header(corrupt_jpeg_bytes, "image/jpeg")
        assert not ok

    @pytest.mark.parametrize("corrupt_webp_bytes", [
        b"RIFD" + WEBP_VP8X_STATIC[4:],                 # 'RIFF' -> 'RIFD'
        WEBP_VP8X_STATIC[:8] + b"WEBA" + WEBP_VP8X_STATIC[12:], # 'WEBP' -> 'WEBA'
    ])
    def test_webp_magic_corruption(self, corrupt_webp_bytes):
        ok, hdr = parse_image_header(corrupt_webp_bytes, "image/webp")
        assert not ok

    @pytest.mark.parametrize("payload, declared_mime", [
        (b"<html><body><script>alert(1)</script></body></html>", "image/png"),
        (b"<svg xmlns='http://www.w3.org/2000/svg'><circle r='10'/></svg>", "image/png"),
        (b"<svg xmlns='http://www.w3.org/2000/svg'><circle r='10'/></svg>", "image/jpeg"),
        (b"<svg xmlns='http://www.w3.org/2000/svg'><circle r='10'/></svg>", "image/webp"),
        (b"GIF89a\x01\x00\x01\x00\x80\x00\x00\xff\xff\xff\x00\x00\x00!\xf9\x04\x01\x00\x00\x00\x00,\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;", "image/png"),
        (b"%PDF-1.7\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF", "image/png"),
        (b"MZ\x90\x00\x03\x00\x00\x00\x04\x00\x00\x00\xff\xff\x00\x00", "image/png"), # PE exe
        (b"\x7fELF\x02\x01\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00", "image/jpeg"),     # ELF exe
        (b"PK\x03\x04\x14\x00\x00\x00\x08\x00\x00\x00\x00\x00\x00\x00", "image/webp"), # ZIP archive (>=12 bytes)
        (PNG_1X1, "image/jpeg"),                                                # PNG claimed as JPEG
        (JPEG_1X1, "image/webp"),                                               # JPEG claimed as WebP
        (WEBP_VP8X_STATIC, "image/png"),                                        # WebP claimed as PNG
    ])
    def test_mime_spoofing_rejections(self, payload, declared_mime):
        ok, hdr = parse_image_header(payload, declared_mime)
        assert not ok
        assert hdr.get("code") == "ERR_ASSET_MIME_SPOOFING"

    @pytest.mark.parametrize("forbidden_mime", [
        "image/jpg",         # Forbidden per spec r2 §5 (must be image/jpeg)
        "image/gif",
        "image/svg+xml",
        "image/bmp",
        "image/tiff",
        "application/octet-stream",
        "text/html",
    ])
    def test_forbidden_mime_in_contract(self, make_rich_v3_doc, forbidden_mime):
        doc = make_rich_v3_doc()
        asset = make_asset_dict(PNG_1X1, "image/png", "ast-01")
        asset["mime"] = forbidden_mime
        doc["assets"] = [asset]
        issues, budget = validate_media_contract(doc)
        assert any(e.code == "ERR_ASSET_INVALID_MIME" for e in issues)


# =============================================================================
# 2. ANIMATED WEBP DETECTION
# =============================================================================

class TestAnimatedWebpDetection:
    """Verify strict blocking of animated WebP across bit variations and frame chunk tags (§5, AC-23)."""

    @pytest.mark.parametrize("flags_byte", [
        0x02,  # Bit 1 set: Animation
        0x03,  # Bit 1 + Bit 0 (animation + reserved)
        0x12,  # Bit 1 + Bit 4 (animation + alpha)
        0x82,  # Bit 1 + Bit 7 (animation + high bit)
        0x22,  # Bit 1 + Bit 5 (animation + ICC)
        0x3E,  # All standard bits set including animation
        0xFF,  # All bits set
    ])
    def test_vp8x_animation_flag_bit_combinations(self, flags_byte):
        payload = bytearray(WEBP_VP8X_STATIC)
        payload[20] = flags_byte
        ok, hdr = parse_image_header(bytes(payload), "image/webp")
        assert not ok
        assert hdr.get("code") == "ERR_ASSET_ANIMATED_WEBP"

    def test_webp_with_anim_chunk_even_if_vp8x_flag_is_zero(self):
        # VP8X chunk (10 bytes payload + 8 header = 18 bytes)
        vp8x_chunk = b"VP8X\x0a\x00\x00\x00" + bytes([0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00])
        # ANIM chunk (6 bytes payload + 8 header = 14 bytes)
        anim_chunk = b"ANIM\x06\x00\x00\x00\x00\x00\x00\x00\x00\x00"
        riff_payload = b"WEBP" + vp8x_chunk + anim_chunk
        riff_header = b"RIFF" + (len(riff_payload)).to_bytes(4, 'little')
        full_payload = riff_header + riff_payload

        ok, hdr = parse_image_header(full_payload, "image/webp")
        assert not ok
        assert hdr.get("code") == "ERR_ASSET_ANIMATED_WEBP"

    def test_webp_with_anmf_frame_chunk(self):
        vp8x_chunk = b"VP8X\x0a\x00\x00\x00" + bytes([0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00])
        anmf_chunk = b"ANMF\x10\x00\x00\x00" + bytes(16)
        riff_payload = b"WEBP" + vp8x_chunk + anmf_chunk
        riff_header = b"RIFF" + (len(riff_payload)).to_bytes(4, 'little')
        full_payload = riff_header + riff_payload

        ok, hdr = parse_image_header(full_payload, "image/webp")
        assert not ok
        assert hdr.get("code") == "ERR_ASSET_ANIMATED_WEBP"


# =============================================================================
# 3. BUDGET EDGE CASES & BOUNDARY VALUE ANALYSIS
# =============================================================================

class TestBudgetBoundaries:
    """Exact boundary tests for 8 MiB per-asset, 32 MiB total, 50 assets, 16 MP, 8192px side (§5)."""

    def test_single_asset_size_exact_boundary(self, make_rich_v3_doc):
        doc = make_rich_v3_doc()
        exact_8mib = MAX_ASSET_BYTES

        asset_exact = {
            "id": "ast-8mib",
            "mime": "image/png",
            "sha256": "0" * 64,
            "byte_length": exact_8mib,
            "width": 10,
            "height": 10,
            "caption": "Exact 8 MiB",
            "locator": {"mode": "relative", "path": "assets/img8mib.png"}
        }
        doc["assets"] = [asset_exact]
        issues, budget = validate_media_contract(doc)
        assert not any(e.code == "ERR_ASSET_SIZE_BUDGET_EXCEEDED" for e in issues)

    def test_single_asset_size_exceeded_by_one_byte(self, make_rich_v3_doc):
        doc = make_rich_v3_doc()
        over_8mib = MAX_ASSET_BYTES + 1
        # In embedded mode, payload of over_8mib bytes
        dummy_bytes = bytes(over_8mib)
        b64 = base64.b64encode(dummy_bytes).decode('ascii')
        asset_over = {
            "id": "ast-over",
            "mime": "image/png",
            "sha256": hashlib.sha256(dummy_bytes).hexdigest(),
            "byte_length": over_8mib,
            "width": 10,
            "height": 10,
            "caption": "Over 8 MiB by 1 byte",
            "locator": {"mode": "embedded", "data_uri": f"data:image/png;base64,{b64}"}
        }
        doc["assets"] = [asset_over]
        issues, budget = validate_media_contract(doc)
        assert any(e.code == "ERR_ASSET_SIZE_BUDGET_EXCEEDED" for e in issues)

    def test_asset_count_exact_boundary(self, make_rich_v3_doc):
        doc = make_rich_v3_doc()

        # Exactly 50 assets -> must pass count check
        assets_50 = []
        for i in range(MAX_DOC_ASSET_COUNT):
            assets_50.append(make_asset_dict(PNG_1X1, "image/png", f"ast-{i:02d}"))
        doc["assets"] = assets_50
        issues, budget = validate_media_contract(doc)
        assert not any(e.code == "ERR_DOC_ASSET_COUNT_EXCEEDED" for e in issues)

        # 51 assets -> must fail with ERR_DOC_ASSET_COUNT_EXCEEDED
        doc["assets"].append(make_asset_dict(PNG_1X1, "image/png", "ast-51"))
        issues_51, _ = validate_media_contract(doc)
        assert any(e.code == "ERR_DOC_ASSET_COUNT_EXCEEDED" for e in issues_51)

    def test_total_media_size_exact_boundary(self, make_rich_v3_doc):
        budget_state = {"total_bytes": MAX_DOC_MEDIA_BYTES, "count": 4}
        ast_1byte = make_asset_dict(PNG_1X1, "image/png", "ast-plus")
        issues, budget = validate_media_contract([ast_1byte], total_budget_state=budget_state)
        assert any(e.code == "ERR_DOC_MEDIA_BUDGET_EXCEEDED" for e in issues)

    @pytest.mark.parametrize("w, h, should_pass", [
        (4096, 4096, True),   # 16,777,216 px = exactly 16 MP
        (4096, 4097, False),  # 16,781,312 px > 16 MP
        (8192, 2048, True),   # 16,777,216 px = 16 MP and side = 8192
        (8192, 2049, False),  # 16,785,408 px > 16 MP
        (8193, 1, False),     # Side 8193 > 8192 px
        (1, 8193, False),     # Side 8193 > 8192 px
        (8192, 8192, False),  # 64 MP > 16 MP
    ])
    def test_megapixel_and_side_boundaries(self, make_rich_v3_doc, w, h, should_pass):
        doc = make_rich_v3_doc()
        ast = {
            "id": "ast-dims",
            "mime": "image/png",
            "sha256": "0" * 64,
            "byte_length": 100,
            "width": w,
            "height": h,
            "caption": "Dimension test",
            "locator": {"mode": "relative", "path": f"assets/dims_{w}_{h}.png"}
        }
        doc["assets"] = [ast]
        issues, _ = validate_media_contract(doc)
        has_dim_err = any(e.code == "ERR_ASSET_DIMENSIONS_EXCEEDED" for e in issues)
        if should_pass:
            assert not has_dim_err, f"Expected {w}x{h} to pass but got ERR_ASSET_DIMENSIONS_EXCEEDED"
        else:
            assert has_dim_err, f"Expected {w}x{h} to fail ERR_ASSET_DIMENSIONS_EXCEEDED"

    @pytest.mark.parametrize("bad_w, bad_h", [
        (0, 10),
        (10, 0),
        (0, 0),
        (-1, 100),
        (100, -1),
    ])
    def test_zero_and_negative_dimensions_schema_rejection(self, make_rich_v3_doc, engine, bad_w, bad_h):
        doc = make_rich_v3_doc()
        doc["assets"][0]["width"] = bad_w
        doc["assets"][0]["height"] = bad_h
        report = engine.validate_document(doc)
        assert not report.is_valid
        assert any("width" in i.path or "height" in i.path for i in report.issues)


# =============================================================================
# 4. LOCATOR ATTACKS (WINDOWS, UNC, FILE, TRAVERSAL, CREDENTIALS)
# =============================================================================

class TestLocatorSecurityAttacks:
    """Exhaustive penetration tests against locator security rules (AC-24)."""

    @pytest.mark.parametrize("drive_path", [
        "C:\\Windows\\System32\\cmd.exe",
        "c:/secret/image.png",
        "D:\\data\\dump.png",
        "d:/foo.png",
        "Z:\\deep\\path.png",
        "c:image.png",                        # drive-relative
        "C:test.png",
    ])
    def test_windows_drive_letters_blocked(self, drive_path):
        ok, code, msg, _ = validate_asset_locator({"mode": "relative", "path": drive_path})
        assert not ok
        assert code == "ERR_FORBIDDEN_ASSET_LOCATOR"
        assert "диска" in msg or "буквой" in msg

    @pytest.mark.parametrize("unc_path", [
        "\\\\server\\share\\file.png",
        "//server/share/file.png",
        "\\\\?\\C:\\Windows\\System32\\notepad.exe",
        "\\\\192.168.1.1\\share\\img.png",
        "//10.0.0.1/share/img.png",
        "\\\\\\server\\share\\img.png",
    ])
    def test_unc_paths_blocked(self, unc_path):
        ok, code, msg, _ = validate_asset_locator({"mode": "relative", "path": unc_path})
        assert not ok
        assert code == "ERR_FORBIDDEN_ASSET_LOCATOR"
        assert "UNC" in msg

    @pytest.mark.parametrize("file_uri", [
        "file:///etc/passwd",
        "file://C:/boot.ini",
        "file:///c:/secret.png",
        "file:image.png",
        "file://localhost/image.png",
    ])
    def test_file_scheme_blocked(self, file_uri):
        ok, code, msg, _ = validate_asset_locator({"mode": "relative", "path": file_uri})
        assert not ok
        assert code == "ERR_FORBIDDEN_ASSET_LOCATOR"

    @pytest.mark.parametrize("traversal_path", [
        "../secret.png",
        "../../secret.png",
        "../../../etc/shadow",
        "assets/../secret.png",
        "assets/../../secret.png",
        "assets/sub/../../../secret.png",
        "..\\secret.png",
        "assets\\..\\secret.png",
        "assets/..",
        "..",
    ])
    def test_directory_traversal_blocked(self, traversal_path):
        ok, code, msg, _ = validate_asset_locator({"mode": "relative", "path": traversal_path})
        assert not ok
        assert code == "ERR_FORBIDDEN_ASSET_LOCATOR"

    @pytest.mark.parametrize("encoded_or_special_path", [
        "assets/%2e%2e/secret.png",
        "assets/%2E%2E/secret.png",
        "assets/%2f/secret.png",
        "assets/%5c/secret.png",
        "assets/%25/secret.png",
        "assets/foo%20bar.png",      # % forbidden per §5 line 130
        "assets/foo:bar.png",        # : forbidden per §5 line 130
        "assets/image.png?version=1", # ? forbidden
        "assets/image.png#fragment",  # # forbidden
    ])
    def test_encoded_and_special_chars_blocked(self, encoded_or_special_path):
        ok, code, msg, _ = validate_asset_locator({"mode": "relative", "path": encoded_or_special_path})
        assert not ok
        assert code == "ERR_FORBIDDEN_ASSET_LOCATOR"

    def test_non_nfc_unicode_path_blocked(self):
        # Decomposed Unicode (NFD): 'e' + combining acute accent (U+0301)
        decomposed = "assets/caf" + unicodedata.normalize("NFD", "é")[1] + "e.png" # e with separate accent
        nfd_path = "assets/" + unicodedata.normalize("NFD", "café.png")
        assert not unicodedata.is_normalized("NFC", nfd_path)
        ok, code, msg, _ = validate_asset_locator({"mode": "relative", "path": nfd_path})
        assert not ok
        assert code == "ERR_FORBIDDEN_ASSET_LOCATOR"
        assert "NFC" in msg

    @pytest.mark.parametrize("bad_external_url", [
        "http://insecure.site/image.png",
        "ftp://files.example.com/image.png",
        "javascript:alert(1)",
        "data:text/html,<script>alert(1)</script>",
        "https://user:password@secure.site/image.png",
        "https://admin@secure.site/image.png",
        "https://example.com/path\\sub\\img.png",
        "https://example.com/path/../img.png",
        "https://example.com/path/..",
    ])
    def test_external_url_security_rejections(self, bad_external_url):
        ok, code, msg, _ = validate_asset_locator({"mode": "external", "url": bad_external_url})
        assert not ok
        assert code == "ERR_FORBIDDEN_ASSET_LOCATOR"

    def test_vulnerability_credentials_empty_password_pattern(self):
        """VULNERABILITY FINDING: https://user:@host/image.png has empty password.
        The current regex ^https://[^/@:]+(:[^/@:]+)?@ fails to match because + requires >= 1 char after colon.
        Documented as a critical finding in Challenger M4 report.
        """
        target_url = "https://user:@secure.site/image.png"
        ok, code, msg, _ = validate_asset_locator({"mode": "external", "url": target_url})
        # If ok is True, we have empirical proof of the bug in validator.py line 278!
        if ok:
            pytest.xfail("EMPIRICALLY CONFIRMED BUG: empty password in credentials URL (https://user:@host) bypasses locator security regex!")
        assert not ok

    @pytest.mark.parametrize("url, should_allow, label", [
        ("https://user:@host/img.png", False, "empty password"),
        ("https://:pass@host/img.png", False, "empty username"),
        ("https://user:pass@host/img.png", False, "user and pass"),
        ("https://@host/img.png", False, "empty user and empty pass with @"),
        ("https://valid.site/img.png", True, "valid external site"),
        ("https://valid.site/image@2x.png", True, "@ in path component"),
        ("https://valid.site/api?q=foo@bar", True, "@ in query string"),
        ("https://valid.site/page#header@target", True, "@ in fragment"),
        ("https://admin:secret@host:8443/img.png", False, "credentials with custom port"),
        ("https://user@[::1]:8443/img.png", False, "credentials with IPv6 authority"),
        ("https://[::1]:8443/img.png", True, "IPv6 authority without credentials"),
    ])
    def test_remediated_credentials_regex_edge_cases(self, url, should_allow, label):
        """M4-r2: Exhaustive validation of external URL authority credentials regex."""
        ok, code, msg, _ = validate_asset_locator({"mode": "external", "url": url})
        if should_allow:
            assert ok, f"Expected {url} ({label}) to be allowed, but got code: {code}, msg: {msg}"
        else:
            assert not ok, f"Expected {url} ({label}) to be rejected, but it was allowed!"
            assert code == "ERR_FORBIDDEN_ASSET_LOCATOR"
            assert "учетные данные" in msg or "credentials" in msg



# =============================================================================
# 5. DETACHED MANIFEST PERMUTATIONS
# =============================================================================

class TestDetachedManifestPermutations:
    """Verify detached integrity manifest permutations (§7, §8, AC-26)."""

    def test_manifest_matching(self, engine, make_rich_v3_doc):
        doc = make_rich_v3_doc()
        raw_bytes = b'{"format":"paralleldoc","version":"3.0"}'
        raw_sha = hashlib.sha256(raw_bytes).hexdigest()

        manifest = {
            "format": "paralleldoc-integrity-1",
            "algorithm": "SHA-256",
            "scope": "raw-bytes",
            "expected_sha256": raw_sha,
            "document_id": "doc-rich-01",
            "revision": "rev-1"
        }
        rep = engine.validate_manifest(manifest)
        assert rep.is_valid

        status, msg = engine.check_manifest_match(manifest, doc["metadata"], raw_sha)
        assert status == "matched"
        assert "совпал" in msg

    def test_manifest_mismatch(self, engine, make_rich_v3_doc):
        doc = make_rich_v3_doc()
        raw_sha = "a" * 64
        manifest = {
            "format": "paralleldoc-integrity-1",
            "algorithm": "SHA-256",
            "scope": "raw-bytes",
            "expected_sha256": "b" * 64,
            "document_id": "doc-rich-01",
            "revision": "rev-1"
        }
        status, msg = engine.check_manifest_match(manifest, doc["metadata"], raw_sha)
        assert status == "mismatch"
        assert "SHA mismatch" in msg

    def test_manifest_different_document_id(self, engine, make_rich_v3_doc):
        doc = make_rich_v3_doc()
        raw_sha = "a" * 64
        manifest = {
            "format": "paralleldoc-integrity-1",
            "algorithm": "SHA-256",
            "scope": "raw-bytes",
            "expected_sha256": raw_sha,
            "document_id": "different-doc-999",
            "revision": "rev-1"
        }
        status, msg = engine.check_manifest_match(manifest, doc["metadata"], raw_sha)
        assert status == "different_document"

    def test_manifest_different_revision(self, engine, make_rich_v3_doc):
        doc = make_rich_v3_doc()
        raw_sha = "a" * 64
        manifest = {
            "format": "paralleldoc-integrity-1",
            "algorithm": "SHA-256",
            "scope": "raw-bytes",
            "expected_sha256": raw_sha,
            "document_id": "doc-rich-01",
            "revision": "rev-999"
        }
        status, msg = engine.check_manifest_match(manifest, doc["metadata"], raw_sha)
        assert status == "different_document"

    @pytest.mark.parametrize("bad_manifest", [
        {"format": "paralleldoc-integrity-2", "algorithm": "SHA-256", "scope": "raw-bytes", "expected_sha256": "a" * 64},
        {"format": "paralleldoc-integrity-1", "algorithm": "SHA-512", "scope": "raw-bytes", "expected_sha256": "a" * 64},
        {"format": "paralleldoc-integrity-1", "algorithm": "SHA-256", "scope": "normalized-json", "expected_sha256": "a" * 64},
        {"format": "paralleldoc-integrity-1", "algorithm": "SHA-256", "scope": "raw-bytes", "expected_sha256": "A" * 64}, # uppercase hex forbidden
        {"format": "paralleldoc-integrity-1", "algorithm": "SHA-256", "scope": "raw-bytes", "expected_sha256": "a" * 63}, # 63 chars
        {"format": "paralleldoc-integrity-1", "algorithm": "SHA-256", "scope": "raw-bytes", "expected_sha256": "a" * 65}, # 65 chars
        {"format": "paralleldoc-integrity-1", "algorithm": "SHA-256", "scope": "raw-bytes", "expected_sha256": "a" * 64, "extra_property": 123}, # additionalProperties: false
    ])
    def test_invalid_manifest_schemas(self, engine, bad_manifest):
        rep = engine.validate_manifest(bad_manifest)
        assert not rep.is_valid
        assert any(i.code == "ERR_MANIFEST_SCHEMA_VIOLATION" for i in rep.issues)
