from collections.abc import Awaitable, Callable

from onto_platform.ingestion.extractors.types import ExtractedDocument, ExtractionFailure


def get_extractor(ext: str) -> Callable[[str, str], Awaitable[ExtractedDocument]]:
    e = ext.lower().lstrip(".")
    if e == "sql":
        from onto_platform.ingestion.extractors.sql_ext import extract_sql
        return extract_sql
    if e == "pdf":
        from onto_platform.ingestion.extractors.pdf_ext import extract_pdf
        return extract_pdf
    if e == "docx":
        from onto_platform.ingestion.extractors.docx_ext import extract_docx
        return extract_docx
    if e == "pptx":
        from onto_platform.ingestion.extractors.pptx_ext import extract_pptx
        return extract_pptx
    if e == "xlsx":
        from onto_platform.ingestion.extractors.xlsx_ext import extract_xlsx
        return extract_xlsx
    raise ExtractionFailure(f"Unsupported extension: {e}")
