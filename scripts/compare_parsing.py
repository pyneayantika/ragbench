"""
What it does: Prints one page in basic parsing and layout parsing, one after the other.
Why it exists: A human has to see whether layout-aware parsing fixes columns and tables.
What breaks without it: Parsing bugs stay hidden inside a character count.
Failure stage: ingestion.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.ingest import ingest_document

PREVIEW = 1500


def page_text(doc_id: str, parsing: str, page_number: int) -> str:
    pages, _hit = ingest_document(doc_id, parsing, force=False)
    for page in pages:
        if page.get("page") == page_number:
            text = page.get("text")
            return text if isinstance(text, str) else ""
    raise SystemExit(f"{doc_id} has no page {page_number} in {parsing} mode")


def main(argv: list[str]) -> None:
    if len(argv) != 2:
        raise SystemExit("Usage: python scripts/compare_parsing.py <doc_id> <page>")
    doc_id = argv[0]
    page_number = int(argv[1])
    for parsing in ("basic", "layout"):
        print(f"===== {doc_id} page {page_number} {parsing} =====")
        print(page_text(doc_id, parsing, page_number)[:PREVIEW])
        print()


if __name__ == "__main__":
    main(sys.argv[1:])
