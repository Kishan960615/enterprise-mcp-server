from pathlib import Path

import httpx
import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from enterprise_mcp.connectors.files import FileConnector
from enterprise_mcp.connectors.github import GitHubConnector
from enterprise_mcp.connectors.knowledge import KnowledgeConnector
from enterprise_mcp.connectors.rest import RestConnector
from enterprise_mcp.connectors.sql import SqlConnector
from enterprise_mcp.domain import ValidationError


@pytest.mark.asyncio
async def test_file_read_is_confined(tmp_path: Path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    (root / "safe.txt").write_text("safe", encoding="utf-8")
    outside = tmp_path / "secret.txt"
    outside.write_text("secret", encoding="utf-8")
    connector = FileConnector({"demo": root}, 1024)

    result = await connector.read("demo", "safe.txt")
    assert result.data["content"] == "safe"

    with pytest.raises(ValidationError, match="escapes"):
        await connector.read("demo", "../secret.txt")


@pytest.mark.asyncio
async def test_file_search_returns_bounded_matches(tmp_path: Path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    (root / "policy-one.md").write_text("one", encoding="utf-8")
    (root / "other.md").write_text("two", encoding="utf-8")
    connector = FileConnector({"demo": root}, 1024)
    result = await connector.search("demo", "policy", limit=1)
    assert result.data["matches"] == [{"path": "policy-one.md", "name": "policy-one.md"}]


@pytest.mark.parametrize(
    "query",
    [
        "DELETE FROM invoices",
        "UPDATE invoices SET amount = 0",
        "CREATE TABLE bad(id int)",
        "SELECT 1; SELECT 2",
    ],
)
def test_sql_validator_rejects_unsafe_statements(query: str) -> None:
    with pytest.raises(ValidationError):
        SqlConnector.validate(query)


def test_sql_validator_accepts_select() -> None:
    SqlConnector.validate("SELECT id, amount FROM invoices WHERE amount > :minimum")


@pytest.mark.asyncio
async def test_sql_connector_executes_bounded_select(tmp_path: Path) -> None:
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'sql.db'}")
    async with engine.begin() as connection:
        await connection.execute(text("CREATE TABLE invoices(id INTEGER, amount INTEGER)"))
        await connection.execute(text("INSERT INTO invoices VALUES (1, 10), (2, 20)"))
    connector = SqlConnector({"demo": engine}, max_rows=1)
    try:
        result = await connector.query("demo", "SELECT * FROM invoices", max_rows=10)
        assert result.data["row_count"] == 1
        assert result.truncated is True
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_rest_connector_uses_named_operation_only() -> None:
    transport = httpx.MockTransport(
        lambda request: httpx.Response(200, json={"ok": True}, request=request)
    )
    async with httpx.AsyncClient(transport=transport) as client:
        connector = RestConnector(
            {"status": {"method": "GET", "url": "https://example.test/status"}},
            client,
            1024,
        )
        result = await connector.request("status")
        assert result.data["body"] == {"ok": True}
        with pytest.raises(ValidationError, match="unknown"):
            await connector.request("arbitrary")


@pytest.mark.asyncio
async def test_knowledge_connector_returns_citations() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "results": [
                    {
                        "document_id": "doc-1",
                        "title": "Policy",
                        "text": "Evidence",
                        "revision": "v1",
                    }
                ]
            },
            request=request,
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await KnowledgeConnector("https://kb.test", client).search("policies", "access")
    assert result.provenance[0].uri.endswith("/doc-1")


@pytest.mark.asyncio
async def test_github_connector_enforces_allowlist_and_returns_revision() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.headers["accept"] == "application/vnd.github.raw+json":
            return httpx.Response(200, text="# README", request=request)
        return httpx.Response(200, json={"sha": "abc123"}, request=request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        connector = GitHubConnector(None, ["acme/repo"], client)
        result = await connector.get_file("acme", "repo", "README.md")
        assert result.data["sha"] == "abc123"
        with pytest.raises(ValidationError, match="allowlisted"):
            await connector.get_file("other", "repo", "README.md")
