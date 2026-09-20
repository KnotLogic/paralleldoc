"""
fixtures/generate_corpus_e.py — Generator for Corpus E (14 Structural & Semantic Error Fixtures).
Materializes 14 error fixtures verifying JSON syntax error handling, V3 format guard rejection (§9),
Draft 2020-12 schema enforcement (§8), referential integrity errors (dangling unit/author/asset refs, duplicate IDs),
orphan unit reconciliation under «Вне групп», explicit missing role badge («Нет анализа»),
and simultaneous multi-error handling (digest mismatch + corrupted media asset).
Complies strictly with Spec r2 §4, §7, §8, §9, §11 (AC-02, AC-07, AC-08, AC-11, AC-28).
"""

import hashlib
import json
from pathlib import Path


def make_valid_base_doc():
    return {
        "format": "paralleldoc",
        "version": "3.0",
        "metadata": {
            "document_id": "doc-error-test-base",
            "revision": "rev-1",
            "title": "Error Test Base Document",
            "author_refs": ["auth-e-01"]
        },
        "authors": [{"id": "auth-e-01", "kind": "tool", "name": "Error Fixture Generator"}],
        "units": [
            {
                "id": "u-e-01",
                "kind": "source",
                "title": "Source Clause",
                "text": "Base source text for error testing.",
                "text_format": "plain",
                "author_refs": ["auth-e-01"],
                "epistemic": "reported",
                "status": "reviewed",
                "source_refs": [],
                "asset_ids": [],
                "provenance": {"label": "Base Spec"}
            },
            {
                "id": "u-e-02",
                "kind": "model",
                "title": "Model Unit",
                "text": "Base model unit text.",
                "text_format": "markdown-safe",
                "author_refs": ["auth-e-01"],
                "epistemic": "hypothesis",
                "status": "reviewed",
                "source_refs": [],
                "asset_ids": []
            },
            {
                "id": "u-e-03",
                "kind": "analysis",
                "title": "Analysis Unit",
                "text": "Base analysis unit text.",
                "text_format": "plain",
                "author_refs": ["auth-e-01"],
                "epistemic": "supported",
                "status": "reviewed",
                "source_refs": ["u-e-01"],
                "asset_ids": []
            },
            {
                "id": "u-e-04",
                "kind": "action",
                "title": "Action Unit",
                "text": "Base action unit text.",
                "text_format": "plain",
                "author_refs": ["auth-e-01"],
                "epistemic": "not-applicable",
                "status": "draft",
                "source_refs": [],
                "asset_ids": []
            }
        ],
        "groups": [
            {"id": "g-e-01", "title": "Base Error Group", "unit_refs": ["u-e-01", "u-e-02", "u-e-03", "u-e-04"]}
        ],
        "visuals": [],
        "assets": [],
        "profiles": []
    }


