"""Convert downloaded SEC filing HTML files to Markdown with docling.

Mirrors `data/downloads/<year>/<file>.htm` into `data/markdown/<year>/<file>.md`,
keeping the same year-based directory structure.

Run from `backend/`: `uv run python -m ingest.convert_html_to_markdown`
"""

from __future__ import annotations

from pathlib import Path

from docling.document_converter import DocumentConverter

REPO_ROOT = Path(__file__).resolve().parents[2]
INPUT_DIR = REPO_ROOT / "data" / "downloads"
OUTPUT_DIR = REPO_ROOT / "data" / "markdown"


def convert_all() -> int:
    converter = DocumentConverter()
    html_paths = sorted(INPUT_DIR.rglob("*.htm*"))

    converted = 0
    for html_path in html_paths:
        relative_path = html_path.relative_to(INPUT_DIR)
        markdown_path = (OUTPUT_DIR / relative_path).with_suffix(".md")
        markdown_path.parent.mkdir(parents=True, exist_ok=True)

        print(f"Converting {relative_path}...")
        result = converter.convert(html_path)
        markdown_path.write_text(result.document.export_to_markdown(), encoding="utf-8")
        converted += 1

    return converted


if __name__ == "__main__":
    count = convert_all()
    print(f"Converted {count} file(s) to {OUTPUT_DIR}")
