"""CLI entrypoint for ingesting SEC filings into Supabase."""

from __future__ import annotations

import argparse
from pathlib import Path

from app.database.supabase import get_admin_client

from ingest.convert_html_to_markdown import convert_all
from ingest.filing import ingest_filing
from ingest.manifest import load_manifest


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest SEC filings into Supabase")
    parser.add_argument(
        "--manifest",
        type=Path,
        required=True,
        help="Default: Path to data/downloads/manifest.json",
        default="../data/downloads/manifest.json",
    )
    parser.add_argument(
        "--convert",
        action="store_true",
        help="Convert HTML downloads to Markdown before ingesting",
    )
    parser.add_argument(
        "--ticker",
        action="append",
        help="Limit ingestion to one or more tickers (repeatable)",
    )
    args = parser.parse_args()

    if args.convert:
        converted = convert_all()
        print(f"Converted {converted} HTML file(s) to Markdown")

    records = load_manifest(args.manifest)
    if args.ticker:
        allowed = {ticker.upper() for ticker in args.ticker}
        records = [record for record in records if record.ticker in allowed]

    if not records:
        print("No filings to ingest.")

        return

    client = get_admin_client()
    for record in records:
        print(f"Ingesting {record.ticker} {record.accession_number}...")
        result = ingest_filing(client, record)
        print(
            f"  Saved document {result['document_id']} with {result['chunks']} chunk(s)"
        )


if __name__ == "__main__":
    main()

# if __name__ == "__main__":
#     import sys

#     sys.argv = [
#         "ingest.run",
#         "--manifest",
#         "../data/downloads/manifest.json",
#         "--ticker",
#         "AAPL",
#     ]
#     main()
