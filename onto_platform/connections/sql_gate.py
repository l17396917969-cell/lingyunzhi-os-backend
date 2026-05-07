# onto_platform/connections/sql_gate.py
from dataclasses import dataclass
from typing import Optional
import sqlglot
from sqlglot import expressions as exp


_FORBIDDEN = (
    exp.Insert, exp.Update, exp.Delete, exp.Merge, exp.Command,
    exp.Create, exp.Drop, exp.Alter,
    # sqlglot maps various write-class statements onto exp.Command with name strings;
    # we additionally enumerate node types that are unambiguously writes.
)
_FORBIDDEN_COMMAND_NAMES = {
    "TRUNCATE", "GRANT", "REVOKE", "COPY", "LOAD", "LOCK",
    "RENAME", "CALL", "SET", "ALTER", "CREATE", "DROP",
}


@dataclass
class GateResult:
    ok: bool
    reason: Optional[str] = None
    detail: Optional[str] = None


def gate(sql: str, *, dialect: str) -> GateResult:
    if not sql or not sql.strip():
        return GateResult(False, "PARSE_ERROR", "empty SQL")
    try:
        parsed = sqlglot.parse(sql, read=dialect)
    except Exception as e:
        return GateResult(False, "PARSE_ERROR", str(e))
    statements = [s for s in parsed if s is not None]
    if len(statements) != 1:
        return GateResult(False, "MULTIPLE_STATEMENTS", f"got {len(statements)} statements")
    root = statements[0]
    # Root must be SELECT-shaped
    if not isinstance(root, (exp.Select, exp.Union, exp.With, exp.Subquery)):
        return GateResult(False, "NOT_SELECT", f"root is {type(root).__name__}")
    # WITH must terminate in a SELECT
    if isinstance(root, exp.With):
        body = root.this
        if not isinstance(body, (exp.Select, exp.Union)):
            return GateResult(False, "NOT_SELECT", "WITH body is not SELECT/UNION")
        # CTE definitions themselves must not be DML/DDL
        for cte in root.expressions:
            if isinstance(cte.this, _FORBIDDEN):
                return GateResult(
                    False,
                    f"WRITE_NODE_{type(cte.this).__name__.upper()}",
                    f"CTE contains {type(cte.this).__name__}",
                )
    # Sweep entire AST for forbidden nodes
    for node in root.walk():
        if isinstance(node, _FORBIDDEN):
            return GateResult(
                False, f"WRITE_NODE_{type(node).__name__.upper()}", str(node)[:120]
            )
        if isinstance(node, exp.Command):
            cname = (node.this or "").upper()
            if cname in _FORBIDDEN_COMMAND_NAMES:
                return GateResult(False, f"WRITE_NODE_{cname}", str(node)[:120])
    return GateResult(ok=True)
