"""
Shared pytest fixtures and factories for ParallelDoc 3.0 test suite.
Strict Draft 2020-12 compliance and custom RFC 3339 date-time format checking.
"""

from datetime import datetime
import json
from pathlib import Path
from typing import Any, Callable, Dict, Iterable
import pytest

import jsonschema
from jsonschema import Draft202012Validator

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from validator import IntegrityEngine, check_datetime, to_json_pointer


@pytest.fixture(scope="session")
def format_checker() -> jsonschema.FormatChecker:
    """Format checker with registered strict RFC 3339 date-time parser."""
    checker = jsonschema.FormatChecker()

    @checker.checks("date-time")
    def _validate_datetime(val: Any) -> bool:
        return check_datetime(val)

    return checker



@pytest.fixture(scope="session")
def schema_v3_path() -> Path:
    p = Path(__file__).resolve().parent.parent / "schema.v3.json"
    assert p.exists(), f"schema.v3.json not found at {p}"
    return p


@pytest.fixture(scope="session")
def manifest_schema_path() -> Path:
    p = Path(__file__).resolve().parent.parent / "manifest.schema.json"
    assert p.exists(), f"manifest.schema.json not found at {p}"
    return p


@pytest.fixture(scope="session")
def schema_v3_dict(schema_v3_path: Path) -> Dict[str, Any]:
    return json.loads(schema_v3_path.read_text(encoding="utf-8"))


@pytest.fixture(scope="session")
def manifest_schema_dict(manifest_schema_path: Path) -> Dict[str, Any]:
    return json.loads(manifest_schema_path.read_text(encoding="utf-8"))


@pytest.fixture(scope="session")
def v3_validator(schema_v3_dict: Dict[str, Any], format_checker: jsonschema.FormatChecker) -> Draft202012Validator:
    return Draft202012Validator(schema_v3_dict, format_checker=format_checker)


@pytest.fixture(scope="session")
def manifest_validator(manifest_schema_dict: Dict[str, Any], format_checker: jsonschema.FormatChecker) -> Draft202012Validator:
    return Draft202012Validator(manifest_schema_dict, format_checker=format_checker)


@pytest.fixture
def json_pointer():
    """Helper fixture to convert path iterable to RFC 6901 pointer."""
    return to_json_pointer


@pytest.fixture
def engine(schema_v3_path: Path, manifest_schema_path: Path) -> IntegrityEngine:
    return IntegrityEngine(schema_v3_path=schema_v3_path, manifest_schema_path=manifest_schema_path)


@pytest.fixture
def make_minimal_v3_doc() -> Callable[[], Dict[str, Any]]:
    """Factory fixture returning a clean, minimal valid v3.0 document."""
    def _factory() -> Dict[str, Any]:
        return {
            "format": "paralleldoc",
            "version": "3.0",
            "metadata": {
                "document_id": "doc-min-01",
                "revision": "rev-1",
                "title": "Minimal Valid ParallelDoc",
                "author_refs": ["auth-01"],
            },
            "authors": [
                {"id": "auth-01", "kind": "human", "name": "Author 1"}
            ],
            "units": [],
            "groups": [],
            "visuals": [],
            "assets": [],
            "profiles": [],
        }
    return _factory


