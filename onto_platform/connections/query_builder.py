"""
InstanceQueryBuilder – builds safe SELECT queries from ObjectType definitions
and executes them via ConnectionPool.
"""

import uuid
from dataclasses import dataclass
from typing import Any, Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from onto_platform.connections.dialect_engine import DialectEngine, UnsupportedDialectError
from onto_platform.connections.pool import ConnectionPool
from onto_platform.connections.sql_gate import gate as sql_gate
from onto_platform.connections.store import ConnectionKind, ConnectionStore
from onto_platform.proto_models import ObjectTypeDefinition, PropertyTypeDefinition
from onto_platform.registry.store import RegistryStore, Env


@dataclass
class InstanceColumn:
    api_name: str
    display_name: str
    physical_column: str


@dataclass
class InstanceData:
    object_type_rid: str
    object_type_name: str
    columns: list[InstanceColumn]
    data: list[dict[str, Any]]
    total: int
    page: int
    page_size: int
    has_more: bool


class QueryBuildError(Exception):
    pass


class InstanceQueryBuilder:
    """Build and execute read-only instance queries from ObjectType definitions."""

    _DEFAULT_PAGE_SIZE = 20
    _MAX_PAGE_SIZE = 100

    def __init__(
        self,
        *,
        registry_store: RegistryStore,
        connection_pool: ConnectionPool,
        connection_store: ConnectionStore,
    ) -> None:
        self._rstore = registry_store
        self._pool = connection_pool
        self._cstore = connection_store

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def query(
        self,
        session: AsyncSession,
        object_type_rid: str,
        *,
        page: int = 1,
        page_size: int = _DEFAULT_PAGE_SIZE,
        search: Optional[str] = None,
        sort_field: Optional[str] = None,
        sort_order: str = "asc",
        env: Env = Env.production,
    ) -> InstanceData:
        """Execute a paginated, searchable, sortable query for an ObjectType."""
        # 1. Resolve ObjectType
        obj = await self._resolve_object_type(session, object_type_rid, env)

        # 2. Validate asset mapping
        mapping = obj.asset_mapping
        if not mapping.read_connection_id:
            raise QueryBuildError(
                f"ObjectType {object_type_rid} has no read_connection_id in asset_mapping"
            )
        if not mapping.read_asset_path:
            raise QueryBuildError(
                f"ObjectType {object_type_rid} has no read_asset_path in asset_mapping"
            )

        connection_id = uuid.UUID(mapping.read_connection_id)
        table = mapping.read_asset_path

        # 3. Resolve connection dialect
        conn_meta = await self._cstore.get_by_id(session, connection_id)
        dialect = self._kind_to_dialect(conn_meta.kind)

        # 4. Build column mapping
        columns, col_map = self._build_columns(obj.property_types)
        if not columns:
            raise QueryBuildError(
                f"ObjectType {object_type_rid} has no property types with physical_column"
            )

        # 5. Build WHERE conditions
        where_conditions = []
        if search:
            # Search across all string-like columns
            for col in columns:
                where_conditions.append(
                    DialectEngine.build_like_condition(col.physical_column, search)
                )

        # 6. Map sort_field from api_name to physical_column
        order_by: Optional[tuple[str, str]] = None
        if sort_field:
            physical = col_map.get(sort_field)
            if not physical:
                raise QueryBuildError(
                    f"Sort field '{sort_field}' not found in ObjectType property types"
                )
            order_by = (physical, sort_order)

        # 7. Clamp pagination
        page = max(1, page)
        page_size = min(max(1, page_size), self._MAX_PAGE_SIZE)
        offset = (page - 1) * page_size

        # 8. Build COUNT query
        count_ast = DialectEngine.build_count(table, where_conditions=where_conditions if not search else None)
        # For search, we need OR logic across LIKE conditions; sqlglot's ILIKE doesn't chain with AND
        if search and where_conditions:
            from sqlglot import expressions as exp
            or_pred = where_conditions[0]
            for cond in where_conditions[1:]:
                or_pred = exp.Or(this=or_pred, expression=cond)
            count_ast = count_ast.where(or_pred)

        count_sql = DialectEngine.generate_sql(count_ast, dialect)
        gate_result = sql_gate(count_sql, dialect=dialect)
        if not gate_result.ok:
            raise QueryBuildError(
                f"SQL gate rejected COUNT query: {gate_result.reason} – {gate_result.detail}"
            )

        # 9. Build SELECT query
        physical_cols = [c.physical_column for c in columns]
        select_ast = DialectEngine.build_select(
            physical_cols,
            table,
            where_conditions=where_conditions if not search else None,
            order_by=order_by,
            limit=page_size,
            offset=offset,
        )
        if search and where_conditions:
            from sqlglot import expressions as exp
            or_pred = where_conditions[0]
            for cond in where_conditions[1:]:
                or_pred = exp.Or(this=or_pred, expression=cond)
            select_ast = select_ast.where(or_pred)

        select_sql = DialectEngine.generate_sql(select_ast, dialect)
        gate_result = sql_gate(select_sql, dialect=dialect)
        if not gate_result.ok:
            raise QueryBuildError(
                f"SQL gate rejected SELECT query: {gate_result.reason} – {gate_result.detail}"
            )

        # 10. Execute queries via ConnectionPool
        async with self._pool.session(session, connection_id) as conn:
            # COUNT
            count_row = await conn.execute(text(count_sql))
            total = count_row.scalar_one()

            # SELECT
            rows = await conn.execute(text(select_sql))
            raw_data = [dict(r._mapping) for r in rows]

        # 11. Format result – map physical_column back to api_name for display
        formatted = [
            {c.api_name: row.get(c.physical_column) for c in columns}
            for row in raw_data
        ]

        return InstanceData(
            object_type_rid=object_type_rid,
            object_type_name=obj.display_name or obj.api_name,
            columns=columns,
            data=formatted,
            total=total,
            page=page,
            page_size=page_size,
            has_more=total > page * page_size,
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    async def _resolve_object_type(
        self,
        session: AsyncSession,
        rid: str,
        env: Env,
    ) -> ObjectTypeDefinition:
        snap = await self._rstore.load(session, env)
        obj = snap.registry.object_types.get(rid)
        if obj is None:
            raise QueryBuildError(f"ObjectType rid={rid} not found in {env.value}")
        return obj

    @staticmethod
    def _kind_to_dialect(kind: ConnectionKind) -> str:
        return {
            ConnectionKind.postgres: "postgres",
            ConnectionKind.mysql: "mysql",
            ConnectionKind.sqlite: "sqlite",
        }.get(kind, "postgres")

    @staticmethod
    def _build_columns(
        property_types: dict[str, PropertyTypeDefinition],
    ) -> tuple[list[InstanceColumn], dict[str, str]]:
        """Return (ordered columns, api_name → physical_column map)."""
        columns: list[InstanceColumn] = []
        col_map: dict[str, str] = {}
        for prop in property_types.values():
            if prop.physical_column:
                columns.append(
                    InstanceColumn(
                        api_name=prop.api_name,
                        display_name=prop.display_name or prop.api_name,
                        physical_column=prop.physical_column,
                    )
                )
                col_map[prop.api_name] = prop.physical_column
        return columns, col_map
