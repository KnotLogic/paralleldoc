"""
tests/test_media.py — Test Suite for ParallelDoc 3.0 Milestone 4 Media Contract.
Verifies binary header parsing, locator security, budgets, digests, and error diagnostics.
Fulfills F34–F44, AC-19–AC-24, AC-26–AC-29.
"""

import base64
import hashlib
from typing import Any, Dict
import pytest

from validator import (
    IntegrityEngine,
    parse_image_header,
    validate_asset_locator,
    validate_media_contract,
)

# Standard valid 1x1 PNG bytes
PNG_1X1_BYTES = bytes([
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

# Minimal valid JPEG bytes (1x1 pixel)
JPEG_1X1_BYTES = bytes([
    0xFF, 0xD8,  # SOI
    0xFF, 0xE0, 0x00, 0x10, 0x4A, 0x46, 0x49, 0x46, 0x00, 0x01, 0x01, 0x01, 0x00, 0x48, 0x00, 0x48, 0x00, 0x00,
    0xFF, 0xC0, 0x00, 0x0B, 0x08,  # SOF0, precision 8
    0x00, 0x01,  # height: 1
    0x00, 0x01,  # width: 1
    0x01, 0x01, 0x11, 0x00,
    0xFF, 0xD9   # EOI
])

# Minimal valid WebP VP8 bytes (1x1 pixel)
WEBP_VP8_BYTES = bytes([
    0x52, 0x49, 0x46, 0x46,  # 'RIFF'
    0x1E, 0x00, 0x00, 0x00,  # size
    0x57, 0x45, 0x42, 0x50,  # 'WEBP'
    0x56, 0x50, 0x38, 0x20,  # 'VP8 '
    0x12, 0x00, 0x00, 0x00,  # chunk size 18
    0x30, 0x01, 0x00,        # frame tag (keyframe)
    0x9D, 0x01, 0x2A,        # start code 9D 01 2A
    0x01, 0x00,              # width 1 (14-bit)
    0x01, 0x00               # height 1 (14-bit)
]) + b'\x00' * 10

# Minimal valid WebP VP8L bytes (1x1 pixel)
WEBP_VP8L_BYTES = bytes([
    0x52, 0x49, 0x46, 0x46,
    0x1A, 0x00, 0x00, 0x00,
    0x57, 0x45, 0x42, 0x50,
    0x56, 0x50, 0x38, 0x4C,  # 'VP8L'
    0x0E, 0x00, 0x00, 0x00,
    0x2F,                    # 1-byte signature
    0x00, 0x00, 0x00, 0x00   # 14-bit width-1 = 0, 14-bit height-1 = 0
]) + b'\x00' * 9

# Minimal static WebP VP8X bytes (1x1 pixel, animation bit 1 = 0)
WEBP_VP8X_STATIC_BYTES = bytes([
    0x52, 0x49, 0x46, 0x46,
    0x20, 0x00, 0x00, 0x00,
    0x57, 0x45, 0x42, 0x50,
    0x56, 0x50, 0x38, 0x58,  # 'VP8X'
    0x0A, 0x00, 0x00, 0x00,  # 10 bytes payload
    0x00, 0x00, 0x00, 0x00,  # flags: animation flag (bit 1) is 0
    0x00, 0x00, 0x00,        # canvas width - 1 = 0 -> 1px
    0x00, 0x00, 0x00         # canvas height - 1 = 0 -> 1px
]) + b'\x00' * 8

# Animated WebP VP8X bytes (animation bit 1 is set: 0x02)
WEBP_VP8X_ANIMATED_BYTES = bytes([
    0x52, 0x49, 0x46, 0x46,
    0x20, 0x00, 0x00, 0x00,
    0x57, 0x45, 0x42, 0x50,
    0x56, 0x50, 0x38, 0x58,
    0x0A, 0x00, 0x00, 0x00,
    0x02, 0x00, 0x00, 0x00,  # flags & 0x02 != 0 -> ANIMATED!
    0x00, 0x00, 0x00,
    0x00, 0x00, 0x00
]) + b'\x00' * 8


def make_test_asset(data_bytes: bytes, mime: str, asset_id: str = "ast-01") -> Dict[str, Any]:
    b64 = base64.b64encode(data_bytes).decode("ascii")
    sha = hashlib.sha256(data_bytes).hexdigest()
    return {
        "id": asset_id,
        "mime": mime,
        "sha256": sha,
        "byte_length": len(data_bytes),
        "width": 1,
        "height": 1,
        "caption": "Test Image",
        "alt": "Test Image Alt",
        "author_refs": ["auth-01"],
        "provenance": {"label": "Generated in-memory test asset"},
        "locator": {
            "mode": "embedded",
            "data_uri": f"data:{mime};base64,{b64}"
        }
    }


# =============================================================================
# 1. Binary Image Header Parsing & Parity
# =============================================================================

def test_parse_image_header_png():
    ok, header = parse_image_header(PNG_1X1_BYTES, "image/png")
    assert ok is True
    assert header["mime"] == "image/png"
    assert header["width"] == 1
    assert header["height"] == 1


def test_parse_image_header_jpeg():
    ok, header = parse_image_header(JPEG_1X1_BYTES, "image/jpeg")
    assert ok is True
    assert header["mime"] == "image/jpeg"
    assert header["width"] == 1
    assert header["height"] == 1


def test_parse_image_header_webp_vp8():
    ok, header = parse_image_header(WEBP_VP8_BYTES, "image/webp")
    assert ok is True
    assert header["mime"] == "image/webp"
    assert header["width"] == 1
    assert header["height"] == 1


def test_parse_image_header_webp_vp8l():
    ok, header = parse_image_header(WEBP_VP8L_BYTES, "image/webp")
    assert ok is True
    assert header["mime"] == "image/webp"
    assert header["width"] == 1
    assert header["height"] == 1


def test_parse_image_header_webp_vp8x_static():
    ok, header = parse_image_header(WEBP_VP8X_STATIC_BYTES, "image/webp")
    assert ok is True
    assert header["mime"] == "image/webp"
    assert header["width"] == 1
    assert header["height"] == 1


def test_parse_image_header_webp_animated_rejected():
    ok, header = parse_image_header(WEBP_VP8X_ANIMATED_BYTES, "image/webp")
    assert ok is False
    assert header["code"] == "ERR_ASSET_ANIMATED_WEBP"


def test_parse_image_header_corrupted_or_truncated():
    ok, header = parse_image_header(b"", "image/png")
    assert ok is False
    ok, header = parse_image_header(b"random garbage bytes 1234567890", "image/png")
    assert ok is False
    ok, header = parse_image_header(PNG_1X1_BYTES[:12], "image/png")
    assert ok is False


# =============================================================================
# 2. Locator Security Hardening
# =============================================================================

@pytest.mark.parametrize("bad_path", [
    "C:\\Windows\\system32\\image.png",
    "D:/secret/file.png",
    "\\\\server\\share\\image.png",
    "file:///etc/passwd",
    "file://C:/image.png",
    "../traversal/image.png",
    "assets/../../secret.png",
    "assets\\sub\\image.png",
    "assets/%2e%2e/secret.png",
    "/absolute/posix/path.png",
])
def test_locator_security_relative_rejections(bad_path):
    ok, code, msg, info = validate_asset_locator({"mode": "relative", "path": bad_path})
    assert not ok
    assert code == "ERR_FORBIDDEN_ASSET_LOCATOR"


@pytest.mark.parametrize("bad_url", [
    "https://user:pass@evil.com/image.png",
    "http://unencrypted.com/image.png",
    "ftp://ftp.server.com/image.png",
    "javascript:alert(1)",
    "https://evil.com/path\\sub/img.png",
    "https://evil.com/path/../secret.png",
])
def test_locator_security_external_rejections(bad_url):
    ok, code, msg, info = validate_asset_locator({"mode": "external", "url": bad_url})
    assert not ok
    assert code == "ERR_FORBIDDEN_ASSET_LOCATOR"


def test_locator_malformed_data_uri():
    ok, code, msg, info = validate_asset_locator({"mode": "embedded", "data_uri": "data:image/png;notbase64,???"})
    assert not ok
    assert code == "ERR_ASSET_CORRUPTED_BASE64"

    ok, code, msg, info = validate_asset_locator({"mode": "embedded", "data_uri": "not_even_a_data_uri"})
    assert not ok
    assert code == "ERR_ASSET_CORRUPTED_BASE64"


def test_locator_valid_data_uri():
    b64 = base64.b64encode(PNG_1X1_BYTES).decode("ascii")
    ok, code, msg, info = validate_asset_locator({"mode": "embedded", "data_uri": f"data:image/png;base64,{b64}"})
    assert ok
    assert code == ""


# =============================================================================
# 3. Media Contract Validation (Engine & Document Level)
# =============================================================================

def test_media_contract_valid_document(make_rich_v3_doc):
    doc = make_rich_v3_doc()
    asset = make_test_asset(PNG_1X1_BYTES, "image/png", "ast-sla-uptime")
    doc["assets"] = [asset]
    doc["units"][0]["asset_ids"] = ["ast-sla-uptime"]

    issues, budget = validate_media_contract(doc)
    assert len(issues) == 0


def test_media_contract_corrupted_base64(make_rich_v3_doc):
    doc = make_rich_v3_doc()
    asset = make_test_asset(PNG_1X1_BYTES, "image/png", "ast-01")
    asset["locator"]["data_uri"] = "data:image/png;base64,invalid_base64_!@#$%"
    doc["assets"] = [asset]

    issues, budget = validate_media_contract(doc)
    assert any(e.code == "ERR_ASSET_CORRUPTED_BASE64" for e in issues)


def test_media_contract_mime_spoofing(make_rich_v3_doc):
    doc = make_rich_v3_doc()
    # Declares image/png but payload is JPEG bytes
    asset = make_test_asset(JPEG_1X1_BYTES, "image/jpeg", "ast-01")
    asset["mime"] = "image/png"
    asset["locator"]["data_uri"] = f"data:image/png;base64,{base64.b64encode(JPEG_1X1_BYTES).decode('ascii')}"
    doc["assets"] = [asset]

    issues, budget = validate_media_contract(doc)
    assert any(e.code == "ERR_ASSET_MIME_SPOOFING" for e in issues)


def test_media_contract_dimension_mismatch(make_rich_v3_doc):
    doc = make_rich_v3_doc()
    asset = make_test_asset(PNG_1X1_BYTES, "image/png", "ast-01")
    asset["width"] = 999  # Actual is 1
    doc["assets"] = [asset]

    issues, budget = validate_media_contract(doc)
    assert any(e.code == "ERR_ASSET_DIMENSIONS_MISMATCH" for e in issues)


def test_media_contract_sha_mismatch(make_rich_v3_doc):
    doc = make_rich_v3_doc()
    asset = make_test_asset(PNG_1X1_BYTES, "image/png", "ast-01")
    asset["sha256"] = "0000000000000000000000000000000000000000000000000000000000000000"
    doc["assets"] = [asset]

    issues, budget = validate_media_contract(doc)
    assert any(e.code == "ERR_ASSET_HASH_MISMATCH" for e in issues)


def test_media_contract_byte_length_mismatch(make_rich_v3_doc):
    doc = make_rich_v3_doc()
    asset = make_test_asset(PNG_1X1_BYTES, "image/png", "ast-01")
    asset["byte_length"] = 12345
    doc["assets"] = [asset]

    issues, budget = validate_media_contract(doc)
    assert any(e.code == "ERR_ASSET_BYTE_LENGTH_MISMATCH" for e in issues)


def test_media_contract_dimension_exceeded(make_rich_v3_doc):
    doc = make_rich_v3_doc()
    asset = make_test_asset(PNG_1X1_BYTES, "image/png", "ast-01")
    asset["width"] = 8193  # Limit is 8192
    doc["assets"] = [asset]

    issues, budget = validate_media_contract(doc)
    assert any(e.code == "ERR_ASSET_DIMENSIONS_EXCEEDED" for e in issues)


def test_media_contract_megapixel_exceeded(make_rich_v3_doc):
    doc = make_rich_v3_doc()
    asset = make_test_asset(PNG_1X1_BYTES, "image/png", "ast-01")
    asset["width"] = 5000
    asset["height"] = 4000  # 20 MP > 16 MP limit
    doc["assets"] = [asset]

    issues, budget = validate_media_contract(doc)
    assert any(e.code == "ERR_ASSET_DIMENSIONS_EXCEEDED" for e in issues)


def test_media_contract_single_asset_size_exceeded(make_rich_v3_doc):
    doc = make_rich_v3_doc()
    large_b64 = "A" * (12 * 1024 * 1024)  # ~9 MiB payload
    asset = {
        "id": "ast-large",
        "mime": "image/png",
        "sha256": "0" * 64,
        "byte_length": 9 * 1024 * 1024,
        "width": 100,
        "height": 100,
        "caption": "Too Large",
        "locator": {
            "mode": "embedded",
            "data_uri": f"data:image/png;base64,{large_b64}"
        }
    }
    doc["assets"] = [asset]

    issues, budget = validate_media_contract(doc)
    assert any(e.code == "ERR_ASSET_SIZE_BUDGET_EXCEEDED" for e in issues)


def test_media_contract_total_size_budget_exceeded(make_rich_v3_doc):
    doc = make_rich_v3_doc()
    # 5 assets each 7 MiB payload -> 35 MiB > 32 MiB total budget
    payload = b"\x00" * (7 * 1024 * 1024)
    chunk_b64 = base64.b64encode(payload).decode("ascii")
    assets = []
    for i in range(5):
        ast = {
            "id": f"ast-{i}",
            "mime": "image/png",
            "sha256": "0" * 64,
            "byte_length": 7 * 1024 * 1024,
            "width": 10,
            "height": 10,
            "caption": f"Asset {i}",
            "locator": {
                "mode": "embedded",
                "data_uri": f"data:image/png;base64,{chunk_b64}"
            }
        }
        assets.append(ast)
    doc["assets"] = assets

    issues, budget = validate_media_contract(doc)
    assert any(e.code == "ERR_DOC_MEDIA_BUDGET_EXCEEDED" for e in issues)


def test_media_contract_asset_count_exceeded(make_rich_v3_doc):
    doc = make_rich_v3_doc()
    assets = []
    for i in range(51):  # > 50 limit
        assets.append(make_test_asset(PNG_1X1_BYTES, "image/png", f"ast-{i}"))
    doc["assets"] = assets

    issues, budget = validate_media_contract(doc)
    assert any(e.code == "ERR_DOC_ASSET_COUNT_EXCEEDED" for e in issues)


def test_integrity_engine_check_media_flag(make_rich_v3_doc):
    doc = make_rich_v3_doc()
    # Replace ast-01 with a genuinely valid 1x1 PNG asset
    valid_ast = make_test_asset(PNG_1X1_BYTES, "image/png", "ast-01")
    doc["assets"] = [valid_ast]

    engine = IntegrityEngine()
    report = engine.validate_document(doc, check_media=True)
    assert report.is_valid, f"Expected valid document but got issues: {[(i.code, i.message) for i in report.issues]}"
    assert len(report.issues) == 0
