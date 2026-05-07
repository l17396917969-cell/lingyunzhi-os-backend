from dataclasses import dataclass, field
from typing import Any


class ExtractionFailure(Exception):
    """Raised when an extractor cannot parse a file."""


@dataclass
class Section:
    heading: str
    text: str
    structured: dict[str, Any] = field(default_factory=dict)


@dataclass
class ExtractedDocument:
    kind: str
    source_filename: str
    sections: list[Section]


@dataclass
class ExtractionBundle:
    documents: list[ExtractedDocument]
