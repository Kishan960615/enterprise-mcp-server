"""Bounded read-only SQL connector."""

from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine
from sqlglot import exp, parse

from enterprise_mcp.domain import ToolResult, ValidationError


class SqlConnector:
    def __init__(self, engines: dict[str, AsyncEngine], max_rows: int) -> None:
        self._engines = engines
        self._max_rows = max_rows

    @staticmethod
    def validate(query: str) -> None:
        try:
            statements = parse(query, read="postgres")
        except Exception as exc:
            raise ValidationError("SQL could not be parsed") from exc
        if len(statements) != 1:
            raise ValidationError("exactly one SQL statement is required")
        statement = statements[0]
        if not isinstance(statement, (exp.Select, exp.Union, exp.Intersect, exp.Except)):
            raise ValidationError("only read-only SELECT queries are permitted")
        forbidden = (exp.Insert, exp.Update, exp.Delete, exp.Create, exp.Drop, exp.Alter)
        if any(statement.find(node) is not None for node in forbidden):
            raise ValidationError("mutating SQL is forbidden")

    async def query(
        self,
        connection: str,
        query: str,
        parameters: dict[str, Any] | None = None,
        max_rows: int = 100,
    ) -> ToolResult:
        self.validate(query)
        try:
            engine = self._engines[connection]
        except KeyError as exc:
            raise ValidationError("unknown SQL connection") from exc
        limit = min(max_rows, self._max_rows)
        # The query passed the SELECT-only AST validator above; the only interpolated
        # server value is an integer clamped by policy.
        wrapped = (
            f"SELECT * FROM ({query.rstrip().rstrip(';')}) "  # noqa: S608
            f"AS enterprise_mcp_query LIMIT {limit + 1}"
        )
        async with engine.connect() as connection_handle:
            result = await connection_handle.execute(text(wrapped), parameters or {})
            rows = result.mappings().fetchmany(limit + 1)
        truncated = len(rows) > limit
        output = [dict(row) for row in rows[:limit]]
        return ToolResult(
            data={"columns": list(result.keys()), "rows": output, "row_count": len(output)},
            truncated=truncated,
        )
