"""
Empirical Pointer Torture: Systematic Null and Malformed Pointer Injection.
Author: Challenger M1-2
Injects None/malformed fields into all referential positions and checks whether
validator returns a graceful report or crashes with unhandled exceptions.
"""

import copy
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from validator import IntegrityEngine


def get_base_doc() -> Dict[str, Any]:
    return {
        "format": "paralleldoc",
        "version": "3.0",
        "metadata": {
            "document_id": "doc-01",
            "revision": "1.0",
            "title": "Valid Doc",
            "author_refs": ["auth-01"],
            "default_profile_id": "builtin:4",
        },
        "authors": [{"id": "auth-01", "kind": "human", "name": "Author"}],
        "units": [
            {
                "id": "u-src",
                "kind": "source",
                "title": "Source",
                "text": "Text",
                "text_format": "plain",
                "author_refs": ["auth-01"],
                "epistemic": "reported",
                "status": "done",
                "source_refs": [],
                "asset_ids": [],
                "provenance": {"label": "L", "source_sha256": "0" * 64},
            },
            {
                "id": "u-mod",
                "kind": "model",
                "title": "Model",
                "text": "Text",
                "text_format": "plain",
                "author_refs": ["auth-01"],
                "epistemic": "hypothesis",
                "status": "draft",
                "source_refs": [],
                "asset_ids": [],
            },
        ],
        "groups": [{"id": "g-01", "title": "Group 1", "unit_refs": ["u-src", "u-mod"]}],
        "visuals": [
            {
                "id": "v-01",
                "type": "relationship-graph",
                "title": "Graph",
                "question": "Q",
                "fallback": "F",
                "owner_unit_id": "u-mod",
                "author_refs": ["auth-01"],
                "nodes": [
                    {"id": "n-01", "label": "Node 1", "unit_refs": ["u-src"]},
                    {"id": "n-02", "label": "Node 2", "unit_refs": ["u-mod"]},
                ],
                "edges": [
                    {
                        "id": "e-01",
                        "from": "n-01",
                        "to": "n-02",
                        "relation": "supports",
                        "label": "Supp",
                        "unit_refs": ["u-src"],
                    }
                ],
            }
        ],
        "assets": [
            {
                "id": "ast-01",
                "mime": "image/png",
                "sha256": "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad",
                "byte_length": 68,
                "width": 1,
                "height": 1,
                "alt": "Alt",
                "caption": "Cap",
                "author_refs": ["auth-01"],
                "provenance": {"label": "P"},
                "locator": {
                    "mode": "embedded",
                    "data_uri": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==",
                },
            }
        ],
        "profiles": [
            {
                "id": "prof-01",
                "title": "P",
                "density": "reading",
                "panels": [
                    {"id": "p1", "title": "T", "kinds": ["source", "model"], "weight": 50},
                    {"id": "p2", "title": "T", "kinds": ["analysis", "action"], "weight": 50},
                ],
            }
        ],
    }


def run_torture():
    engine = IntegrityEngine()
    test_mutations: List[Tuple[str, Callable[[Dict[str, Any]], None]]] = [
        ("metadata.author_refs = None", lambda d: d["metadata"].__setitem__("author_refs", None)),
        ("unit.author_refs = None", lambda d: d["units"][0].__setitem__("author_refs", None)),
        ("unit.asset_ids = None", lambda d: d["units"][0].__setitem__("asset_ids", None)),
        ("unit.source_refs = None", lambda d: d["units"][0].__setitem__("source_refs", None)),
        ("visual.author_refs = None", lambda d: d["visuals"][0].__setitem__("author_refs", None)),
        ("visual.nodes = None", lambda d: d["visuals"][0].__setitem__("nodes", None)),
        ("visual.edges = None", lambda d: d["visuals"][0].__setitem__("edges", None)),
        ("node.unit_refs = None", lambda d: d["visuals"][0]["nodes"][0].__setitem__("unit_refs", None)),
        ("edge.unit_refs = None", lambda d: d["visuals"][0]["edges"][0].__setitem__("unit_refs", None)),
        ("asset.author_refs = None", lambda d: d["assets"][0].__setitem__("author_refs", None)),
        ("group.unit_refs = None", lambda d: d["groups"][0].__setitem__("unit_refs", None)),
        ("profile.panels = None", lambda d: d["profiles"][0].__setitem__("panels", None)),
        ("panel.kinds = None", lambda d: d["profiles"][0]["panels"][0].__setitem__("kinds", None)),
        ("root.units = None", lambda d: d.__setitem__("units", None)),
        ("root.groups = None", lambda d: d.__setitem__("groups", None)),
        ("root.visuals = None", lambda d: d.__setitem__("visuals", None)),
        ("root.assets = None", lambda d: d.__setitem__("assets", None)),
        ("root.profiles = None", lambda d: d.__setitem__("profiles", None)),
        ("root.authors = None", lambda d: d.__setitem__("authors", None)),
    ]

    print(f"Running {len(test_mutations)} torture injection tests...\n")
    results = []
    for desc, mutate_fn in test_mutations:
        doc = copy.deepcopy(get_base_doc())
        mutate_fn(doc)
        try:
            report = engine.validate_document(doc)
            results.append((desc, "GRACEFUL", f"is_valid={report.is_valid}, issues={len(report.issues)}"))
        except Exception as e:
            results.append((desc, "CRASHED", f"{type(e).__name__}: {e}"))

    for desc, status, detail in results:
        indicator = "FAIL (CRASH)" if status == "CRASHED" else "PASS (GRACEFUL)"
        print(f"[{indicator:13s}] {desc:32s} -> {detail}")

    crashes = [r for r in results if r[1] == "CRASHED"]
    print(f"\nSummary: {len(crashes)} / {len(test_mutations)} mutations caused unhandled crashes.")


if __name__ == "__main__":
    run_torture()
