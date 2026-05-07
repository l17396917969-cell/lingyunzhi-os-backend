# onto_platform/connections/data_query.py
import uuid
from typing import Any, Optional, Union
import sqlglot
from sqlglot import expressions as exp
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from onto_platform.proto_models import (
    OntologyRegistry, MaskingStrategy,
    ObjectTypeDefinition, LinkTypeDefinition,
)
from onto_platform.connections.pool import ConnectionPool
from onto_platform.connections.sql_gate import gate
from onto_platform.connections.masking import MaskingResolver, apply_mask


class SqlRejectedError(Exception):
    def __init__(self, reason: str, detail: Optional[str] = None):
        super().__init__(f"SQL rejected: {reason}")
        self.reason = reason
        self.detail = detail


def _ensure_limit(sql: str, dialect: str, cap: int) -> str:
    """Inject or shrink LIMIT to (cap+1). Used to detect truncation."""
    parsed = sqlglot.parse_one(sql, read=dialect)
    select = parsed
    if isinstance(parsed, exp.With):
        select = parsed.this
    if isinstance(select, exp.Union):
        # Wrap as subquery so we can attach a single LIMIT
        wrapped = exp.Select().select("*").from_(exp.Subquery(this=parsed, alias=exp.TableAlias(this=exp.to_identifier("sub"))))
        wrapped.set("limit", exp.Limit(expression=exp.Literal.number(cap + 1)))
        return wrapped.sql(dialect=dialect)
    if not isinstance(select, exp.Select):
        return sql
    existing_limit = select.args.get("limit")
    target = cap + 1
    if existing_limit is None:
        select.set("limit", exp.Limit(expression=exp.Literal.number(target)))
    else:
        try:
            lim_expr = existing_limit.args.get("expression")
            existing_value = int(str(lim_expr)) if lim_expr is not None else target + 1
            if existing_value > target:
                select.set("limit", exp.Limit(expression=exp.Literal.number(target)))
        except (ValueError, AttributeError):
            select.set("limit", exp.Limit(expression=exp.Literal.number(target)))
    return parsed.sql(dialect=dialect)


async def query_sql(
    session: AsyncSession,
    *,
    pool: ConnectionPool,
    connection_id: uuid.UUID,
    sql: str,
    max_rows: int,
    timeout_ms: int,
    registry: OntologyRegistry,
    dialect: str,
) -> dict[str, Any]:
    g = gate(sql, dialect=dialect)
    if not g.ok:
        raise SqlRejectedError(g.reason or "UNKNOWN", g.detail)

    resolver = MaskingResolver(registry, dialect=dialect)
    resolved_columns = resolver.resolve(sql)

    rewritten_sql = _ensure_limit(sql, dialect, max_rows)

    async with pool.session(session, connection_id, timeout_ms=timeout_ms) as conn:
        result = await conn.execute(text(rewritten_sql))
        column_names = [str(c) for c in result.keys()]
        rows_raw = result.fetchall()

    truncated = len(rows_raw) > max_rows
    if truncated:
        rows_raw = rows_raw[:max_rows]

    # Align resolved_columns by output name. The resolver works on the original
    # SQL; column ordering matches DB result keys for direct projections.
    resolved_by_name = {rc.name: rc for rc in resolved_columns}

    masked_columns: list[str] = []
    columns_meta: list[dict[str, Any]] = []
    unresolved: list[str] = []
    for cn in column_names:
        rc = resolved_by_name.get(cn)
        if rc is None or not rc.is_resolved:
            unresolved.append(cn)
            columns_meta.append({"name": cn, "data_type": None, "resolved_property_rid": None})
        else:
            columns_meta.append({"name": cn, "data_type": None, "resolved_property_rid": None})
            if rc.masking is not MaskingStrategy.MASK_NONE:
                masked_columns.append(cn)

    out_rows: list[list[Any]] = []
    for r in rows_raw:
        out_row = []
        for i, cn in enumerate(column_names):
            v = r[i]
            rc = resolved_by_name.get(cn)
            if rc is not None and rc.is_resolved and rc.masking is not MaskingStrategy.MASK_NONE:
                v = apply_mask(v, rc.masking)
            out_row.append(v)
        out_rows.append(out_row)

    return {
        "columns": columns_meta,
        "rows": out_rows,
        "row_count": len(out_rows),
        "truncated": truncated,
        "masked_columns": masked_columns,
        "unresolved_columns": unresolved,
    }


class BoundAssetNotFoundError(Exception):
    pass


class AssetUnboundError(Exception):
    pass


def describe_bound_asset(registry: OntologyRegistry, target_rid: str) -> dict[str, Any]:
    entity: Union[ObjectTypeDefinition, LinkTypeDefinition]
    if target_rid in registry.object_types:
        entity = registry.object_types[target_rid]
    elif target_rid in registry.link_types:
        entity = registry.link_types[target_rid]
    else:
        raise BoundAssetNotFoundError(target_rid)
    am = entity.asset_mapping
    if not (am.read_connection_id or am.read_asset_path):
        raise AssetUnboundError(target_rid)
    columns = []
    for pt in entity.property_types.values():
        columns.append({
            "api_name": pt.api_name,
            "physical_column": pt.physical_column,
            "data_type": pt.data_type.value if hasattr(pt.data_type, "value") else str(pt.data_type),
            "sensitivity": pt.compliance.sensitivity.value,
            "masking_strategy": pt.compliance.masking.value,
            "property_rid": pt.rid,
        })
    return {
        "rid": target_rid,
        "connection_id": entity.asset_mapping.read_connection_id,
        "asset_path": entity.asset_mapping.read_asset_path,
        "columns": columns,
    }
