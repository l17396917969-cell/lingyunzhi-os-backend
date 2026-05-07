# tests/unit/test_sql_gate.py
from pathlib import Path
import pytest
from onto_platform.connections.sql_gate import gate, GateResult


REDTEAM = Path(__file__).resolve().parents[1] / "fixtures" / "sql_redteam.txt"


def _redteam_lines():
    for line in REDTEAM.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        yield line


@pytest.mark.parametrize("sql", list(_redteam_lines()))
def test_redteam_all_rejected(sql):
    res = gate(sql, dialect="mysql")
    assert isinstance(res, GateResult)
    assert res.ok is False, f"Expected rejection: {sql!r}"


@pytest.mark.parametrize("sql", [
    "SELECT 1",
    "SELECT a, b FROM t WHERE c > 1",
    "SELECT * FROM t LIMIT 10",
    "WITH d AS (SELECT a FROM t) SELECT * FROM d",
    "SELECT a FROM t1 UNION SELECT b FROM t2",
    "SELECT count(*) OVER (PARTITION BY x) FROM t",
])
def test_known_good_passes(sql):
    res = gate(sql, dialect="mysql")
    assert res.ok is True, f"Expected pass: {sql!r}; reason={res.reason}"


def test_empty_string_rejected():
    res = gate("", dialect="mysql")
    assert res.ok is False
    assert res.reason == "PARSE_ERROR"