@pytest.fixture
def make_rich_v3_doc() -> Callable[[], Dict[str, Any]]:
    """Factory fixture returning a fully populated valid v3.0 document."""
    def _factory() -> Dict[str, Any]:
        return {
            "format": "paralleldoc",
            "version": "3.0",
            "metadata": {
                "document_id": "doc-rich-01",
                "revision": "rev-1",
                "title": "Rich Valid ParallelDoc Document",
                "created_at": "2026-09-06T17:00:00Z",
                "language": "ru",
                "author_refs": ["auth-01"],
                "default_profile_id": "prof-01",
            },
            "authors": [
                {"id": "auth-01", "kind": "human", "name": "Author 1", "version": "1.0"}
            ],
            "units": [
                {
                    "id": "u-src",
                    "kind": "source",
                    "title": "Primary Source Clause",
                    "text": "SLA uptime is 99.95% per calendar month excluding maintenance.",
                    "text_format": "plain",
                    "summary": "Source SLA clause",
                    "author_refs": ["auth-01"],
                    "epistemic": "reported",
                    "status": "done",
                    "source_refs": [],
                    "asset_ids": [],
                    "provenance": {
                        "label": "Contract Agreement §4.1",
                        "source_sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
                    }
                },
                {
                    "id": "u-mod",
                    "kind": "model",
                    "title": "SLA Evaluation Model",
                    "text": "Formal graph model evaluating SLA compliance and risk bounds.",
                    "text_format": "markdown-safe",
                    "author_refs": ["auth-01"],
                    "epistemic": "hypothesis",
                    "status": "reviewed",
                    "source_refs": [],
                    "asset_ids": []
                },
                {
                    "id": "u-ana",
                    "kind": "analysis",
                    "title": "Downtime Calculation Analysis",
                    "text": "Calculated maximum allowable unplanned downtime is 21.6 minutes per month.",
                    "text_format": "plain",
                    "author_refs": ["auth-01"],
                    "epistemic": "supported",
                    "status": "reviewed",
                    "source_refs": ["u-src"],
                    "asset_ids": []
                },
                {
                    "id": "u-act",
                    "kind": "action",
                    "title": "Monitoring Alert Thresholds",
                    "text": "Deploy monitoring alert at 15 minutes cumulative monthly downtime.",
                    "text_format": "plain",
                    "author_refs": ["auth-01"],
                    "epistemic": "not-applicable",
                    "status": "draft",
                    "source_refs": [],
                    "asset_ids": ["ast-01"]
                }
            ],
            "groups": [
                {
                    "id": "g-01",
                    "title": "Primary SLA Review Group",
                    "unit_refs": ["u-src", "u-mod", "u-ana", "u-act"]
                }
            ],
            "visuals": [
                {
                    "id": "v-01",
                    "type": "relationship-graph",
                    "title": "SLA Logic Flow",
                    "question": "Is 99.95% availability guaranteed without maintenance exclusion?",
                    "fallback": "Graph representation of SLA clause dependencies.",
                    "owner_unit_id": "u-mod",
                    "author_refs": ["auth-01"],
                    "nodes": [
                        {"id": "n-01", "label": "Source Agreement", "unit_refs": ["u-src"]},
                        {"id": "n-02", "label": "Calculated Downtime", "unit_refs": ["u-ana"]}
                    ],
                    "edges": [
                        {
                            "id": "e-01",
                            "from": "n-01",
                            "to": "n-02",
                            "relation": "supports",
                            "label": "Grounds for calculation",
                            "unit_refs": ["u-src", "u-ana"]
                        }
                    ]
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
                    "alt": "1x1 transparent PNG icon",
                    "caption": "Minimal benchmark asset",
                    "author_refs": ["auth-01"],
                    "provenance": {"label": "Generated in-memory"},
                    "locator": {
                        "mode": "embedded",
                        "data_uri": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
                    }
                }
            ],
            "profiles": [
                {
                    "id": "prof-01",
                    "title": "4-Panel Review",
                    "density": "reading",
                    "panels": [
                        {"id": "p-src", "title": "Source", "kinds": ["source"], "weight": 28},
                        {"id": "p-mod", "title": "Model", "kinds": ["model"], "weight": 30},
                        {"id": "p-ana", "title": "Analysis", "kinds": ["analysis"], "weight": 26},
                        {"id": "p-act", "title": "Actions", "kinds": ["action"], "weight": 16}
                    ]
                }
            ],
            "extensions": {
                "astrai.org/verification": {
                    "audit_status": "passed",
                    "evaluator": "M1"
                }
            }
        }
    return _factory
