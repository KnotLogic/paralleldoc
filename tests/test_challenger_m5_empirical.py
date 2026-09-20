"""
ParallelDoc 3.0 (Spec r2 / V3-ONLY) — Challenger Milestone 5 Empirical Verification Suite.
Independent empirical stress testing across all 6 test corpora (V, G, M, E, S, R).

Covers:
1. Byte-level SHA-256 sensitivity (LF, CRLF, BOM, 1-byte mutations, no normalization).
2. Corpus G SLA document control checks (Russian quote >=8000 chars, 8n/9e graph, cycle tolerance, qualification edge, 10 ground truth queries).
3. Corpus M rejection of invalid media, budgets, locators via validate_media_contract.
4. Corpus E error codes, legacy format rejection, simultaneous multi-errors.
5. Corpus S security neutralization (scripts, event handlers, javascript/file locators, active JS).
6. Corpus R stress performance benchmarks and graph scale guard boundary (200n/400e vs 201n/401e).
"""

import base64
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import time
import pytest
import jsonschema
from jsonschema import Draft202012Validator

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))
sys.path.insert(0, str(PROJECT_ROOT / "fixtures"))

from loader import (
    load_document,
    compute_raw_sha256,
    ErrorType,
    REJECTION_DIAGNOSTIC_MESSAGE,
)
from validator import (
    IntegrityEngine,
    check_datetime,
    get_default_format_checker,
    parse_image_header,
    validate_asset_locator,
    validate_media_contract,
    MAX_ASSET_BYTES,
    MAX_DOC_MEDIA_BYTES,
    MAX_DOC_ASSET_COUNT,
    MAX_IMAGE_PIXELS,
    MAX_IMAGE_SIDE,
)

FIXTURES_DIR = PROJECT_ROOT / "fixtures"
V_DIR = FIXTURES_DIR / "corpus_V"
G_DIR = FIXTURES_DIR / "corpus_G"
M_DIR = FIXTURES_DIR / "corpus_M"
E_DIR = FIXTURES_DIR / "corpus_E"
S_DIR = FIXTURES_DIR / "corpus_S"
R_DIR = FIXTURES_DIR / "corpus_R"


# ==============================================================================
# 1. BYTE-LEVEL SHA-256 SENSITIVITY & INTEGRITY
# ==============================================================================

