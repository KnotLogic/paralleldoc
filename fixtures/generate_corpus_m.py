"""
fixtures/generate_corpus_m.py — Generator for Corpus M (24 Media Contract Fixtures).
Materializes 24 deterministic media fixtures verifying PNG, JPEG, WebP, aspect ratios,
corrupted base64, MIME spoofing, wrong SHA/dimensions/length, animated WebP,
budget overruns (single, total, count, MP, side), and forbidden locators (Windows, UNC, file, credentials).
Complies strictly with Spec r2 §5, §7, §11 (AC-19, AC-20, AC-22, AC-23, AC-24).
"""

import base64
import hashlib
import json
from pathlib import Path
import struct
import zlib


def make_png_bytes(width: int, height: int, rgba: tuple = (30, 144, 255, 255)) -> bytes:
    raw_scanlines = bytearray()
    r, g, b, a = rgba
    for _ in range(height):
        raw_scanlines.append(0)
        raw_scanlines.extend([r, g, b, a] * width)
    compressed = zlib.compress(bytes(raw_scanlines), level=6)

    def chunk(tag: bytes, data: bytes) -> bytes:
        crc = zlib.crc32(tag + data) & 0xffffffff
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", crc)

    ihdr_data = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr_data) + chunk(b"IDAT", compressed) + chunk(b"IEND", b"")


def make_jpeg_bytes(width: int, height: int) -> bytes:
    return (
        bytes([
            0xFF, 0xD8,
            0xFF, 0xE0, 0x00, 0x10, 0x4A, 0x46, 0x49, 0x46, 0x00, 0x01, 0x01, 0x01, 0x00, 0x48, 0x00, 0x48, 0x00, 0x00,
            0xFF, 0xC0, 0x00, 0x0B, 0x08,
        ])
        + struct.pack(">HH", height, width)
        + bytes([0x01, 0x01, 0x11, 0x00, 0xFF, 0xD9])
    )


def make_webp_vp8_bytes(width: int, height: int) -> bytes:
    hdr = (
        bytes([
            0x52, 0x49, 0x46, 0x46,
            0x1E, 0x00, 0x00, 0x00,
            0x57, 0x45, 0x42, 0x50,
            0x56, 0x50, 0x38, 0x20,
            0x12, 0x00, 0x00, 0x00,
            0x30, 0x01, 0x00,
            0x9D, 0x01, 0x2A
        ])
        + struct.pack("<HH", width & 0x3FFF, height & 0x3FFF)
        + b"\x00" * 10
    )
    return hdr


def make_webp_vp8l_bytes(width: int, height: int) -> bytes:
    w_m1 = (width - 1) & 0x3FFF
    h_m1 = (height - 1) & 0x3FFF
    b0 = w_m1 & 0xFF
    b1 = ((w_m1 >> 8) & 0x3F) | ((h_m1 & 0x03) << 6)
    b2 = (h_m1 >> 2) & 0xFF
    b3 = (h_m1 >> 10) & 0x0F
    payload = bytes([0x2F, b0, b1, b2, b3]) + b"\x00" * 9
    hdr = (
        b"RIFF"
        + struct.pack("<I", len(payload) + 12)
        + b"WEBPVP8L"
        + struct.pack("<I", len(payload))
        + payload
    )
    return hdr


def make_animated_webp_bytes(width: int, height: int) -> bytes:
    flags = 0x02  # animation bit set
    w_m1 = width - 1
    h_m1 = height - 1
    vp8x_data = bytes([
        flags, 0, 0, 0,
        w_m1 & 0xFF, (w_m1 >> 8) & 0xFF, (w_m1 >> 16) & 0xFF,
        h_m1 & 0xFF, (h_m1 >> 8) & 0xFF, (h_m1 >> 16) & 0xFF
    ])
    chunk_vp8x = b"VP8X" + struct.pack("<I", 10) + vp8x_data
    total_size = len(b"WEBP") + len(chunk_vp8x)
    return b"RIFF" + struct.pack("<I", total_size) + b"WEBP" + chunk_vp8x


