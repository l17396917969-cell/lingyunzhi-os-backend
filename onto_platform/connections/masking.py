# onto_platform/connections/masking.py
from dataclasses import dataclass, field
from typing import Any, Iterable
import sqlglot
from sqlglot import expressions as exp

from onto_platform.proto_models import (
    OntologyRegistry, PropertyTypeDefinition,
    Sensitivity, MaskingStrategy,
)


_SENSITIVITY_ORDER: dict[Sensitivity, int] = {
    Sensitivity.SENSITIVITY_UNSPECIFIED: 0,
    Sensitivity.PUBLIC: 1,
    Sensitivity.INTERNAL: 2,
    Sensitivity.CONFIDENTIAL: 3,
    Sensitivity.RESTRICTED: 4,
}


@dataclass
class ResolvedColumn:
    name: str  # alias if present, else original column name
    sensitivity: Sensitivity = Sensitivity.SENSITIVITY_UNSPECIFIED
    masking: MaskingStrategy = MaskingStrategy.MASK_NONE
    is_resolved: bool = True


def _build_physical_to_property_index(reg: OntologyRegistry) -> dict[str, PropertyTypeDefinition]:
    """Map physical_column -> the most-restrictive PropertyType using it.

    For V1 we don't disambiguate by table; the assumption is that an operator
    binds distinct physical columns to distinct properties. If two properties
    use the same physical_column, we pick the one with the highest sensitivity.
    """
    out: dict[str, PropertyTypeDefinition] = {}

    def consider(pt: PropertyTypeDefinition) -> None:
        if not pt.physical_column:
            return
        existing = out.get(pt.physical_column)
        if existing is None or (
            _SENSITIVITY_ORDER[pt.compliance.sensitivity]
            > _SENSITIVITY_ORDER[existing.compliance.sensitivity]
        ):
            out[pt.physical_column] = pt

    for obj in reg.object_types.values():
        for pt in obj.property_types.values():
            consider(pt)
    for lt in reg.link_types.values():
        for pt in lt.property_types.values():
            consider(pt)
    return out


def _highest(*pts: PropertyTypeDefinition | None) -> PropertyTypeDefinition | None:
    real = [p for p in pts if p is not None]
    if not real:
        return None
    return max(real, key=lambda p: _SENSITIVITY_ORDER[p.compliance.sensitivity])


class MaskingResolver:
    def __init__(self, registry: OntologyRegistry, *, dialect: str) -> None:
        self._idx = _build_physical_to_property_index(registry)
        self._dialect = dialect

    def resolve(self, sql: str) -> list[ResolvedColumn]:
        parsed = sqlglot.parse_one(sql, read=self._dialect)
        # Find the outermost SELECT (handling WITH/UNION wrappers)
        select = parsed
        if isinstance(parsed, exp.With):
            select = parsed.this
        if isinstance(select, exp.Union):
            # Use the LEFT side's projections for column-name semantics
            select = select.left
        if not isinstance(select, exp.Select):
            return []
        out: list[ResolvedColumn] = []
        for proj in select.expressions:
            out.append(self._resolve_projection(proj))
        return out

    def _resolve_projection(self, proj: exp.Expression) -> ResolvedColumn:
        # Unwrap alias to learn the output name; keep the underlying expression for resolution
        if isinstance(proj, exp.Alias):
            output_name = proj.alias_or_name
            inner: exp.Expression = proj.this
        else:
            output_name = proj.alias_or_name or proj.name or str(proj)
            inner = proj
        sources = list(self._collect_source_columns(inner))
        if not sources:
            return ResolvedColumn(name=output_name, is_resolved=False)
        pts = [self._idx.get(c) for c in sources]
        winner = _highest(*pts)
        if winner is None:
            return ResolvedColumn(name=output_name, is_resolved=False)
        return ResolvedColumn(
            name=output_name,
            sensitivity=winner.compliance.sensitivity,
            masking=winner.compliance.masking,
            is_resolved=True,
        )

    def _collect_source_columns(self, node: exp.Expression) -> Iterable[str]:
        if isinstance(node, exp.Column):
            yield node.name
            return
        # recurse into all child Column references in derived expressions / aggregations
        for col in node.find_all(exp.Column):
            yield col.name


def apply_mask(value: Any, strategy: MaskingStrategy) -> Any:
    if value is None:
        return None
    if strategy is MaskingStrategy.MASK_NONE:
        return value
    if strategy is MaskingStrategy.MASK_NULLIFY:
        return None
    if strategy is MaskingStrategy.MASK_REDACT_FULL:
        return "***"
    s = str(value)
    if strategy is MaskingStrategy.SHOW_LAST_4:
        if len(s) < 4:
            return None
        return ("*" * (len(s) - 4)) + s[-4:]
    if strategy is MaskingStrategy.SHOW_FIRST_2:
        if len(s) < 2:
            return None
        return s[:2] + "****"
    if strategy is MaskingStrategy.MASK_EMAIL_DOMAIN:
        if "@" not in s:
            return None
        local, _, _ = s.partition("@")
        return f"{local}@***"
    if strategy is MaskingStrategy.MASK_EMAIL_USER:
        if "@" not in s:
            return None
        _, _, dom = s.partition("@")
        return f"***@{dom}"
    if strategy is MaskingStrategy.MASK_PHONE_MIDDLE:
        if len(s) < 7:
            return None
        return s[:3] + "****" + s[-4:]
    return value
