"""
fixtures/generate_corpus_v.py — Generator for Corpus V (Valid Variants).
Materializes 11 valid v3.0 documents, detached manifest, LF/CRLF/BOM byte variants,
and control verification table per Spec r2 §8, §9, §11 (AC-02, AC-07, AC-08, AC-25, AC-26, AC-46).
"""

import hashlib
import json
from pathlib import Path


def get_base_v08_doc():
    return {
        "format": "paralleldoc",
        "version": "3.0",
        "metadata": {
            "document_id": "v-doc-08-base",
            "revision": "rev-1",
            "title": "Corpus V08 Canonical Byte Variant Document",
            "created_at": "2026-09-06T18:00:00Z",
            "language": "ru",
            "author_refs": ["auth-v-01"]
        },
        "authors": [
            {"id": "auth-v-01", "kind": "human", "name": "Corpus V Lead Evaluator"}
        ],
        "units": [
            {
                "id": "u-v08-01",
                "kind": "source",
                "title": "Baseline SLA Clause",
                "text": "Уровень доступности сервиса составляет 99.95% в месяц, без учета плановых работ.",
                "text_format": "plain",
                "author_refs": ["auth-v-01"],
                "epistemic": "reported",
                "status": "reviewed",
                "source_refs": [],
                "asset_ids": [],
                "provenance": {"label": "SLA Specification Section 1.1"}
            },
            {
                "id": "u-v08-02",
                "kind": "model",
                "title": "High Availability Topology",
                "text": "Двухузловая архитектура с автоматическим переключением отказоустойчивости.",
                "text_format": "markdown-safe",
                "author_refs": ["auth-v-01"],
                "epistemic": "hypothesis",
                "status": "reviewed",
                "source_refs": [],
                "asset_ids": []
            },
            {
                "id": "u-v08-03",
                "kind": "analysis",
                "title": "Downtime Margin Analysis",
                "text": "Допустимый суммарный простой составляет не более 21.6 минут в месяц.",
                "text_format": "plain",
                "author_refs": ["auth-v-01"],
                "epistemic": "supported",
                "status": "reviewed",
                "source_refs": ["u-v08-01"],
                "asset_ids": []
            },
            {
                "id": "u-v08-04",
                "kind": "action",
                "title": "Monitoring Threshold Alert",
                "text": "Настройка алерта на порог 15 минут времени недоступности.",
                "text_format": "plain",
                "author_refs": ["auth-v-01"],
                "epistemic": "not-applicable",
                "status": "draft",
                "source_refs": [],
                "asset_ids": []
            }
        ],
        "groups": [
            {
                "id": "g-v08-01",
                "title": "SLA Core Evaluation Group",
                "unit_refs": ["u-v08-01", "u-v08-02", "u-v08-03", "u-v08-04"]
            }
        ],
        "visuals": [
            {
                "id": "vis-v08-01",
                "type": "relationship-graph",
                "title": "SLA Verification Logic",
                "question": "Обеспечивает ли Multi-AZ заданный уровень 99.95%?",
                "fallback": "Таблица взаимосвязей требований SLA и архитектуры.",
                "owner_unit_id": "u-v08-02",
                "author_refs": ["auth-v-01"],
                "nodes": [
                    {"id": "node-01", "label": "Clause 1.1", "unit_refs": ["u-v08-01"]},
                    {"id": "node-02", "label": "Downtime Calc", "unit_refs": ["u-v08-03"]}
                ],
                "edges": [
                    {
                        "id": "edge-01",
                        "from": "node-01",
                        "to": "node-02",
                        "relation": "supports",
                        "label": "Calculated from specification",
                        "unit_refs": ["u-v08-01", "u-v08-03"]
                    }
                ]
            }
        ],
        "assets": [],
        "profiles": []
    }


