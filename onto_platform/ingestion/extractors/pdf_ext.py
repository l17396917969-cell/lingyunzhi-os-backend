import asyncio

from pypdf import PdfReader
from pypdf.errors import PdfReadError

from onto_platform.ingestion.extractors.types import (
    ExtractedDocument,
    ExtractionFailure,
    Section,
)


async def extract_pdf(path: str, filename: str) -> ExtractedDocument:
    def _do() -> ExtractedDocument:
        try:
            reader = PdfReader(path)
        except (PdfReadError, Exception) as e:
            raise ExtractionFailure(f"pypdf failed on {filename}: {e}") from e
        sections: list[Section] = []
        for i, page in enumerate(reader.pages):
            try:
                text = page.extract_text() or ""
            except Exception as e:
                raise ExtractionFailure(
                    f"pypdf page {i + 1} failed on {filename}: {e}"
                ) from e
            sections.append(Section(heading=f"page {i + 1}", text=text))
        return ExtractedDocument(kind="pdf", source_filename=filename, sections=sections)

    return await asyncio.to_thread(_do)
