"""Manifest loading and path resolution for ingested filings."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MARKDOWN_DIR = REPO_ROOT / "data" / "markdown"

TICKER_COMPANY_NAMES: dict[str, str] = {
    "AAPL": "Apple Inc.",
    "MSFT": "Microsoft Corporation",
    "NVDA": "NVIDIA Corporation",
    "AMZN": "Amazon.com, Inc.",
    "GOOGL": "Alphabet Inc.",
}


@dataclass(frozen=True)
class FilingRecord:
    ticker: str
    company_name: str
    filing_type: str
    filing_date: date | None
    fiscal_year: int | None
    accession_number: str
    source_url: str | None
    markdown_path: Path
    metadata: dict[str, Any]


def load_manifest(path: Path) -> list[FilingRecord]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    records: list[FilingRecord] = []

    for entry in payload.get("filings", []):
        records.append(_entry_to_record(entry))

    return records


def _entry_to_record(entry: dict[str, Any]) -> FilingRecord:
    ticker = entry["ticker"]
    filing_date = _parse_date(entry.get("filing_date"))
    report_date = entry.get("report_date")
    fiscal_year = int(report_date[:4]) if report_date else (
        filing_date.year if filing_date else None
    )

    local_path = entry.get("local_path", "")
    markdown_path = DEFAULT_MARKDOWN_DIR / Path(local_path).with_suffix(".md")

    return FilingRecord(
        ticker=ticker,
        company_name=TICKER_COMPANY_NAMES.get(ticker, ticker),
        filing_type=entry.get("form", "10-K"),
        filing_date=filing_date,
        fiscal_year=fiscal_year,
        accession_number=entry["accession_number"],
        source_url=entry.get("source_url"),
        markdown_path=markdown_path,
        metadata={
            "cik": entry.get("cik"),
            "primary_document": entry.get("primary_document"),
            "report_date": report_date,
        },
    )


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    return date.fromisoformat(value)
