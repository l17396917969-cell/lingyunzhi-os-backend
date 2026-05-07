import pytest
from onto_platform.ingestion.extractors.pdf_ext import extract_pdf
from onto_platform.ingestion.extractors.types import ExtractionFailure

pytestmark = pytest.mark.asyncio


@pytest.fixture(scope="module")
def sample_pdf(tmp_path_factory):
    from reportlab.pdfgen import canvas
    p = tmp_path_factory.mktemp("pdf") / "sample.pdf"
    c = canvas.Canvas(str(p))
    c.drawString(72, 720, "Materials master data")
    c.drawString(72, 700, "MD_MATERIAL holds part numbers and cost.")
    c.showPage()
    c.drawString(72, 720, "Stations")
    c.drawString(72, 700, "MD_STATION lists workshop stations.")
    c.save()
    return p


async def test_extract_pdf_yields_pages(sample_pdf):
    doc = await extract_pdf(str(sample_pdf), "sample.pdf")
    assert doc.kind == "pdf"
    assert len(doc.sections) == 2
    assert "Materials master data" in doc.sections[0].text


async def test_extract_pdf_corrupt_raises(tmp_path):
    bad = tmp_path / "bad.pdf"
    bad.write_bytes(b"not really a pdf")
    with pytest.raises(ExtractionFailure):
        await extract_pdf(str(bad), "bad.pdf")
