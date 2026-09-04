#!/usr/bin/env python3
"""
CLI generator and converter for ParallelDoc documents (cockpit-v1.json).

Usage:
  python generate_paralleldoc.py --init <output.json> [--title "Document Title"]
  python generate_paralleldoc.py --from-tsv <input.tsv> -o <output.json> --title "Title"
"""

import sys
import json
import argparse
import hashlib
from datetime import datetime, timezone
from pathlib import Path

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

def create_blank_paralleldoc(title="New Document", doc_id=None, source_file=""):
    if not doc_id:
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        doc_id = f"doc_{timestamp}"

    return {
        "$schema": "https://antigravity.local/schemas/cockpit-v1.json",
        "metadata": {
            "title": title,
            "document_id": doc_id,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "source_file": source_file
        },
        "columns": [
            { "key": "col1", "title": "Original Clause (EN)", "width_weight": 30 },
            { "key": "col2", "title": "Target Translation (UA)", "width_weight": 30 },
            { "key": "col3", "title": "Engineering & Risk Assessment (EN)", "width_weight": 40 }
        ],
        "items": [
            {
                "id": "1",
                "col1": "1. First clause of the source document...",
                "col2": "1. Переклад першого пункту...",
                "col3": "✅ **Assessment:** Evaluation of terms, compliance, and operational feasibility..."
            }
        ]
    }

def save_and_report(doc_data, output_path: Path):
    json_bytes = json.dumps(doc_data, ensure_ascii=False, indent=2).encode('utf-8')
    output_path.write_bytes(json_bytes)
    sha256 = hashlib.sha256(json_bytes).hexdigest()

    print("=" * 60)
    print(f"✅ ParallelDoc JSON created: {output_path.name}")
    print("=" * 60)
    print(f"📄 Title:   {doc_data['metadata']['title']}")
    print(f"🔢 Clauses: {len(doc_data['items'])}")
    print(f"🔒 SHA-256: {sha256}")
    print("=" * 60)

def main():
    parser = argparse.ArgumentParser(description="ParallelDoc JSON Generator & Converter")
    parser.add_argument("--init", type=str, help="Initialize a template document at specified path")
    parser.add_argument("--from-tsv", type=str, help="Convert TSV file (col1 <tab> col2 <tab> col3)")
    parser.add_argument("-o", "--output", type=str, help="Output JSON path")
    parser.add_argument("--title", type=str, default="New Document", help="Document title")
    parser.add_argument("--doc-id", type=str, default=None, help="Document ID")
    parser.add_argument("--col1", type=str, default="Original Clause (EN)", help="Column 1 header")
    parser.add_argument("--col2", type=str, default="Target Translation (UA)", help="Column 2 header")
    parser.add_argument("--col3", type=str, default="Engineering & Risk Assessment (EN)", help="Column 3 header")

    args = parser.parse_args()

    if args.init:
        out = Path(args.init)
        doc = create_blank_paralleldoc(args.title, args.doc_id)
        save_and_report(doc, out)
    elif args.from_tsv:
        if not args.output:
            print("❌ Error: Specify output file with -o <output.json>")
            sys.exit(1)
        tsv_path = Path(args.from_tsv)
        if not tsv_path.exists():
            print(f"❌ File not found: {tsv_path}")
            sys.exit(1)

        items = []
        with open(tsv_path, "r", encoding="utf-8") as f:
            for idx, line in enumerate(f, start=1):
                parts = line.rstrip("\r\n").split("\t")
                if not parts or not any(parts):
                    continue
                c1 = parts[0] if len(parts) > 0 else ""
                c2 = parts[1] if len(parts) > 1 else ""
                c3 = parts[2] if len(parts) > 2 else ""
                items.append({
                    "id": str(idx),
                    "col1": c1,
                    "col2": c2,
                    "col3": c3
                })

        doc = {
            "$schema": "https://antigravity.local/schemas/cockpit-v1.json",
            "metadata": {
                "title": args.title,
                "document_id": args.doc_id or tsv_path.stem,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "source_file": tsv_path.name
            },
            "columns": [
                { "key": "col1", "title": args.col1, "width_weight": 30 },
                { "key": "col2", "title": args.col2, "width_weight": 30 },
                { "key": "col3", "title": args.col3, "width_weight": 40 }
            ],
            "items": items
        }
        save_and_report(doc, Path(args.output))
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
