"""
fixtures/generate_corpus_r.py — Deterministic Generator for Corpus R (Stress Load & Graph Scale).
Materializes:
- stress_1000_units.json / corpus_R_stress_1000.json (1,000 units across 250 groups, >=1.0 MiB text,
  100 nodes / 150 edges graph, 3 embedded raster assets with 12 MiB decoded bytes).
- graph_limit_200n_400e.json / corpus_R_large_graph_200n_400e.json (200 nodes / 400 edges).
- graph_breach_201n_401e.json / corpus_R_overflow_graph_201n_401e.json (201 nodes / 401 edges).
Complies strictly with Spec r2 §5, §6, §10, §11 (AC-43, AC-44).
"""

import base64
import hashlib
import json
from pathlib import Path
import struct
import zlib


def make_png_bytes(width: int, height: int, rgba: tuple = (41, 128, 185, 255)) -> bytes:
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


def generate_stress_1000_doc():
    units = []
    groups = []
    kinds = ["source", "model", "analysis", "action"]

    for g_idx in range(1, 251):
        g_id = f"g-{g_idx:03d}"
        group_unit_refs = []
        source_id = f"u-{(g_idx - 1) * 4 + 1:04d}"

        for k_idx, kind in enumerate(kinds):
            u_id = f"u-{(g_idx - 1) * 4 + k_idx + 1:04d}"
            group_unit_refs.append(u_id)

            payload_text = (
                f"Раздел {g_idx}.{k_idx + 1}: Эксплуатационная спецификация отказоустойчивости кластера {u_id}. "
                f"В рамках соглашения об уровне обслуживания гарантируется непрерывный мониторинг и автоматический failover в Multi-AZ. "
                f"Статистическая вероятность сохранения доступности на уровне не ниже 99.95% подтверждается телеметрией. "
            ) * 10

            unit_obj = {
                "id": u_id,
                "kind": kind,
                "title": f"Спецификация {g_idx}.{k_idx + 1}: Компонент оценки SLA ({u_id})",
                "text": payload_text,
                "text_format": "plain",
                "author_refs": ["auth-bench-01"],
                "epistemic": "supported" if kind == "analysis" else ("hypothesis" if kind == "model" else ("not-applicable" if kind == "action" else "reported")),
                "status": "reviewed",
                "source_refs": [source_id] if kind == "analysis" else [],
                "asset_ids": []
            }
            if kind == "source":
                unit_obj["provenance"] = {"label": f"Specification Document Section {g_idx}"}
            units.append(unit_obj)

        groups.append({
            "id": g_id,
            "title": f"Группа {g_idx}: Домен оценки SLA и инфраструктуры",
            "unit_refs": group_unit_refs
        })

    # 2. Synthesize Graph (100 nodes, 150 edges)
    nodes = []
    for i in range(100):
        nodes.append({
            "id": f"node-{i:03d}",
            "label": f"Узел {i:03d} (Кластер)",
            "unit_refs": [units[i]["id"]]
        })

    edges = []
    relation_types = ["supports", "qualifies", "contradicts", "depends_on", "precedes", "compares"]
    for i in range(150):
        src = f"node-{i % 100:03d}"
        dst = f"node-{(i + 1) % 100:03d}"
        rel = relation_types[i % len(relation_types)]
        edges.append({
            "id": f"edge-{i:03d}",
            "from": src,
            "to": dst,
            "relation": rel,
            "label": f"Связь {i:03d} ({rel})",
            "unit_refs": [units[i % 1000]["id"]]
        })

    # 3. Embed 3 raster assets (1024x1024 PNGs = 4.19 MiB decoded bytes each, total 12.58 MiB decoded)
    assets = []
    for a_idx in range(1, 4):
        png_b = make_png_bytes(1024, 1024, (20 * a_idx, 80 + 20 * a_idx, 160, 255))
        b64 = base64.b64encode(png_b).decode("ascii")
        ast_id = f"ast-bench-{a_idx:02d}"
        assets.append({
            "id": ast_id,
            "mime": "image/png",
            "sha256": hashlib.sha256(png_b).hexdigest().lower(),
            "byte_length": len(png_b),
            "width": 1024,
            "height": 1024,
            "alt": f"Стресс-диаграмма {a_idx} (1024x1024, 4.19 MiB decoded)",
            "caption": f"Диаграмма {a_idx}: Нагрузочный бенчмарк архитектуры",
            "author_refs": ["auth-bench-01"],
            "provenance": {"label": f"Синтезатор Corpus R, поток {a_idx}"},
            "locator": {"mode": "embedded", "data_uri": f"data:image/png;base64,{b64}"}
        })
        units[a_idx * 10]["asset_ids"].append(ast_id)

    doc = {
        "format": "paralleldoc",
        "version": "3.0",
        "metadata": {
            "document_id": "doc-stress-corpus-r-1000",
            "revision": "rev-1.0",
            "title": "ParallelDoc 3.0 Corpus R: Нагрузочный документ (1,000 юнитов, 250 групп, 12 МБ медиа)",
            "created_at": "2026-09-06T20:00:00Z",
            "language": "ru",
            "author_refs": ["auth-bench-01"],
            "default_profile_id": "builtin:3"
        },
        "authors": [
            {"id": "auth-bench-01", "kind": "tool", "name": "Corpus R Benchmark Synthesizer"}
        ],
        "units": units,
        "groups": groups,
        "visuals": [
            {
                "id": "vis-stress-100n-150e",
                "type": "relationship-graph",
                "title": "Нагрузочный семантический граф (100 узлов / 150 рёбер)",
                "question": "Сохраняет ли система отзывчивость и частоту кадров при 100 узлах и 150 ребрах?",
                "fallback": "Текстовая таблица взаимосвязей для 150 нагрузочных ребер.",
                "owner_unit_id": units[1]["id"],  # kind=model, required!
                "author_refs": ["auth-bench-01"],
                "nodes": nodes,
                "edges": edges
            }
        ],
        "assets": assets,
        "profiles": []
    }
    return doc


