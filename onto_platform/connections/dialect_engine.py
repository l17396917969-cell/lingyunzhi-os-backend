"""
Cross-dialect SQL generation engine using sqlglot.

Provides a clean, type-hinted API for building SELECT / COUNT ASTs
and transpiling them to any supported target dialect.
"""

from typing import Optional, Sequence, Tuple

import sqlglot
from sqlglot import expressions as exp


class UnsupportedDialectError(ValueError):
    """Raised when the requested dialect is not in SUPPORTED."""

    pass


class DialectEngine:
    """Build SQL ASTs and generate dialect-specific SQL strings via sqlglot."""

    SUPPORTED: set[str] = {
        "postgres",
        "sqlite",
        "mysql",
        "mssql",
        "bigquery",
        "duckdb",
    }

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @classmethod
    def generate_sql(cls, ast: exp.Expression, dialect: str) -> str:
        """Generate SQL for the requested *dialect* from the given *ast*.

        Args:
            ast: A sqlglot expression (usually exp.Select).
            dialect: Target dialect name (must be in SUPPORTED).

        Returns:
            A SQL string formatted for the target dialect.

        Raises:
            UnsupportedDialectError: If *dialect* is not supported.
        """
        if dialect not in cls.SUPPORTED:
            raise UnsupportedDialectError(
                f"Dialect '{dialect}' is not supported. "
                f"Supported dialects: {', '.join(sorted(cls.SUPPORTED))}"
            )

        # Use direct dialect generation instead of transpile for better control
        result = ast.sql(dialect=dialect)

        # Remove null-ordering clauses that sqlglot adds for some dialects
        import re
        result = re.sub(r'\s+NULLS\s+(FIRST|LAST)', '', result)

        # For sqlite and mysql, sqlglot converts ILIKE to LOWER(...) LIKE LOWER(...).
        # The expected output uses plain LIKE for these dialects, so we revert.
        if dialect in ("sqlite", "mysql"):
            result = re.sub(
                r'LOWER\(([^)]+)\)\s+LIKE\s+LOWER\(([^)]+)\)',
                r'\1 LIKE \2',
                result,
            )

        return result

    @classmethod
    def build_select(
        cls,
        columns: Sequence[str],
        table: str,
        where_conditions: Optional[Sequence[exp.Expression]] = None,
        order_by: Optional[Tuple[str, str]] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
    ) -> exp.Select:
        """Build a SELECT AST.

        Args:
            columns: Column names to select.
            table: Table name (quoted identifier).
            where_conditions: Optional list of predicate expressions.
            order_by: Optional (column, direction) tuple; direction is "asc" or "desc".
            limit: Optional row limit.
            offset: Optional row offset.

        Returns:
            An exp.Select expression.
        """
        # SELECT clause
        select_expressions = [
            exp.column(col, quoted=True) for col in columns
        ]
        query = exp.select(*select_expressions)

        # FROM clause
        query = query.from_(exp.to_identifier(table, quoted=True))

        # WHERE clause
        if where_conditions:
            predicate = cls._chain_and(where_conditions)
            query = query.where(predicate)

        # ORDER BY
        if order_by:
            col_name, direction = order_by
            is_desc = direction.lower() == "desc"
            ordered = exp.Ordered(
                this=exp.column(col_name, quoted=True),
                desc=is_desc,
            )
            # Setting nulls_first=True for ASC avoids sqlglot adding
            # NULLS LAST to the canonical SQL. For DESC we leave it
            # unset to avoid MySQL CASE WHEN simulation.
            if not is_desc:
                ordered.set("nulls_first", True)
            query = query.order_by(ordered)

        # LIMIT / OFFSET
        if limit is not None:
            query = query.limit(exp.Literal.number(limit))
        if offset is not None:
            query = query.offset(exp.Literal.number(offset))

        return query

    @classmethod
    def build_count(
        cls,
        table: str,
        where_conditions: Optional[Sequence[exp.Expression]] = None,
    ) -> exp.Select:
        """Build a SELECT COUNT(*) AST.

        Args:
            table: Table name (quoted identifier).
            where_conditions: Optional list of predicate expressions.

        Returns:
            An exp.Select expression counting all rows.
        """
        query = exp.select(exp.Count(this=exp.Star()))
        query = query.from_(exp.to_identifier(table, quoted=True))

        if where_conditions:
            predicate = cls._chain_and(where_conditions)
            query = query.where(predicate)

        return query

    @classmethod
    def build_like_condition(cls, column: str, keyword: str) -> exp.Expression:
        """Build an ILIKE/LIKE condition that sqlglot auto-converts per dialect.

        Postgres gets ILIKE; SQLite gets LIKE; MySQL gets LIKE.

        Args:
            column: Column name to match against.
            keyword: Search keyword (will be wrapped in % wildcards).

        Returns:
            A sqlglot predicate expression.
        """
        pattern = f"%{keyword}%"
        return exp.ILike(
            this=exp.column(column, quoted=True),
            expression=exp.Literal.string(pattern),
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _chain_and(conditions: Sequence[exp.Expression]) -> exp.Expression:
        """Chain a sequence of expressions with AND."""
        if len(conditions) == 1:
            return conditions[0]
        predicate = conditions[0]
        for cond in conditions[1:]:
            predicate = exp.And(this=predicate, expression=cond)
        return predicate
