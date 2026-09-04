#!/usr/bin/env python3
"""
Validator and SHA-256 Hasher for ParallelDoc documents.
Usage: python validate_document.py <path_to_file.json>
"""

import sys
import json
import hashlib
from pathlib import Path

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

def validate_paralleldoc_json(filepath: Path):
    if not filepath.exists():
        print(f"❌ Error: File not found: {filepath}")
        sys.exit(1)

    raw_text = filepath.read_text(encoding='utf-8')
    normalized_bytes = raw_text.replace('\r\n', '\n').encode('utf-8')
    sha256_hash = hashlib.sha256(normalized_bytes).hexdigest()

    try:
        data = json.loads(raw_text)
    except Exception as e:
        print(f"❌ JSON decode error: {e}")
        sys.exit(1)

    # Structure validation
    errors = []
    if "metadata" not in data or not isinstance(data["metadata"], dict):
        errors.append("Missing required object 'metadata'")
    elif not data["metadata"].get("title"):
        errors.append("Field 'metadata.title' is required and must not be empty")

    if "columns" not in data or not isinstance(data["columns"], list) or len(data["columns"]) != 3:
        errors.append("Field 'columns' must be an array of exactly 3 column objects")

    if "items" not in data or not isinstance(data["items"], list):
        errors.append("Field 'items' must be an array")
    else:
        for idx, item in enumerate(data["items"]):
            row_id = item.get("id", f"idx_{idx}")
            for col in ["col1", "col2", "col3"]:
                if col not in item:
                    errors.append(f"Row #{row_id} missing required field '{col}'")

    if errors:
        print("❌ Document validation failed:")
        for err in errors:
            print(f"  - {err}")
        sys.exit(1)

    title = data["metadata"].get("title")
    count = len(data["items"])
    cols = [c.get("title", f"Col {i+1}") for i, c in enumerate(data.get("columns", []))]

    print("=" * 60)
    print("✅ Document is 100% valid and ready for ParallelDoc!")
    print("=" * 60)
    print(f"📄 Document:   {title}")
    print(f"🔢 Clauses:    {count}")
    print(f"📊 Columns:    {' | '.join(cols)}")
    print(f"🔒 SHA-256:    {sha256_hash}")
    print("=" * 60)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        default_file = Path(__file__).parent / "sample_document.json"
        if default_file.exists():
            validate_paralleldoc_json(default_file)
        else:
            print("Usage: python validate_document.py <document.json>")
    else:
        validate_paralleldoc_json(Path(sys.argv[1]))
