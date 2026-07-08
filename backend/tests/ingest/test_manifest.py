import json
from datetime import date
from pathlib import Path

from ingest.manifest import load_manifest


def test_load_manifest_resolves_markdown_paths(tmp_path: Path) -> None:
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "filings": [
                    {
                        "ticker": "AAPL",
                        "cik": "0000320193",
                        "form": "10-K",
                        "filing_date": "2024-11-01",
                        "report_date": "2024-09-28",
                        "accession_number": "0000320193-24-000123",
                        "primary_document": "aapl-20240928.htm",
                        "source_url": "https://example.com/filing",
                        "local_path": "2024/aapl_10-k_2024-11-01_0000320193-24-000123.htm",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    records = load_manifest(manifest_path)

    assert len(records) == 1
    record = records[0]
    assert record.ticker == "AAPL"
    assert record.company_name == "Apple Inc."
    assert record.filing_type == "10-K"
    assert record.filing_date == date(2024, 11, 1)
    assert record.fiscal_year == 2024
    assert record.accession_number == "0000320193-24-000123"
    assert record.markdown_path.name == "aapl_10-k_2024-11-01_0000320193-24-000123.md"
    assert "2024" in str(record.markdown_path)