def generate_corpus_e(target_dir: Path):
    target_dir.mkdir(parents=True, exist_ok=True)
    results = []

    def record_fixture(fname: str, raw_bytes: bytes, error_category: str, expected_diag: str):
        (target_dir / fname).write_bytes(raw_bytes)
        results.append({
            "file": fname,
            "bytes": len(raw_bytes),
            "sha256": hashlib.sha256(raw_bytes).hexdigest().lower(),
            "category": error_category,
            "expected_diagnostic": expected_diag
        })

    # e01: Invalid JSON syntax (trailing comma, unclosed object)
    raw_e01 = b'{\n  "format": "paralleldoc",\n  "version": "3.0",\n  "metadata": {\n    "title": "Broken syntax",\n'
    record_fixture("e01_invalid_json_syntax.json", raw_e01, "SYNTAX_ERROR", "Синтаксическая ошибка JSON")

    # e02: Missing format field
    doc_e02 = make_valid_base_doc()
    del doc_e02["format"]
    b_e02 = json.dumps(doc_e02, indent=2, ensure_ascii=False).encode("utf-8")
    record_fixture("e02_missing_format_field.json", b_e02, "FORMAT_GUARD", "«Неподдерживаемый формат; требуется ParallelDoc 3.0»")

    # e03: Invalid format field value ("cockpit-v1")
    doc_e03 = make_valid_base_doc()
    doc_e03["format"] = "cockpit-v1"
    b_e03 = json.dumps(doc_e03, indent=2, ensure_ascii=False).encode("utf-8")
    record_fixture("e03_invalid_format_field.json", b_e03, "FORMAT_GUARD", "«Неподдерживаемый формат; требуется ParallelDoc 3.0»")

    # e04: Unknown version field ("2.1")
    doc_e04 = make_valid_base_doc()
    doc_e04["version"] = "2.1"
    b_e04 = json.dumps(doc_e04, indent=2, ensure_ascii=False).encode("utf-8")
    record_fixture("e04_unknown_version_field.json", b_e04, "VERSION_GUARD", "«Неподдерживаемый формат; требуется ParallelDoc 3.0»")

    # e05: Legacy v2.1 document (columns, items, metadata)
    doc_e05 = {
        "$schema": "https://antigravity.local/schemas/cockpit-v1.json",
        "metadata": {"title": "Legacy v2.1 Document", "document_id": "legacy-doc-01"},
        "columns": [
            {"key": "col1", "title": "Original Clause", "width_weight": 50},
            {"key": "col2", "title": "Translation", "width_weight": 50}
        ],
        "items": [
            {"id": "1", "col1": "Original source text", "col2": "Translated text"}
        ]
    }
    b_e05 = json.dumps(doc_e05, indent=2, ensure_ascii=False).encode("utf-8")
    record_fixture("e05_legacy_v21_document.json", b_e05, "LEGACY_V21", "«Неподдерживаемый формат; требуется ParallelDoc 3.0»")

    # e06: Legacy v2.1 with added v3 header (tampered)
    doc_e06 = {
        "format": "paralleldoc",
        "version": "3.0",
        "metadata": {"document_id": "doc-tampered-v21", "revision": "rev-1", "title": "Tampered Legacy Doc", "author_refs": ["auth-01"]},
        "authors": [{"id": "auth-01", "kind": "human", "name": "Author"}],
        "columns": [{"key": "c1", "title": "Col 1"}],
        "items": [{"id": "item-1", "c1": "Val"}]
    }
    b_e06 = json.dumps(doc_e06, indent=2, ensure_ascii=False).encode("utf-8")
    record_fixture("e06_legacy_with_v3_header_tamper.json", b_e06, "SCHEMA_ADDITIONAL_PROPERTIES", "additionalProperties: columns, items")

    # e07: Schema missing required collections (missing "groups")
    doc_e07 = make_valid_base_doc()
    del doc_e07["groups"]
    b_e07 = json.dumps(doc_e07, indent=2, ensure_ascii=False).encode("utf-8")
    record_fixture("e07_schema_missing_required_collections.json", b_e07, "SCHEMA_REQUIRED_MISSING", "required: groups")

    # e08: Dangling unit_refs in group
    doc_e08 = make_valid_base_doc()
    doc_e08["groups"][0]["unit_refs"].append("u-nonexistent-99")
    b_e08 = json.dumps(doc_e08, indent=2, ensure_ascii=False).encode("utf-8")
    record_fixture("e08_dangling_unit_refs.json", b_e08, "REFERENTIAL_INTEGRITY", "ERR_DANGLING_REF: u-nonexistent-99")

    # e09: Dangling author_refs in unit
    doc_e09 = make_valid_base_doc()
    doc_e09["units"][0]["author_refs"].append("auth-nonexistent-99")
    b_e09 = json.dumps(doc_e09, indent=2, ensure_ascii=False).encode("utf-8")
    record_fixture("e09_dangling_author_refs.json", b_e09, "REFERENTIAL_INTEGRITY", "ERR_DANGLING_REF: auth-nonexistent-99")

    # e10: Dangling asset_ids in unit
    doc_e10 = make_valid_base_doc()
    doc_e10["units"][0]["asset_ids"].append("ast-nonexistent-99")
    b_e10 = json.dumps(doc_e10, indent=2, ensure_ascii=False).encode("utf-8")
    record_fixture("e10_dangling_asset_ids.json", b_e10, "REFERENTIAL_INTEGRITY", "ERR_DANGLING_REF: ast-nonexistent-99")

    # e11: Orphan unit (unit present in units[] but omitted from all groups)
    doc_e11 = make_valid_base_doc()
    doc_e11["units"].append({
        "id": "u-orphan-77",
        "kind": "action",
        "title": "Orphan Action Unit",
        "text": "This unit is not referenced in any group and must be reconciled under «Вне групп».",
        "text_format": "plain",
        "author_refs": ["auth-e-01"],
        "epistemic": "not-applicable",
        "status": "draft",
        "source_refs": [],
        "asset_ids": []
    })
    b_e11 = json.dumps(doc_e11, indent=2, ensure_ascii=False).encode("utf-8")
    record_fixture("e11_orphan_unit.json", b_e11, "ORPHAN_RECONCILIATION", "Reconciled under «Вне групп»")

    # e12: Duplicate IDs in units collection
    doc_e12 = make_valid_base_doc()
    doc_e12["units"][1]["id"] = "u-e-01"  # duplicate ID
    b_e12 = json.dumps(doc_e12, indent=2, ensure_ascii=False).encode("utf-8")
    record_fixture("e12_duplicate_ids.json", b_e12, "DUPLICATE_ID", "ERR_DUPLICATE_ID: u-e-01")

    # e13: Missing analysis role (has source, model, action, but no analysis)
    doc_e13 = make_valid_base_doc()
    doc_e13["units"] = [u for u in doc_e13["units"] if u["kind"] != "analysis"]
    doc_e13["groups"][0]["unit_refs"] = [u["id"] for u in doc_e13["units"]]
    b_e13 = json.dumps(doc_e13, indent=2, ensure_ascii=False).encode("utf-8")
    record_fixture("e13_missing_analysis_role.json", b_e13, "MISSING_ROLE_BADGE", "Badge «Нет анализа»")

    # e14: Simultaneous mismatch + corrupted asset error
    doc_e14 = make_valid_base_doc()
    doc_e14["assets"] = [{
        "id": "ast-broken-01",
        "mime": "image/png",
        "sha256": "0000000000000000000000000000000000000000000000000000000000000000",
        "byte_length": 50,
        "width": 10, "height": 10,
        "alt": "Corrupted broken asset",
        "caption": "Broken Asset Error Card",
        "author_refs": ["auth-e-01"],
        "provenance": {"label": "Base Spec"},
        "locator": {"mode": "embedded", "data_uri": "data:image/png;base64,iVBORw0KGgo%%%INVALID_BASE64%%%"}
    }]
    doc_e14["units"][0]["asset_ids"] = ["ast-broken-01"]
    b_e14 = json.dumps(doc_e14, indent=2, ensure_ascii=False).encode("utf-8")
    record_fixture("e14_simultaneous_mismatch_and_asset_error.json", b_e14, "MULTI_ERROR", "Simultaneous SHA mismatch + Asset error")

    # Companion manifest for e14 with deliberate mismatch
    manifest_e14 = {
        "format": "paralleldoc-integrity-1",
        "algorithm": "SHA-256",
        "scope": "raw-bytes",
        "expected_sha256": "deadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeef",
        "document_id": "doc-error-test-base",
        "revision": "rev-1"
    }
    (target_dir / "e14_manifest_mismatch.json").write_text(json.dumps(manifest_e14, indent=2), encoding="utf-8")

    # Control table
    (target_dir / "corpus_E_control.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(f"Corpus E successfully materialized in {target_dir} ({len(results)} fixtures + 1 manifest).")


if __name__ == "__main__":
    generate_corpus_e(Path("fixtures/corpus_E"))