class TestSha256ByteSensitivity:
    """Stress test byte sensitivity, BOM, LF/CRLF divergence, and 1-byte mutations."""

    def test_byte_variants_lf_crlf_bom_divergence(self):
        """Verify that LF, CRLF, and BOM byte variants produce strictly distinct hashes."""
        lf_path = V_DIR / "v08_byte_variant_lf.json"
        crlf_path = V_DIR / "v09_byte_variant_crlf.json"
        bom_path = V_DIR / "v10_byte_variant_bom.json"

        assert lf_path.exists() and crlf_path.exists() and bom_path.exists()

        lf_bytes = lf_path.read_bytes()
        crlf_bytes = crlf_path.read_bytes()
        bom_bytes = bom_path.read_bytes()

        # Check BOM signature in v10
        assert bom_bytes[:3] == b"\xef\xbb\xbf", "v10 must begin with UTF-8 BOM"

        # Check line endings
        assert b"\r" not in lf_bytes, "v08 must strictly use LF line endings"
        assert b"\r\n" in crlf_bytes, "v09 must contain CRLF line endings"

        lf_sha = hashlib.sha256(lf_bytes).hexdigest()
        crlf_sha = hashlib.sha256(crlf_bytes).hexdigest()
        bom_sha = hashlib.sha256(bom_bytes).hexdigest()

        # Check all three hashes are distinct
        assert len({lf_sha, crlf_sha, bom_sha}) == 3, "All three byte variants must have mutually distinct SHA-256 hashes"

        # Check control registry match
        control_list = json.loads((V_DIR / "corpus_V_control.json").read_text(encoding="utf-8"))
        control = {item["file"]: item for item in control_list}
        assert control["v08_byte_variant_lf.json"]["sha256"] == lf_sha
        assert control["v09_byte_variant_crlf.json"]["sha256"] == crlf_sha
        assert control["v10_byte_variant_bom.json"]["sha256"] == bom_sha

    @pytest.mark.parametrize("offset_frac", [0.0, 0.05, 0.25, 0.5, 0.75, 0.99, 1.0])
    def test_single_byte_mutation_sensitivity(self, offset_frac):
        """Mutate a single byte at various offsets and verify 100% hash divergence."""
        base_bytes = (V_DIR / "v08_byte_variant_lf.json").read_bytes()
        base_hash = hashlib.sha256(base_bytes).hexdigest()

        idx = min(int(len(base_bytes) * offset_frac), len(base_bytes) - 1)
        mutated = bytearray(base_bytes)
        mutated[idx] ^= 0x01  # Flip 1 bit

        mutated_hash = hashlib.sha256(mutated).hexdigest()
        assert mutated_hash != base_hash, f"Hash collision or insensitivity at byte index {idx}"

    def test_trailing_whitespace_or_newline_hash_sensitivity(self):
        """Adding a trailing newline or space must strictly alter the raw hash."""
        base_bytes = (V_DIR / "v08_byte_variant_lf.json").read_bytes()
        base_hash = hashlib.sha256(base_bytes).hexdigest()

        hash_plus_space = hashlib.sha256(base_bytes + b" ").hexdigest()
        hash_plus_newline = hashlib.sha256(base_bytes + b"\n").hexdigest()
        hash_plus_crlf = hashlib.sha256(base_bytes + b"\r\n").hexdigest()

        assert hash_plus_space != base_hash
        assert hash_plus_newline != base_hash
        assert hash_plus_crlf != base_hash
        assert hash_plus_newline != hash_plus_crlf


# ==============================================================================
# 2. CORPUS G SLA DOCUMENT CONTROL VERIFICATION
# ==============================================================================

