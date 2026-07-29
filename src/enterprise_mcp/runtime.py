"""Application runtime, capability registration, and safe execution."""

import asyncio
import time
from typing import Any
from uuid import uuid4

import httpx
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from enterprise_mcp.connectors import (
    FileConnector,
    GitHubConnector,
    KnowledgeConnector,
    RestConnector,
    SqlConnector,
)
from enterprise_mcp.domain import (
    CapabilityDescriptor,
    CapabilityKind,
    InvocationContext,
    Principal,
    RiskClass,
    ToolResult,
)
from enterprise_mcp.persistence import AuditService, Database
from enterprise_mcp.policy import PolicyEngine
from enterprise_mcp.registry import CapabilityRegistry, RegisteredTool
from enterprise_mcp.settings import Settings


class Runtime:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.database = Database(settings.database_url)
        self.audit = AuditService(self.database.sessions)
        self.policy = PolicyEngine()
        self.registry = CapabilityRegistry()
        self.http = httpx.AsyncClient(timeout=settings.tool_timeout_seconds)
        sql_engines: dict[str, AsyncEngine] = {}
        if settings.database_url.startswith("postgresql"):
            sql_engines["default"] = create_async_engine(settings.database_url, pool_pre_ping=True)
        self.knowledge = KnowledgeConnector(settings.knowledge_base_url, self.http)
        self.files = FileConnector(settings.file_roots, settings.max_result_bytes)
        self.rest = RestConnector(settings.rest_operations, self.http, settings.max_result_bytes)
        self.github = GitHubConnector(
            settings.github_token, settings.github_allowed_repositories, self.http
        )
        self.sql = SqlConnector(sql_engines, settings.max_sql_rows)
        self._sql_engines = sql_engines
        self._register_tools()
        self.registry.seal()

    async def start(self) -> None:
        await self.database.create_schema()

    async def close(self) -> None:
        await self.http.aclose()
        for engine in self._sql_engines.values():
            await engine.dispose()
        await self.database.close()

    async def invoke(
        self,
        principal: Principal,
        name: str,
        arguments: dict[str, Any],
    ) -> ToolResult:
        registered = self.registry.tool(name)
        request_id = str(uuid4())
        self.policy.require(principal, registered.descriptor)
        context = InvocationContext(
            request_id=request_id,
            principal=principal,
            deadline_seconds=self.settings.tool_timeout_seconds,
        )
        started = time.perf_counter()
        try:
            result = await asyncio.wait_for(
                registered.handler(context, arguments),
                timeout=self.settings.tool_timeout_seconds,
            )
        except Exception:
            await self.audit.record(
                principal=principal,
                request_id=request_id,
                event_type="tool.invocation",
                outcome="error",
                capability_name=name,
                arguments=arguments,
                duration_ms=int((time.perf_counter() - started) * 1000),
            )
            raise
        await self.audit.record(
            principal=principal,
            request_id=request_id,
            event_type="tool.invocation",
            outcome="success",
            capability_name=name,
            arguments=arguments,
            duration_ms=int((time.perf_counter() - started) * 1000),
        )
        return result

    def authorized_capabilities(self, principal: Principal) -> list[dict[str, str]]:
        capabilities: list[dict[str, str]] = []
        for tool in self.registry.tools():
            decision = self.policy.authorize(principal, tool.descriptor)
            if decision.decision.value == "allow":
                capabilities.append(
                    {
                        "name": tool.descriptor.name,
                        "description": tool.descriptor.description,
                        "risk": tool.descriptor.risk.value,
                    }
                )
        return capabilities

    def _register_tools(self) -> None:
        self._add("system.capabilities", "List authorized capabilities", RiskClass.R0, self._caps)
        self._add("knowledge.search", "Search enterprise knowledge", RiskClass.R1, self._knowledge)
        self._add("files.search", "Search an approved file root", RiskClass.R1, self._files_search)
        self._add("files.read", "Read a confined text file", RiskClass.R1, self._files_read)
        self._add("rest.request", "Invoke an allowlisted REST operation", RiskClass.R2, self._rest)
        self._add("sql.query", "Run a bounded read-only SQL query", RiskClass.R2, self._sql)
        self._add(
            "github.get_file",
            "Read a file from an allowlisted repository",
            RiskClass.R1,
            self._github,
        )

    def _add(self, name: str, description: str, risk: RiskClass, handler: Any) -> None:
        self.registry.register_tool(
            RegisteredTool(
                descriptor=CapabilityDescriptor(
                    name=name,
                    kind=CapabilityKind.TOOL,
                    description=description,
                    risk=risk,
                    permission=f"tool:{name}:invoke",
                ),
                handler=handler,
            )
        )

    async def _caps(self, context: InvocationContext, arguments: dict[str, Any]) -> ToolResult:
        return ToolResult(data={"capabilities": self.authorized_capabilities(context.principal)})

    async def _knowledge(self, context: InvocationContext, arguments: dict[str, Any]) -> ToolResult:
        return await self.knowledge.search(
            str(arguments["collection"]),
            str(arguments["query"]),
            int(arguments.get("top_k", 5)),
        )

    async def _files_search(
        self, context: InvocationContext, arguments: dict[str, Any]
    ) -> ToolResult:
        return await self.files.search(
            str(arguments["root"]), str(arguments["query"]), int(arguments.get("limit", 20))
        )

    async def _files_read(
        self, context: InvocationContext, arguments: dict[str, Any]
    ) -> ToolResult:
        return await self.files.read(
            str(arguments["root"]),
            str(arguments["path"]),
            int(arguments.get("start_line", 1)),
            int(arguments.get("end_line", 200)),
        )

    async def _rest(self, context: InvocationContext, arguments: dict[str, Any]) -> ToolResult:
        query = arguments.get("query")
        return await self.rest.request(
            str(arguments["operation"]),
            query if isinstance(query, dict) else None,
        )

    async def _sql(self, context: InvocationContext, arguments: dict[str, Any]) -> ToolResult:
        parameters = arguments.get("parameters")
        return await self.sql.query(
            str(arguments["connection"]),
            str(arguments["query"]),
            parameters if isinstance(parameters, dict) else None,
            int(arguments.get("max_rows", 100)),
        )

    async def _github(self, context: InvocationContext, arguments: dict[str, Any]) -> ToolResult:
        return await self.github.get_file(
            str(arguments["owner"]),
            str(arguments["repository"]),
            str(arguments["path"]),
            str(arguments.get("ref", "main")),
        )
