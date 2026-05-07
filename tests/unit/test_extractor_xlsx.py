import pytest
from onto_platform.ingestion.extractors.xlsx_ext import extract_xlsx
from onto_platform.ingestion.extractors.types import ExtractionFailure

pytestmark = pytest.mark.asyncio


@pytest.fixture(scope="module")
def sample_xlsx(tmp_path_factory):
    from openpyxl import Workbook
    p = tmp_path_factory.mktemp("xlsx") / "sample.xlsx"
    wb = Workbook()
    ws = wb.active
    ws.title = "Materials"
    ws.append(["material_code", "material_name", "cost_price"])
    ws.append(["MTL-0001", "Bolt", 1.25])
    ws.append(["MTL-0002", "Nut", 0.40])
    ws2 = wb.create_sheet("Stations")
    ws2.append(["station_code", "station_name"])
    ws2.append(["ST-A1", "Receiving"])
    wb.save(str(p))
    return p


async def test_extract_xlsx_per_sheet(sample_xlsx):
    doc = await extract_xlsx(str(sample_xlsx), "sample.xlsx")
    assert doc.kind == "xlsx"
    headings = [s.heading for s in doc.sections]
    assert "Materials" in headings and "Stations" in headings
    mat = next(s for s in doc.sections if s.heading == "Materials")
    assert mat.structured["headers"] == ["material_code", "material_name", "cost_price"]
    assert len(mat.structured["sample_rows"]) == 2


async def test_extract_xlsx_corrupt_raises(tmp_path):
    bad = tmp_path / "bad.xlsx"
    bad.write_bytes(b"not an xlsx")
    with pytest.raises(ExtractionFailure):
        await extract_xlsx(str(bad), "bad.xlsx")
