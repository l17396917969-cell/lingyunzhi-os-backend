# tests/unit/test_extractor_dispatch.py
import pytest
from onto_platform.ingestion.extractors import get_extractor
from onto_platform.ingestion.extractors.types import (
    ExtractedDocument, Section, ExtractionFailure,
)


def test_get_extractor_for_known_extensions():
    for ext in ("sql", "pdf", "docx", "pptx", "xlsx"):
        ex = get_extractor(ext)
        assert callable(ex)


def test_unknown_extension_raises():
    with pytest.raises(ExtractionFailure):
        get_extractor("exe")


def test_section_round_trip():
    s = Section(heading="title", text="body")
    d = ExtractedDocument(kind="sql", source_filename="x.sql", sections=[s])
    assert d.sections[0].heading == "title"