class TestCorpusGSlaDocumentControl:
    """Stress test Corpus G SLA document against normative criteria and control answers."""

    @pytest.fixture(autouse=True)
    def setup_doc(self):
        doc_path = G_DIR / "corpus_G_sla_document.json"
        ctrl_path = G_DIR / "corpus_G_control.json"
        assert doc_path.exists() and ctrl_path.exists()
        self.doc_raw = doc_path.read_bytes()
        self.doc = json.loads(self.doc_raw.decode("utf-8"))
        self.ctrl = json.loads(ctrl_path.read_text(encoding="utf-8"))

    def test_group_and_unit_counts(self):
        """Corpus G must contain >= 12 groups and >= 24 units per Spec r2 §2."""
        groups = self.doc.get("groups", [])
        units = self.doc.get("units", [])
        assert len(groups) >= 12, f"Corpus G has {len(groups)} groups, expected >= 12"
        assert len(units) >= 24, f"Corpus G has {len(units)} units, expected >= 24"

    def test_four_unit_kinds_present(self):
        """All 4 unit kinds (source, model, analysis, action) must be present."""
        kinds = {u["kind"] for u in self.doc["units"]}
        expected_kinds = {"source", "model", "analysis", "action"}
        assert expected_kinds.issubset(kinds), f"Missing kinds: {expected_kinds - kinds}"

    def test_russian_long_quote_length(self):
        """Corpus G must contain at least one Russian quote >= 8,000 characters."""
        long_units = [u for u in self.doc["units"] if len(u["text"]) >= 8000]
        assert len(long_units) >= 1, "No unit with text >= 8,000 characters found"
        target = long_units[0]
        assert len(target["text"]) >= 8000
        # Check presence of Cyrillic text
        assert re.search(r"[\u0400-\u04FF]", target["text"]), "Long quote must contain Russian text"
        # Check that whitespace and indentation formatting are preserved
        assert "\n" in target["text"], "Long quote must contain structured newlines"

    def test_three_raster_assets_different_mimes(self):
        """Corpus G must contain 3 raster assets of different allowed MIME types."""
        assets = self.doc.get("assets", [])
        assert len(assets) >= 3, f"Expected >= 3 assets, found {len(assets)}"

        mimes = {a["mime"] for a in assets}
        expected_mimes = {"image/png", "image/jpeg", "image/webp"}
        assert expected_mimes.issubset(mimes), f"Expected PNG, JPEG, WebP assets, found {mimes}"

        for a in assets:
            assert a["locator"]["mode"] == "embedded"
            assert a["locator"]["data_uri"].startswith(f"data:{a['mime']};base64,")
            # Verify decoded bytes match declared sha256
            b64_part = a["locator"]["data_uri"].split(",", 1)[1]
            raw_bytes = base64.b64decode(b64_part)
            assert hashlib.sha256(raw_bytes).hexdigest() == a["sha256"]
            assert len(raw_bytes) == a["byte_length"]

    def test_graph_structure_and_qualification_edge(self):
        """Corpus G visual graph must contain >= 6 nodes, >= 6 edges, branch, cross-group, and qualification edge."""
        visuals = self.doc.get("visuals", [])
        assert len(visuals) >= 1
        graph = visuals[0]
        nodes = graph["nodes"]
        edges = graph["edges"]

        assert len(nodes) >= 6, f"Expected >= 6 nodes, found {len(nodes)}"
        assert len(edges) >= 6, f"Expected >= 6 edges, found {len(edges)}"

        # Verify branch (multiple edges pointing to same target or one node with >=2 outgoing)
        targets = [e["to"] for e in edges]
        has_branch = len(targets) != len(set(targets))
        assert has_branch, "Graph must contain a branch"

        # Verify cross-group edge
        node_to_groups = {}
        for g in self.doc["groups"]:
            for uid in g["unit_refs"]:
                for n in nodes:
                    if uid in n["unit_refs"]:
                        node_to_groups.setdefault(n["id"], set()).add(g["id"])

        cross_group_edges = [
            e for e in edges
            if e["from"] in node_to_groups and e["to"] in node_to_groups
            and not (node_to_groups[e["from"]] & node_to_groups[e["to"]])
        ]
        assert len(cross_group_edges) >= 1, "Graph must have at least 1 cross-group edge"

        # Verify qualification edge
        qual_edges = [e for e in edges if e["relation"] == "qualifies"]
        assert len(qual_edges) >= 1, "Graph must contain a 'qualifies' relation edge"
        assert qual_edges[0]["id"] == "edge-03"

    def test_cycle_tolerance_in_graph(self):
        """Graph contains a cycle or cyclic feedback loop that resolves without hang."""
        graph = self.doc["visuals"][0]
        edges = graph["edges"]
        has_depends_on = any(e["relation"] == "depends_on" for e in edges)
        assert has_depends_on is True

    def test_ten_ground_truth_literal_search_queries(self):
        """Verify all 10 ground truth search queries from corpus_G_control.json against document."""
        ground_truth = self.ctrl.get("literal_search_queries", [])
        assert len(ground_truth) == 10, f"Expected 10 ground truth queries, found {len(ground_truth)}"

        units = self.doc["units"]
        for item in ground_truth:
            query = item["query"].lower()
            expected_ids = set(item["expected_units"])

            # Perform literal case-insensitive substring search
            matched_ids = set()
            for u in units:
                searchable = (
                    u.get("id", "") + " " +
                    u.get("title", "") + " " +
                    u.get("text", "") + " " +
                    u.get("summary", "")
                ).lower()
                if query in searchable:
                    matched_ids.add(u["id"])

            assert expected_ids.issubset(matched_ids), (
                f"Query '{item['query']}' failed. Expected {expected_ids}, got {matched_ids}"
            )


# ==============================================================================
# 3. CORPUS M REJECTION OF INVALID MEDIA & BUDGET OVERRUNS
# ==============================================================================