def generate_corpus_v(target_dir: Path):
    target_dir.mkdir(parents=True, exist_ok=True)

    # v01: Minimal empty collections
    v01 = {
        "format": "paralleldoc",
        "version": "3.0",
        "metadata": {
            "document_id": "v-doc-01-minimal",
            "revision": "rev-1",
            "title": "Corpus V01 Minimal Empty Document",
            "author_refs": ["auth-v-01"]
        },
        "authors": [{"id": "auth-v-01", "kind": "human", "name": "V Author"}],
        "units": [],
        "groups": [],
        "visuals": [],
        "assets": [],
        "profiles": []
    }
    b01 = json.dumps(v01, indent=2, ensure_ascii=False).encode("utf-8")
    (target_dir / "v01_minimal_empty_collections.json").write_bytes(b01)

    # v02: Optional fields missing
    v02 = {
        "format": "paralleldoc",
        "version": "3.0",
        "metadata": {
            "document_id": "v-doc-02-no-optionals",
            "revision": "rev-1",
            "title": "Corpus V02 Document Without Optional Fields",
            "author_refs": ["auth-v-01"]
        },
        "authors": [{"id": "auth-v-01", "kind": "tool", "name": "Audit Tool"}],
        "units": [
            {
                "id": "u-01",
                "kind": "source",
                "title": "Contract Clause",
                "text": "Basic clause without summary or supersedes.",
                "text_format": "plain",
                "author_refs": ["auth-v-01"],
                "epistemic": "reported",
                "status": "reviewed",
                "source_refs": [],
                "asset_ids": [],
                "provenance": {"label": "Contract §1"}
            },
            {
                "id": "u-02",
                "kind": "action",
                "title": "Required Action",
                "text": "Basic action without asset_ids.",
                "text_format": "plain",
                "author_refs": ["auth-v-01"],
                "epistemic": "not-applicable",
                "status": "draft",
                "source_refs": [],
                "asset_ids": []
            }
        ],
        "groups": [
            {"id": "g-01", "title": "Group 1", "unit_refs": ["u-01", "u-02"]}
        ],
        "visuals": [],
        "assets": [],
        "profiles": []
    }
    b02 = json.dumps(v02, indent=2, ensure_ascii=False).encode("utf-8")
    (target_dir / "v02_optional_fields_missing.json").write_bytes(b02)

    # v03: Namespaced extensions
    v03 = {
        "format": "paralleldoc",
        "version": "3.0",
        "metadata": {
            "document_id": "v-doc-03-extensions",
            "revision": "rev-1",
            "title": "Corpus V03 Namespaced Extensions Document",
            "author_refs": ["auth-v-01"]
        },
        "authors": [{"id": "auth-v-01", "kind": "tool", "name": "Extension Validator"}],
        "units": [
            {
                "id": "u-ext-01",
                "kind": "source",
                "title": "Extension Source Unit",
                "text": "Clause with namespaced extension data.",
                "text_format": "plain",
                "author_refs": ["auth-v-01"],
                "epistemic": "reported",
                "status": "reviewed",
                "source_refs": [],
                "asset_ids": [],
                "provenance": {"label": "Ext Ref"},
                "extensions": {
                    "astrai.org/compliance-grade": {"grade": "A+", "score": 98.5}
                }
            }
        ],
        "groups": [{"id": "g-ext-01", "title": "Extension Group", "unit_refs": ["u-ext-01"]}],
        "visuals": [],
        "assets": [],
        "profiles": [],
        "extensions": {
            "astrai.org/audit-trail": {
                "auditor": "Teamwork M5 Worker",
                "verified": True,
                "check_ids": [101, 102, 103]
            },
            "custom-vendor.com/v3-telemetry": {
                "session_id": "sess-9912"
            }
        }
    }
    b03 = json.dumps(v03, indent=2, ensure_ascii=False).encode("utf-8")
    (target_dir / "v03_namespaced_extensions.json").write_bytes(b03)

    # v04: Plain and Markdown text formats
    v04 = {
        "format": "paralleldoc",
        "version": "3.0",
        "metadata": {
            "document_id": "v-doc-04-mixed-formats",
            "revision": "rev-1",
            "title": "Corpus V04 Mixed Plain and Markdown Formats",
            "author_refs": ["auth-v-01"]
        },
        "authors": [{"id": "auth-v-01", "kind": "human", "name": "Format Specialist"}],
        "units": [
            {
                "id": "u-plain-01",
                "kind": "source",
                "title": "Plain Text Source with Indents",
                "text": "def calculate_uptime(total_seconds, downtime_seconds):\n    ratio = (total_seconds - downtime_seconds) / total_seconds\n    return ratio >= 0.9995",
                "text_format": "plain",
                "author_refs": ["auth-v-01"],
                "epistemic": "reported",
                "status": "done",
                "source_refs": [],
                "asset_ids": [],
                "provenance": {"label": "source_code.py:12"}
            },
            {
                "id": "u-md-01",
                "kind": "analysis",
                "title": "Markdown Safe Analysis Unit",
                "text": "### Вывод анализа\n\n- **Архитектура:** Multi-AZ с резервированием\n- **Надёжность:** *99.99% исторический показатель*\n- `MTTR <= 45s` при аварийном переключении",
                "text_format": "markdown-safe",
                "author_refs": ["auth-v-01"],
                "epistemic": "supported",
                "status": "reviewed",
                "source_refs": ["u-plain-01"],
                "asset_ids": []
            }
        ],
        "groups": [{"id": "g-fmt-01", "title": "Format Test Group", "unit_refs": ["u-plain-01", "u-md-01"]}],
        "visuals": [],
        "assets": [],
        "profiles": []
    }
    b04 = json.dumps(v04, indent=2, ensure_ascii=False).encode("utf-8")
    (target_dir / "v04_plain_and_markdown.json").write_bytes(b04)

    # v05: Unicode, RTL and Emoji
    v05 = {
        "format": "paralleldoc",
        "version": "3.0",
        "metadata": {
            "document_id": "v-doc-05-unicode-rtl",
            "revision": "rev-1",
            "title": "Corpus V05 Многоязычный документ с RTL и Emoji 🏳️‍🌈⚡🛡️",
            "language": "mul",
            "author_refs": ["auth-v-01"]
        },
        "authors": [{"id": "auth-v-01", "kind": "human", "name": "Global Polyglot 🌍"}],
        "units": [
            {
                "id": "u-rtl-ar",
                "kind": "source",
                "title": "المواصفات الفنية للخدمة السحابية",
                "text": "تضمن الشركة توفر الخدمة بنسبة 99.95% شهرياً مع استثناء أعمال الصيانة المجدولة مسبقاً.",
                "text_format": "plain",
                "author_refs": ["auth-v-01"],
                "epistemic": "reported",
                "status": "reviewed",
                "source_refs": [],
                "asset_ids": [],
                "provenance": {"label": "العقد رقم 42"}
            },
            {
                "id": "u-rtl-he",
                "kind": "source",
                "title": "הסכם רמת שירות (SLA)",
                "text": "זמינות השירות החודשית לא תפחת מ-99.95%, למעט זמני תחזוקה מתואמים מראש.",
                "text_format": "plain",
                "author_refs": ["auth-v-01"],
                "epistemic": "reported",
                "status": "reviewed",
                "source_refs": [],
                "asset_ids": [],
                "provenance": {"label": "נספח שירות 2"}
            },
            {
                "id": "u-cjk-zh",
                "kind": "analysis",
                "title": "高可用性技术评估",
                "text": "采用多可用区（Multi-AZ）架构设计，历史运行时间达 99.99%。数学公式: $\\sum \\Delta t \\le 21.6\\text{ min}$。",
                "text_format": "markdown-safe",
                "author_refs": ["auth-v-01"],
                "epistemic": "supported",
                "status": "reviewed",
                "source_refs": ["u-rtl-ar", "u-rtl-he"],
                "asset_ids": []
            },
            {
                "id": "u-emoji-ua",
                "kind": "action",
                "title": "Рекомендовані дії 🚀🛡️",
                "text": "Підтвердити відповідність критеріям SLA та розгорнути моніторинг Prom-SKS в реальному часі!",
                "text_format": "plain",
                "author_refs": ["auth-v-01"],
                "epistemic": "not-applicable",
                "status": "done",
                "source_refs": [],
                "asset_ids": []
            }
        ],
        "groups": [
            {
                "id": "g-multi-01",
                "title": "Международные спецификации / International Standards",
                "unit_refs": ["u-rtl-ar", "u-rtl-he", "u-cjk-zh", "u-emoji-ua"]
            }
        ],
        "visuals": [],
        "assets": [],
        "profiles": []
    }
    b05 = json.dumps(v05, indent=2, ensure_ascii=False).encode("utf-8")
    (target_dir / "v05_unicode_rtl_emoji.json").write_bytes(b05)

    # v06: Long text quotes (>1200 and >8000 chars)
    quote_1400 = ("Параграф 4.1 Соглашения об уровне обслуживания облачной инфраструктуры. " * 20)[:1450]
    quote_8500 = ("Статья 12. Регламент измерения доступности, порядок учета инцидентов и процедура компенсации штрафных баллов за время технологического простоя сервиса. " * 65)[:8600]
    v06 = {
        "format": "paralleldoc",
        "version": "3.0",
        "metadata": {
            "document_id": "v-doc-06-long-quotes",
            "revision": "rev-1",
            "title": "Corpus V06 Progressive Disclosure Long Quotes Document",
            "author_refs": ["auth-v-01"]
        },
        "authors": [{"id": "auth-v-01", "kind": "human", "name": "Legal Counsel"}],
        "units": [
            {
                "id": "u-quote-1400",
                "kind": "source",
                "title": "Medium Quote (1,450 Chars)",
                "text": quote_1400,
                "text_format": "plain",
                "author_refs": ["auth-v-01"],
                "epistemic": "reported",
                "status": "reviewed",
                "source_refs": [],
                "asset_ids": [],
                "provenance": {"label": "Legal SLA Contract §4.1"}
            },
            {
                "id": "u-quote-8500",
                "kind": "source",
                "title": "Long Benchmark Quote (8,600 Chars)",
                "text": quote_8500,
                "text_format": "plain",
                "author_refs": ["auth-v-01"],
                "epistemic": "reported",
                "status": "reviewed",
                "source_refs": [],
                "asset_ids": [],
                "provenance": {"label": "Master Cloud Service Terms Article 12"}
            }
        ],
        "groups": [
            {"id": "g-quotes-01", "title": "Legal Terms Group", "unit_refs": ["u-quote-1400", "u-quote-8500"]}
        ],
        "visuals": [],
        "assets": [],
        "profiles": []
    }
    b06 = json.dumps(v06, indent=2, ensure_ascii=False).encode("utf-8")
    (target_dir / "v06_long_text_quotes.json").write_bytes(b06)

    # v07: Valid ID patterns (extreme valid characters)
    v07 = {
        "format": "paralleldoc",
        "version": "3.0",
        "metadata": {
            "document_id": "doc:2026.09-v3_01.corp-alpha:node-99",
            "revision": "rev.1.0_final-build:2026",
            "title": "Corpus V07 Document with Extreme Valid Identifiers",
            "author_refs": ["auth.lead-eng:primary_01"]
        },
        "authors": [{"id": "auth.lead-eng:primary_01", "kind": "human", "name": "ID Syntax Tester"}],
        "units": [
            {
                "id": "u-sla.core:metric_01-alpha",
                "kind": "source",
                "title": "Extreme ID Unit 1",
                "text": "Unit testing valid ID regex pattern.",
                "text_format": "plain",
                "author_refs": ["auth.lead-eng:primary_01"],
                "epistemic": "reported",
                "status": "done",
                "source_refs": [],
                "asset_ids": [],
                "provenance": {"label": "Doc §1"}
            },
            {
                "id": "u-calc_02.risk:assessment_final",
                "kind": "analysis",
                "title": "Extreme ID Unit 2",
                "text": "Analysis unit with complex ID.",
                "text_format": "plain",
                "author_refs": ["auth.lead-eng:primary_01"],
                "epistemic": "supported",
                "status": "reviewed",
                "source_refs": ["u-sla.core:metric_01-alpha"],
                "asset_ids": []
            }
        ],
        "groups": [
            {
                "id": "g:infrastructure.compute:cluster-01",
                "title": "Extreme ID Group",
                "unit_refs": ["u-sla.core:metric_01-alpha", "u-calc_02.risk:assessment_final"]
            }
        ],
        "visuals": [],
        "assets": [],
        "profiles": []
    }
    b07 = json.dumps(v07, indent=2, ensure_ascii=False).encode("utf-8")
    (target_dir / "v07_valid_id_patterns.json").write_bytes(b07)

    # v08, v09, v10: Byte variants of canonical base document
    base_doc = get_base_v08_doc()
    base_json_str = json.dumps(base_doc, indent=2, ensure_ascii=False)

    # v08: pure LF (\x0A)
    b08 = base_json_str.replace("\r\n", "\n").encode("utf-8")
    (target_dir / "v08_byte_variant_lf.json").write_bytes(b08)
    sha08 = hashlib.sha256(b08).hexdigest().lower()

    # v09: pure CRLF (\x0D\x0A)
    b09 = base_json_str.replace("\r\n", "\n").replace("\n", "\r\n").encode("utf-8")
    (target_dir / "v09_byte_variant_crlf.json").write_bytes(b09)
    sha09 = hashlib.sha256(b09).hexdigest().lower()

    # v10: UTF-8 BOM (\xEF\xBB\xBF) prefixed to LF
    b10 = b"\xef\xbb\xbf" + b08
    (target_dir / "v10_byte_variant_bom.json").write_bytes(b10)
    sha10 = hashlib.sha256(b10).hexdigest().lower()

    assert sha08 != sha09 != sha10, "All three byte variants must yield distinct SHA-256 digests!"

    # v11: Custom profile
    v11 = {
        "format": "paralleldoc",
        "version": "3.0",
        "metadata": {
            "document_id": "v-doc-11-custom-profile",
            "revision": "rev-1",
            "title": "Corpus V11 Custom Profile Document",
            "default_profile_id": "prof-custom-3p",
            "author_refs": ["auth-v-01"]
        },
        "authors": [{"id": "auth-v-01", "kind": "human", "name": "Profile Designer"}],
        "units": [
            {
                "id": "u-11-src",
                "kind": "source",
                "title": "Requirement Clause",
                "text": "Requirements specification for cloud service availability.",
                "text_format": "plain",
                "author_refs": ["auth-v-01"],
                "epistemic": "reported",
                "status": "reviewed",
                "source_refs": [],
                "asset_ids": [],
                "provenance": {"label": "Specs v1"}
            },
            {
                "id": "u-11-mod",
                "kind": "model",
                "title": "Architecture Model",
                "text": "Graph model of infrastructure layers.",
                "text_format": "markdown-safe",
                "author_refs": ["auth-v-01"],
                "epistemic": "hypothesis",
                "status": "reviewed",
                "source_refs": [],
                "asset_ids": []
            },
            {
                "id": "u-11-act",
                "kind": "action",
                "title": "Action Items",
                "text": "Deployment and operational tasks.",
                "text_format": "plain",
                "author_refs": ["auth-v-01"],
                "epistemic": "not-applicable",
                "status": "draft",
                "source_refs": [],
                "asset_ids": []
            }
        ],
        "groups": [
            {"id": "g-11-01", "title": "Architecture Group", "unit_refs": ["u-11-src", "u-11-mod", "u-11-act"]}
        ],
        "visuals": [],
        "assets": [],
        "profiles": [
            {
                "id": "prof-custom-3p",
                "title": "3-Panel Custom Review Layout",
                "density": "dense",
                "panels": [
                    {"id": "p-spec", "title": "Specifications", "kinds": ["source"], "weight": 35},
                    {"id": "p-arch", "title": "Architecture Model", "kinds": ["model", "analysis"], "weight": 40},
                    {"id": "p-exec", "title": "Execution & Actions", "kinds": ["action"], "weight": 25}
                ]
            }
        ]
    }
    b11 = json.dumps(v11, indent=2, ensure_ascii=False).encode("utf-8")
    (target_dir / "v11_custom_profile.json").write_bytes(b11)

    # Detached manifest for v08
    manifest_v08 = {
        "format": "paralleldoc-integrity-1",
        "algorithm": "SHA-256",
        "scope": "raw-bytes",
        "expected_sha256": sha08,
        "document_id": "v-doc-08-base",
        "revision": "rev-1"
    }
    (target_dir / "corpus_V_manifest.json").write_text(json.dumps(manifest_v08, indent=2), encoding="utf-8")

    # Control JSON
    all_files = sorted([f.name for f in target_dir.glob("*.json") if f.name != "corpus_V_control.json"])
    control_table = []
    for fn in all_files:
        raw_b = (target_dir / fn).read_bytes()
        sha = hashlib.sha256(raw_b).hexdigest().lower()
        control_table.append({
            "file": fn,
            "bytes": len(raw_b),
            "sha256": sha
        })
    (target_dir / "corpus_V_control.json").write_text(json.dumps(control_table, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Corpus V successfully materialized in {target_dir} ({len(control_table)} files).")


if __name__ == "__main__":
    generate_corpus_v(Path("fixtures/corpus_V"))
