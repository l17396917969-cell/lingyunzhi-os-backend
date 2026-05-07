import aiofiles
import sqlglot
from sqlglot import expressions as exp
from sqlglot.errors import ErrorLevel

from onto_platform.ingestion.extractors.types import (
    ExtractedDocument,
    ExtractionFailure,
    Section,
)


async def extract_sql(path: str, filename: str) -> ExtractedDocument:
    async with aiofiles.open(path, "r") as f:
        text = await f.read()
    try:
        statements = sqlglot.parse(text, read="mysql", error_level=ErrorLevel.IGNORE)
    except Exception as e:
        raise ExtractionFailure(f"sqlglot failed on {filename}: {e}") from e
    sections: list[Section] = []
    for stmt in statements:
        if stmt is None:
            continue
        if isinstance(stmt, exp.Create) and stmt.this and isinstance(stmt.this, exp.Schema):
            tname = stmt.this.this.name if stmt.this.this else "?"
            cols = []
            for col in stmt.this.expressions:
                if isinstance(col, exp.ColumnDef):
                    cols.append({
                        "name": col.this.name,
                        "type": str(col.args.get("kind") or ""),
                    })
            sections.append(Section(
                heading=f"CREATE TABLE {tname}",
                text=stmt.sql(dialect="mysql"),
                structured={"table": tname, "columns": cols},
            ))
    return ExtractedDocument(kind="sql", source_filename=filename, sections=sections)
