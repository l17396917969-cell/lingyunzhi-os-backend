from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Iterable
from onto_platform.proto_models import OntologyRegistry


class Severity(str, Enum):
    ERROR = "ERROR"
    WARNING = "WARNING"


@dataclass
class Finding:
    severity: Severity
    code: str
    path: str
    message: str
    details: dict[str, Any] = field(default_factory=dict)

    @property
    def is_error(self) -> bool:
        return self.severity is Severity.ERROR


@dataclass
class ValidatorCtx:
    connection_ids: set[str]


_CheckerFn = Callable[[OntologyRegistry, ValidatorCtx], Iterable[Finding]]
_CHECKERS: list[_CheckerFn] = []


def checker(fn: _CheckerFn) -> _CheckerFn:
    """Register a checker. Each checker is `(registry, ctx) -> Iterable[Finding]`."""
    _CHECKERS.append(fn)
    return fn


def validate(registry: OntologyRegistry, *, connection_ids: set[str]) -> list[Finding]:
    ctx = ValidatorCtx(connection_ids=connection_ids)
    findings: list[Finding] = []
    for fn in _CHECKERS:
        for f in fn(registry, ctx):
            findings.append(f)
    return findings


def has_errors(findings: Iterable[Finding]) -> bool:
    return any(f.is_error for f in findings)


# trigger checker registration
from onto_platform.registry import checks  # noqa: E402,F401
