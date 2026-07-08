# Data

Local data artifacts for development live here.

- `downloads/` holds raw source files fetched from SEC EDGAR, grouped by year.
- `markdown/` holds the same filings converted to Markdown via docling, mirroring the `downloads/` year-based structure.
- Downloaded payloads and converted Markdown are gitignored because the corpus can get large.
- Fetch a sample corpus with `uv run data/download.py`
- Convert the corpus to Markdown (from `backend/`) with `uv run python -m ingest.convert_html_to_markdown`
- Ingest Markdown into Supabase (from `backend/`) with `uv run python -m ingest.run --manifest ../data/downloads/manifest.json --convert`
