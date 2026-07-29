"""Allowlisted named REST operation connector."""

from typing import Any
from urllib.parse import urlparse

import httpx

from enterprise_mcp.domain import DependencyError, ToolResult, ValidationError


class RestConnector:
    def __init__(
        self,
        operations: dict[str, dict[str, str]],
        client: httpx.AsyncClient,
        max_result_bytes: int,
    ) -> None:
        self._operations = operations
        self._client = client
        self._max_result_bytes = max_result_bytes

    async def request(
        self,
        operation: str,
        query: dict[str, str] | None = None,
    ) -> ToolResult:
        try:
            config = self._operations[operation]
            method = config["method"].upper()
            url = config["url"]
        except KeyError as exc:
            raise ValidationError("unknown REST operation") from exc
        parsed = urlparse(url)
        if method not in {"GET", "HEAD"} or parsed.scheme not in {"http", "https"}:
            raise ValidationError("REST operation is not allowed")
        try:
            response = await self._client.request(
                method,
                url,
                params=query,
                follow_redirects=False,
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise DependencyError("REST dependency is unavailable") from exc
        if len(response.content) > self._max_result_bytes:
            raise DependencyError("REST response exceeded size limit")
        try:
            data: Any = response.json()
        except ValueError:
            data = response.text
        return ToolResult(data={"status_code": response.status_code, "body": data})
