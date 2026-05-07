import pytest
from pathlib import Path
from onto_platform.ingestion.extractors.sql_ext import extract_sql

pytestmark = pytest.mark.asyncio


async def test_extract_sql_finds_two_tables(tmp_path):
    fixture = Path(__file__).resolve().parents[1] / "fixtures" / "extractors" / "sample.sql"
    doc = await extract_sql(str(fixture), "sample.sql")
    assert doc.kind == "sql"
    headings = [s.heading for s in doc.sections]
    assert any("customers" in h for h in headings)
    assert any("orders" in h for h in headings)
    # structured payload includes columns
    cols_section = next(s for s in doc.sections if "customers" in s.heading)
    cols = cols_section.structured.get("columns", [])
    assert any(c["name"] == "id" for c in cols)