def make_base_doc(doc_id: str, title: str, assets: list):
    for a in assets:
        if "provenance" not in a:
            a["provenance"] = {"label": "Media Spec v3"}
    return {
        "format": "paralleldoc",
        "version": "3.0",
        "metadata": {
            "document_id": doc_id,
            "revision": "rev-1",
            "title": title,
            "author_refs": ["auth-m-01"]
        },
        "authors": [{"id": "auth-m-01", "kind": "tool", "name": "Media Contract Tester"}],
        "units": [
            {
                "id": "u-m-01",
                "kind": "source",
                "title": "Media Demonstration Clause",
                "text": "Clause referencing test raster assets.",
                "text_format": "plain",
                "author_refs": ["auth-m-01"],
                "epistemic": "reported",
                "status": "reviewed",
                "source_refs": [],
                "asset_ids": [a["id"] for a in assets],
                "provenance": {"label": "Media Spec v3"}
            }
        ],
        "groups": [{"id": "g-m-01", "title": "Media Test Group", "unit_refs": ["u-m-01"]}],
        "visuals": [],
        "assets": assets,
        "profiles": []
    }


def generate_corpus_m(target_dir: Path):
    target_dir.mkdir(parents=True, exist_ok=True)
    results = []

    def write_fixture(fname: str, doc: dict, expected_code: str = "OK"):
        raw_b = json.dumps(doc, indent=2, ensure_ascii=False).encode("utf-8")
        (target_dir / fname).write_bytes(raw_b)
        results.append({
            "file": fname,
            "bytes": len(raw_b),
            "sha256": hashlib.sha256(raw_b).hexdigest().lower(),
            "expected_code": expected_code
        })

    # 01: Valid PNG
    png_b = make_png_bytes(240, 140)
    write_fixture("m01_valid_png.json", make_base_doc("m-01", "Valid PNG Asset", [{
        "id": "ast-01",
        "mime": "image/png",
        "sha256": hashlib.sha256(png_b).hexdigest().lower(),
        "byte_length": len(png_b),
        "width": 240, "height": 140,
        "alt": "Valid test PNG thumbnail",
        "caption": "Figure 1: Valid PNG",
        "author_refs": ["auth-m-01"],
        "locator": {"mode": "embedded", "data_uri": f"data:image/png;base64,{base64.b64encode(png_b).decode('ascii')}"}
    }]), "OK")

    # 02: Valid JPEG
    jpeg_b = make_jpeg_bytes(160, 100)
    write_fixture("m02_valid_jpeg.json", make_base_doc("m-02", "Valid JPEG Asset", [{
        "id": "ast-02",
        "mime": "image/jpeg",
        "sha256": hashlib.sha256(jpeg_b).hexdigest().lower(),
        "byte_length": len(jpeg_b),
        "width": 160, "height": 100,
        "alt": "Valid test JPEG thumbnail",
        "caption": "Figure 2: Valid JPEG",
        "author_refs": ["auth-m-01"],
        "locator": {"mode": "embedded", "data_uri": f"data:image/jpeg;base64,{base64.b64encode(jpeg_b).decode('ascii')}"}
    }]), "OK")

    # 03: Valid WebP VP8
    webp_vp8_b = make_webp_vp8_bytes(180, 90)
    write_fixture("m03_valid_webp_vp8.json", make_base_doc("m-03", "Valid WebP VP8 Asset", [{
        "id": "ast-03",
        "mime": "image/webp",
        "sha256": hashlib.sha256(webp_vp8_b).hexdigest().lower(),
        "byte_length": len(webp_vp8_b),
        "width": 180, "height": 90,
        "alt": "Valid test WebP VP8 thumbnail",
        "caption": "Figure 3: Valid WebP VP8",
        "author_refs": ["auth-m-01"],
        "locator": {"mode": "embedded", "data_uri": f"data:image/webp;base64,{base64.b64encode(webp_vp8_b).decode('ascii')}"}
    }]), "OK")

    # 04: Valid WebP VP8L
    webp_vp8l_b = make_webp_vp8l_bytes(100, 100)
    write_fixture("m04_valid_webp_vp8l.json", make_base_doc("m-04", "Valid WebP VP8L Asset", [{
        "id": "ast-04",
        "mime": "image/webp",
        "sha256": hashlib.sha256(webp_vp8l_b).hexdigest().lower(),
        "byte_length": len(webp_vp8l_b),
        "width": 100, "height": 100,
        "alt": "Valid test WebP VP8L thumbnail",
        "caption": "Figure 4: Valid WebP VP8L",
        "author_refs": ["auth-m-01"],
        "locator": {"mode": "embedded", "data_uri": f"data:image/webp;base64,{base64.b64encode(webp_vp8l_b).decode('ascii')}"}
    }]), "OK")

    # 05: Valid Transparent PNG
    png_trans_b = make_png_bytes(100, 100, (0, 0, 0, 0))
    write_fixture("m05_valid_transparent_png.json", make_base_doc("m-05", "Valid Transparent PNG Asset", [{
        "id": "ast-05",
        "mime": "image/png",
        "sha256": hashlib.sha256(png_trans_b).hexdigest().lower(),
        "byte_length": len(png_trans_b),
        "width": 100, "height": 100,
        "alt": "Transparent PNG with alpha=0",
        "caption": "Figure 5: Transparent PNG",
        "author_refs": ["auth-m-01"],
        "locator": {"mode": "embedded", "data_uri": f"data:image/png;base64,{base64.b64encode(png_trans_b).decode('ascii')}"}
    }]), "OK")

    # 06: Valid Extreme Aspect Ratios
    png_wide_b = make_png_bytes(1200, 200)
    png_tall_b = make_png_bytes(200, 800)
    write_fixture("m06_valid_aspect_ratios.json", make_base_doc("m-06", "Extreme Aspect Ratios", [
        {
            "id": "ast-06-wide",
            "mime": "image/png",
            "sha256": hashlib.sha256(png_wide_b).hexdigest().lower(),
            "byte_length": len(png_wide_b),
            "width": 1200, "height": 200,
            "alt": "Ultra wide panoramic image",
            "caption": "Figure 6a: 6:1 wide",
            "author_refs": ["auth-m-01"],
            "locator": {"mode": "embedded", "data_uri": f"data:image/png;base64,{base64.b64encode(png_wide_b).decode('ascii')}"}
        },
        {
            "id": "ast-06-tall",
            "mime": "image/png",
            "sha256": hashlib.sha256(png_tall_b).hexdigest().lower(),
            "byte_length": len(png_tall_b),
            "width": 200, "height": 800,
            "alt": "Tall portrait image",
            "caption": "Figure 6b: 1:4 portrait",
            "author_refs": ["auth-m-01"],
            "locator": {"mode": "embedded", "data_uri": f"data:image/png;base64,{base64.b64encode(png_tall_b).decode('ascii')}"}
        }
    ]), "OK")

    # 07: Corrupted Base64 Syntax
    write_fixture("m07_corrupted_base64_syntax.json", make_base_doc("m-07", "Corrupted Base64", [{
        "id": "ast-07",
        "mime": "image/png",
        "sha256": "0000000000000000000000000000000000000000000000000000000000000000",
        "byte_length": 100,
        "width": 100, "height": 100,
        "alt": "Corrupted Base64 syntax",
        "caption": "Error Card 07",
        "author_refs": ["auth-m-01"],
        "locator": {"mode": "embedded", "data_uri": "data:image/png;base64,iVBORw0KGgo%%%INVALID_CHARS%%%"}
    }]), "ERR_ASSET_CORRUPTED_BASE64")

    # 08: Corrupted Base64 Truncated Stream
    trunc_b = png_b[:14]  # Truncated PNG header
    write_fixture("m08_corrupted_base64_truncated.json", make_base_doc("m-08", "Truncated Stream", [{
        "id": "ast-08",
        "mime": "image/png",
        "sha256": hashlib.sha256(trunc_b).hexdigest().lower(),
        "byte_length": len(trunc_b),
        "width": 240, "height": 140,
        "alt": "Truncated PNG bytes",
        "caption": "Error Card 08",
        "author_refs": ["auth-m-01"],
        "locator": {"mode": "embedded", "data_uri": f"data:image/png;base64,{base64.b64encode(trunc_b).decode('ascii')}"}
    }]), "ERR_ASSET_CORRUPTED_BASE64")

    # 09: MIME Spoofing PNG declared as JPEG
    write_fixture("m09_mime_spoofing_png_as_jpeg.json", make_base_doc("m-09", "MIME Spoofing PNG as JPEG", [{
        "id": "ast-09",
        "mime": "image/jpeg",
        "sha256": hashlib.sha256(png_b).hexdigest().lower(),
        "byte_length": len(png_b),
        "width": 240, "height": 140,
        "alt": "PNG declared as JPEG",
        "caption": "Error Card 09",
        "author_refs": ["auth-m-01"],
        "locator": {"mode": "embedded", "data_uri": f"data:image/jpeg;base64,{base64.b64encode(png_b).decode('ascii')}"}
    }]), "ERR_ASSET_MIME_SPOOFING")

    # 10: MIME Spoofing JPEG declared as PNG
    write_fixture("m10_mime_spoofing_jpeg_as_png.json", make_base_doc("m-10", "MIME Spoofing JPEG as PNG", [{
        "id": "ast-10",
        "mime": "image/png",
        "sha256": hashlib.sha256(jpeg_b).hexdigest().lower(),
        "byte_length": len(jpeg_b),
        "width": 160, "height": 100,
        "alt": "JPEG declared as PNG",
        "caption": "Error Card 10",
        "author_refs": ["auth-m-01"],
        "locator": {"mode": "embedded", "data_uri": f"data:image/png;base64,{base64.b64encode(jpeg_b).decode('ascii')}"}
    }]), "ERR_ASSET_MIME_SPOOFING")

    # 11: MIME Spoofing WebP declared as PNG
    write_fixture("m11_mime_spoofing_webp_as_png.json", make_base_doc("m-11", "MIME Spoofing WebP as PNG", [{
        "id": "ast-11",
        "mime": "image/png",
        "sha256": hashlib.sha256(webp_vp8_b).hexdigest().lower(),
        "byte_length": len(webp_vp8_b),
        "width": 180, "height": 90,
        "alt": "WebP declared as PNG",
        "caption": "Error Card 11",
        "author_refs": ["auth-m-01"],
        "locator": {"mode": "embedded", "data_uri": f"data:image/png;base64,{base64.b64encode(webp_vp8_b).decode('ascii')}"}
    }]), "ERR_ASSET_MIME_SPOOFING")

    # 12: Unsupported GIF bytes declared as PNG
    gif_b = b"GIF89a\x01\x00\x01\x00\x80\x00\x00\x00\x00\x00\xff\xff\xff!\xf9\x04\x01\x00\x00\x00\x00,\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;"
    write_fixture("m12_mime_unsupported_gif.json", make_base_doc("m-12", "Unsupported GIF bytes", [{
        "id": "ast-12",
        "mime": "image/png",
        "sha256": hashlib.sha256(gif_b).hexdigest().lower(),
        "byte_length": len(gif_b),
        "width": 1, "height": 1,
        "alt": "GIF89a payload declared as PNG",
        "caption": "Error Card 12",
        "author_refs": ["auth-m-01"],
        "locator": {"mode": "embedded", "data_uri": f"data:image/png;base64,{base64.b64encode(gif_b).decode('ascii')}"}
    }]), "ERR_ASSET_MIME_SPOOFING")

    # 13: Wrong SHA-256
    tampered_sha = hashlib.sha256(png_b).hexdigest().lower()[:-4] + "ffff"
    write_fixture("m13_wrong_sha256.json", make_base_doc("m-13", "Wrong SHA-256", [{
        "id": "ast-13",
        "mime": "image/png",
        "sha256": tampered_sha,
        "byte_length": len(png_b),
        "width": 240, "height": 140,
        "alt": "Tampered SHA-256",
        "caption": "Error Card 13",
        "author_refs": ["auth-m-01"],
        "locator": {"mode": "embedded", "data_uri": f"data:image/png;base64,{base64.b64encode(png_b).decode('ascii')}"}
    }]), "ERR_ASSET_HASH_MISMATCH")

    # 14: Wrong Dimensions
    write_fixture("m14_wrong_dimensions.json", make_base_doc("m-14", "Wrong Dimensions", [{
        "id": "ast-14",
        "mime": "image/png",
        "sha256": hashlib.sha256(png_b).hexdigest().lower(),
        "byte_length": len(png_b),
        "width": 400, "height": 300,  # actual 240x140
        "alt": "Dimension mismatch",
        "caption": "Error Card 14",
        "author_refs": ["auth-m-01"],
        "locator": {"mode": "embedded", "data_uri": f"data:image/png;base64,{base64.b64encode(png_b).decode('ascii')}"}
    }]), "ERR_ASSET_DIMENSIONS_MISMATCH")

    # 15: Wrong Byte Length
    write_fixture("m15_wrong_byte_length.json", make_base_doc("m-15", "Wrong Byte Length", [{
        "id": "ast-15",
        "mime": "image/png",
        "sha256": hashlib.sha256(png_b).hexdigest().lower(),
        "byte_length": 99999,  # actual len(png_b)
        "width": 240, "height": 140,
        "alt": "Byte length mismatch",
        "caption": "Error Card 15",
        "author_refs": ["auth-m-01"],
        "locator": {"mode": "embedded", "data_uri": f"data:image/png;base64,{base64.b64encode(png_b).decode('ascii')}"}
    }]), "ERR_ASSET_BYTE_LENGTH_MISMATCH")

    # 16: Animated WebP Rejected
    anim_webp_b = make_animated_webp_bytes(100, 100)
    write_fixture("m16_animated_webp_rejected.json", make_base_doc("m-16", "Animated WebP", [{
        "id": "ast-16",
        "mime": "image/webp",
        "sha256": hashlib.sha256(anim_webp_b).hexdigest().lower(),
        "byte_length": len(anim_webp_b),
        "width": 100, "height": 100,
        "alt": "Animated WebP image",
        "caption": "Error Card 16",
        "author_refs": ["auth-m-01"],
        "locator": {"mode": "embedded", "data_uri": f"data:image/webp;base64,{base64.b64encode(anim_webp_b).decode('ascii')}"}
    }]), "ERR_ASSET_ANIMATED_WEBP")

    # 17: Single Asset Size Budget Exceeded (>8 MiB: 9.0 MB)
    raw_9mb = b"A" * 9000000
    b64_9mb = base64.b64encode(raw_9mb).decode("ascii")
    write_fixture("m17_budget_single_asset_exceeded.json", make_base_doc("m-17", "Single Asset Budget Exceeded", [{
        "id": "ast-17",
        "mime": "image/png",
        "sha256": "0000000000000000000000000000000000000000000000000000000000000000",
        "byte_length": len(raw_9mb),
        "width": 100, "height": 100,
        "alt": "Single asset > 8 MiB",
        "caption": "Error Card 17",
        "author_refs": ["auth-m-01"],
        "locator": {"mode": "embedded", "data_uri": f"data:image/png;base64,{b64_9mb}"}
    }]), "ERR_ASSET_SIZE_BUDGET_EXCEEDED")

    # 18: Total Assets Budget Exceeded (>32 MiB: 5 assets of ~7 MiB each)
    raw_7mb = b"B" * 7000000
    b64_7mb = base64.b64encode(raw_7mb).decode("ascii")
    assets_35mb = []
    for i in range(5):
        assets_35mb.append({
            "id": f"ast-18-{i}",
            "mime": "image/png",
            "sha256": "0000000000000000000000000000000000000000000000000000000000000000",
            "byte_length": len(raw_7mb),
            "width": 100, "height": 100,
            "alt": f"Asset {i} of 35MB budget test",
            "caption": f"Asset 18-{i}",
            "author_refs": ["auth-m-01"],
            "locator": {"mode": "embedded", "data_uri": f"data:image/png;base64,{b64_7mb}"}
        })
    write_fixture("m18_budget_total_assets_exceeded.json", make_base_doc("m-18", "Total Assets Budget Exceeded", assets_35mb), "ERR_DOC_MEDIA_BUDGET_EXCEEDED")

    # 19: Asset Count Budget Exceeded (51 assets > 50 max)
    assets_51 = []
    for i in range(51):
        assets_51.append({
            "id": f"ast-19-{i:02d}",
            "mime": "image/png",
            "sha256": hashlib.sha256(png_b).hexdigest().lower(),
            "byte_length": len(png_b),
            "width": 240, "height": 140,
            "alt": f"Asset {i}",
            "caption": f"Asset {i}",
            "author_refs": ["auth-m-01"],
            "locator": {"mode": "embedded", "data_uri": f"data:image/png;base64,{base64.b64encode(png_b).decode('ascii')}"}
        })
    write_fixture("m19_budget_asset_count_exceeded.json", make_base_doc("m-19", "Asset Count Budget Exceeded", assets_51), "ERR_DOC_ASSET_COUNT_EXCEEDED")

    # 20: Megapixels Exceeded (5000x4000 = 20 MP > 16 MP limit)
    write_fixture("m20_budget_megapixels_exceeded.json", make_base_doc("m-20", "Megapixels Budget Exceeded", [{
        "id": "ast-20",
        "mime": "image/png",
        "sha256": hashlib.sha256(png_b).hexdigest().lower(),
        "byte_length": len(png_b),
        "width": 5000, "height": 4000,
        "alt": "20 Megapixel image",
        "caption": "Error Card 20",
        "author_refs": ["auth-m-01"],
        "locator": {"mode": "embedded", "data_uri": f"data:image/png;base64,{base64.b64encode(png_b).decode('ascii')}"}
    }]), "ERR_ASSET_DIMENSIONS_EXCEEDED")

    # 21: Dimension Side Exceeded (9000x100 > 8192 px limit)
    write_fixture("m21_budget_dimension_side_exceeded.json", make_base_doc("m-21", "Dimension Side Budget Exceeded", [{
        "id": "ast-21",
        "mime": "image/png",
        "sha256": hashlib.sha256(png_b).hexdigest().lower(),
        "byte_length": len(png_b),
        "width": 9000, "height": 100,
        "alt": "9000px side image",
        "caption": "Error Card 21",
        "author_refs": ["auth-m-01"],
        "locator": {"mode": "embedded", "data_uri": f"data:image/png;base64,{base64.b64encode(png_b).decode('ascii')}"}
    }]), "ERR_ASSET_DIMENSIONS_EXCEEDED")

    # 22: Forbidden Locator Windows Drive
    write_fixture("m22_locator_forbidden_absolute_windows.json", make_base_doc("m-22", "Forbidden Windows Path", [{
        "id": "ast-22",
        "mime": "image/png",
        "sha256": hashlib.sha256(png_b).hexdigest().lower(),
        "byte_length": len(png_b),
        "width": 240, "height": 140,
        "alt": "Windows drive locator",
        "caption": "Error Card 22",
        "author_refs": ["auth-m-01"],
        "locator": {"mode": "relative", "path": "C:\\images\\diagram.png"}
    }]), "ERR_FORBIDDEN_ASSET_LOCATOR")

    # 23: Forbidden Locator UNC / File / Traversal
    write_fixture("m23_locator_forbidden_unc_file_traversal.json", make_base_doc("m-23", "Forbidden UNC / Traversal", [{
        "id": "ast-23",
        "mime": "image/png",
        "sha256": hashlib.sha256(png_b).hexdigest().lower(),
        "byte_length": len(png_b),
        "width": 240, "height": 140,
        "alt": "UNC share path",
        "caption": "Error Card 23",
        "author_refs": ["auth-m-01"],
        "locator": {"mode": "relative", "path": "\\\\smb-server\\share\\img.png"}
    }]), "ERR_FORBIDDEN_ASSET_LOCATOR")

    # 24: Forbidden Locator Credentials in URL
    write_fixture("m24_locator_forbidden_credentials.json", make_base_doc("m-24", "Forbidden Credentials URL", [{
        "id": "ast-24",
        "mime": "image/png",
        "sha256": hashlib.sha256(png_b).hexdigest().lower(),
        "byte_length": len(png_b),
        "width": 240, "height": 140,
        "alt": "URL with credentials",
        "caption": "Error Card 24",
        "author_refs": ["auth-m-01"],
        "locator": {"mode": "external", "url": "https://admin:secretpass@cloud-storage.com/asset.png"}
    }]), "ERR_FORBIDDEN_ASSET_LOCATOR")

    # Control table
    (target_dir / "corpus_M_control.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(f"Corpus M successfully materialized in {target_dir} ({len(results)} fixtures).")


if __name__ == "__main__":
    generate_corpus_m(Path("fixtures/corpus_M"))