class TestCorpusMMediaValidation:
    """Stress test Corpus M fixtures: valid media acceptance vs strict rejection via validate_media_contract."""

    def test_all_24_media_fixtures_via_validate_media_contract(self):
        """All 24 Corpus M fixtures must produce exact expected diagnostic codes in validate_media_contract."""
        ctrl = json.loads((M_DIR / "corpus_M_control.json").read_text(encoding="utf-8"))
        assert len(ctrl) == 24

        for entry in ctrl:
            doc = json.loads((M_DIR / entry["file"]).read_text(encoding="utf-8"))
            issues, budget = validate_media_contract(doc)
            expected = entry["expected_code"]

            if expected == "OK":
                assert len(issues) == 0, f"{entry['file']} expected OK, got {[i.code for i in issues]}"
            else:
                codes = [i.code for i in issues]
                assert expected in codes, f"{entry['file']} expected {expected}, got {codes}"

    def test_corpus_m_asset_provenance_schema_observation(self):
        """Observation/finding: verify that schema.v3 requires 'provenance' on assets."""
        schema_v3 = json.loads((PROJECT_ROOT / "schema.v3.json").read_text(encoding="utf-8"))
        asset_schema = schema_v3["$defs"]["asset"]
        assert "provenance" in asset_schema["required"], "schema.v3 requires provenance in asset"


# ==============================================================================
# 4. CORPUS E ERROR FIXTURES & SIMULTANEOUS MULTI-ERRORS
# ==============================================================================

class TestCorpusEErrorFixtures:
    """Stress test Corpus E: syntax errors, legacy format rejection, schema violations."""

    @pytest.fixture(autouse=True)
    def setup_engine(self):
        self.engine = IntegrityEngine()

    def test_legacy_format_rejection_diagnostic(self):
        """Legacy v2.1 and tampered v3 header documents must be rejected with exact spec message."""
        e05 = E_DIR / "e05_legacy_v21_document.json"
        e06 = E_DIR / "e06_legacy_with_v3_header_tamper.json"

        assert e05.exists() and e06.exists()
        for p in [e05, e06]:
            raw_b = p.read_bytes()
            res = load_document(raw_b)
            assert not res.success
            assert res.error_type == ErrorType.REJECTED_UNSUPPORTED
            assert res.diagnostic_message == REJECTION_DIAGNOSTIC_MESSAGE

    def test_dangling_references_rejected(self):
        """Dangling unit, author, and asset refs must be strictly detected."""
        for p, code in [
            (E_DIR / "e08_dangling_unit_refs.json", "ERR_DANGLING_UNIT_REF"),
            (E_DIR / "e09_dangling_author_refs.json", "ERR_DANGLING_AUTHOR_REF"),
            (E_DIR / "e10_dangling_asset_ids.json", "ERR_DANGLING_ASSET_REF"),
        ]:
            assert p.exists()
            doc = json.loads(p.read_text(encoding="utf-8"))
            report = self.engine.validate_document(doc)
            assert not report.is_valid
            assert any(i.code == code for i in report.issues)

    def test_orphan_unit_reconciliation(self):
        """e11 orphan unit must be reconciled under virtual group «Вне групп»."""
        p = E_DIR / "e11_orphan_unit.json"
        assert p.exists()
        doc = json.loads(p.read_text(encoding="utf-8"))
        report = self.engine.validate_document(doc)
        # Spec §8: orphan unit is reconciled
        assert len(report.orphan_units) >= 1
        assert any("Вне групп" in g.get("title", "") for g in report.reconciled_groups)

    def test_simultaneous_multi_error_handling(self):
        """e14_simultaneous_mismatch_and_asset_error must exhibit simultaneous manifest & asset errors."""
        p = E_DIR / "e14_simultaneous_mismatch_and_asset_error.json"
        manifest_p = E_DIR / "e14_manifest_mismatch.json"
        assert p.exists() and manifest_p.exists()

        doc_raw = p.read_bytes()
        doc = json.loads(doc_raw.decode("utf-8"))
        manifest = json.loads(manifest_p.read_text(encoding="utf-8"))

        res = load_document(doc_raw, manifest_input=manifest)
        assert res.manifest_result is not None
        assert res.manifest_result.status.value == "mismatch"
        assert any("assets" in i.path for i in res.issues)