def generate_graph_scale_doc(n_count: int, e_count: int, doc_id: str, title: str):
    units = []
    groups = []

    # 1 source, 1 model
    units.append({
        "id": "u-scale-src",
        "kind": "source",
        "title": "Исходные требования к масштабируемости графа",
        "text": f"Тестирование масштабируемости графа связей на границе {n_count} узлов и {e_count} рёбер.",
        "text_format": "plain",
        "author_refs": ["auth-scale-01"],
        "epistemic": "reported",
        "status": "reviewed",
        "source_refs": [],
        "asset_ids": [],
        "provenance": {"label": "Spec §6, §11"}
    })
    units.append({
        "id": "u-scale-mod",
        "kind": "model",
        "title": "Модель масштабирования графа",
        "text": f"Модель содержит граф размером {n_count} узлов и {e_count} рёбер.",
        "text_format": "markdown-safe",
        "author_refs": ["auth-scale-01"],
        "epistemic": "hypothesis",
        "status": "reviewed",
        "source_refs": [],
        "asset_ids": []
    })
    groups.append({
        "id": "g-scale-01",
        "title": f"Группа масштабируемости ({n_count}n / {e_count}e)",
        "unit_refs": ["u-scale-src", "u-scale-mod"]
    })

    nodes = []
    for i in range(n_count):
        nodes.append({
            "id": f"n-{i:03d}",
            "label": f"Node {i:03d}",
            "unit_refs": ["u-scale-src" if i % 2 == 0 else "u-scale-mod"]
        })

    edges = []
    relation_types = ["supports", "qualifies", "contradicts", "depends_on", "precedes", "compares"]
    for i in range(e_count):
        src = f"n-{i % n_count:03d}"
        dst = f"n-{(i + 1) % n_count:03d}"
        rel = relation_types[i % len(relation_types)]
        edges.append({
            "id": f"e-{i:03d}",
            "from": src,
            "to": dst,
            "relation": rel,
            "label": f"Rel {i:03d}",
            "unit_refs": ["u-scale-src"]
        })

    doc = {
        "format": "paralleldoc",
        "version": "3.0",
        "metadata": {
            "document_id": doc_id,
            "revision": "rev-1.0",
            "title": title,
            "author_refs": ["auth-scale-01"]
        },
        "authors": [{"id": "auth-scale-01", "kind": "tool", "name": "Scale Limit Tester"}],
        "units": units,
        "groups": groups,
        "visuals": [
            {
                "id": "vis-scale-test",
                "type": "relationship-graph",
                "title": f"Граф масштабирования ({n_count} узлов / {e_count} рёбер)",
                "question": "Превышен ли лимит масштабирования графа?",
                "fallback": f"Таблица всех {e_count} связей между {n_count} узлами.",
                "owner_unit_id": "u-scale-mod",
                "author_refs": ["auth-scale-01"],
                "nodes": nodes,
                "edges": edges
            }
        ],
        "assets": [],
        "profiles": []
    }
    return doc


def generate_corpus_r(target_dir: Path):
    target_dir.mkdir(parents=True, exist_ok=True)
    results = []

    def write_pair(name1: str, name2: str, doc: dict, desc: str):
        raw_b = json.dumps(doc, indent=2, ensure_ascii=False).encode("utf-8")
        p1 = target_dir / name1
        p2 = target_dir / name2
        p1.write_bytes(raw_b)
        p2.write_bytes(raw_b)
        sha = hashlib.sha256(raw_b).hexdigest().lower()
        results.append({
            "primary_file": name1,
            "alias_file": name2,
            "bytes": len(raw_b),
            "sha256": sha,
            "description": desc
        })

    # 1. Stress 1,000 units
    doc_stress = generate_stress_1000_doc()
    write_pair(
        "stress_1000_units.json",
        "corpus_R_stress_1000.json",
        doc_stress,
        "1,000 units, 250 groups, 100n/150e graph, 12 MiB decoded assets"
    )

    # 2. Large graph limit (200 nodes / 400 edges)
    doc_200 = generate_graph_scale_doc(200, 400, "doc-graph-200n-400e", "Граф на границе лимита (200n / 400e)")
    write_pair(
        "graph_limit_200n_400e.json",
        "corpus_R_large_graph_200n_400e.json",
        doc_200,
        "200 nodes / 400 edges within visual rendering limit"
    )

    # 3. Large graph breach (201 nodes / 401 edges)
    doc_201 = generate_graph_scale_doc(201, 401, "doc-graph-201n-401e", "Граф с превышением лимита (201n / 401e)")
    write_pair(
        "graph_breach_201n_401e.json",
        "corpus_R_overflow_graph_201n_401e.json",
        doc_201,
        "201 nodes / 401 edges triggering scale limit guard banner and fallback table"
    )

    # Control table
    (target_dir / "corpus_R_control.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(f"Corpus R successfully materialized in {target_dir} ({len(results)} pairs).")


if __name__ == "__main__":
    generate_corpus_r(Path("fixtures/corpus_R"))