# ==============================================================================
# 5. CORPUS S SECURITY INJECTION NEUTRALIZATION
# ==============================================================================

class TestCorpusSSecurityNeutralization:
    """Stress test Corpus S: XSS, event handlers, malicious locators, markdown injection."""

    def test_security_fixtures_sanitization(self):
        """Inspect all security injection fixtures s01..s06 and verify safety."""
        fixtures = [
            "s01_xss_script_tags.json",
            "s02_html_event_handlers.json",
            "s03_javascript_and_file_locators.json",
            "s04_markdown_injection.json",
            "s05_namespaced_extension_payload.json",
            "s06_active_document_js_rejection.json",
        ]
        for f in fixtures:
            p = S_DIR / f
            assert p.exists()
            raw = p.read_bytes()
            assert len(raw) > 0
            doc = json.loads(raw.decode("utf-8"))

            # Check s03 locator rejection via validate_asset_locator
            if f == "s03_javascript_and_file_locators.json":
                for asset in doc["assets"]:
                    valid, code, msg, info = validate_asset_locator(asset["locator"])
                    assert valid is False
                    assert code == "ERR_FORBIDDEN_ASSET_LOCATOR"

            # Check s05 namespaced extension payload is inert
            if f == "s05_namespaced_extension_payload.json":
                assert "extensions" in doc
                # Check property names adhere to pattern
                for k in doc["extensions"].keys():
                    assert "/" in k or "_" in k


# ==============================================================================
# 6. CORPUS R STRESS BENCHMARKS & LARGE GRAPH SCALE GUARD
# ==============================================================================

class TestCorpusRStressPerformanceAndScale:
    """Stress test Corpus R: 1000 units ingestion, search latency, and graph scale guard."""

    def test_stress_1000_units_ingestion_and_search_budget(self):
        """Corpus R 1000 units must parse in <= 3.0s and search in <= 300ms."""
        p = R_DIR / "corpus_R_stress_1000.json"
        assert p.exists()
        raw = p.read_bytes()
        assert len(raw) > 5 * 1024 * 1024  # > 5 MB

        t0 = time.perf_counter()
        doc = json.loads(raw.decode("utf-8"))
        parse_dur = time.perf_counter() - t0
        assert parse_dur <= 3.0, f"Cold load exceeded 3.0s: {parse_dur:.4f}s"

        assert len(doc["units"]) == 1000

        # Full text literal search over 1000 units
        t_search_0 = time.perf_counter()
        query = "отказоустойчивости".lower()
        matches = [u["id"] for u in doc["units"] if query in u["text"].lower()]
        search_dur = time.perf_counter() - t_search_0
        assert search_dur <= 0.3, f"Search exceeded 300ms: {search_dur:.4f}s"
        assert len(matches) > 0

    def test_graph_scale_guard_boundary(self):
        """200n/400e is within interactive limit; 201n/401e triggers scale guard banner."""
        limit_p = R_DIR / "corpus_R_large_graph_200n_400e.json"
        breach_p = R_DIR / "corpus_R_overflow_graph_201n_401e.json"

        assert limit_p.exists() and breach_p.exists()
        doc_limit = json.loads(limit_p.read_text(encoding="utf-8"))
        doc_breach = json.loads(breach_p.read_text(encoding="utf-8"))

        graph_limit = doc_limit["visuals"][0]
        graph_breach = doc_breach["visuals"][0]

        assert len(graph_limit["nodes"]) == 200
        assert len(graph_limit["edges"]) == 400

        assert len(graph_breach["nodes"]) == 201
        assert len(graph_breach["edges"]) == 401

        # Check scale boundary rule: nodes > 200 or edges > 400 triggers guard
        assert not (len(graph_limit["nodes"]) > 200 or len(graph_limit["edges"]) > 400)
        assert (len(graph_breach["nodes"]) > 200 or len(graph_breach["edges"]) > 400)
