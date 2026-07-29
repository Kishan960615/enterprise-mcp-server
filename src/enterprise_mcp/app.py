"""ASGI application factory with MCP and operational endpoints."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest
from starlette.responses import Response

from enterprise_mcp import __version__
from enterprise_mcp.auth import PrincipalResolver
from enterprise_mcp.domain import AuthenticationError, EnterpriseMcpError, Principal
from enterprise_mcp.mcp_server import configure, mcp
from enterprise_mcp.runtime import Runtime
from enterprise_mcp.settings import Settings, get_settings

REQUESTS = Counter("enterprise_mcp_http_requests_total", "HTTP requests", ["path", "status"])
LATENCY = Histogram("enterprise_mcp_http_duration_seconds", "HTTP latency", ["path"])


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    runtime = Runtime(settings)
    resolver = PrincipalResolver(settings)
    configure(runtime, resolver)
    mcp_app = mcp.http_app(path="/")

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        await runtime.start()
        app.state.ready = True
        async with mcp_app.lifespan(mcp_app):
            yield
        app.state.ready = False
        await runtime.close()

    app = FastAPI(
        title="Enterprise MCP Server",
        version=__version__,
        lifespan=lifespan,
        docs_url="/docs" if settings.environment != "production" else None,
    )
    app.state.ready = False
    app.state.runtime = runtime
    app.state.resolver = resolver

    @app.middleware("http")
    async def metrics_middleware(request: Request, call_next: Any) -> Response:
        with LATENCY.labels(path=request.url.path).time():
            response: Response = await call_next(request)
        REQUESTS.labels(path=request.url.path, status=str(response.status_code)).inc()
        return response

    @app.exception_handler(EnterpriseMcpError)
    async def enterprise_error(request: Request, exc: EnterpriseMcpError) -> JSONResponse:
        return JSONResponse(
            status_code=403 if exc.code == "permission_denied" else 400,
            content={
                "code": exc.code,
                "message": str(exc),
                "correlation_id": request.headers.get("x-request-id", "unavailable"),
            },
        )

    def principal(
        request: Request,
        authorization: str | None = Header(default=None),
    ) -> Principal:
        headers = dict(request.headers)
        if authorization:
            headers["authorization"] = authorization
        try:
            return resolver.from_headers(headers)
        except AuthenticationError as exc:
            raise HTTPException(status_code=401, detail=str(exc)) from exc

    @app.get("/health/live")
    async def live() -> dict[str, str]:
        return {"status": "alive"}

    @app.get("/health/ready")
    async def ready(request: Request) -> JSONResponse:
        status = bool(request.app.state.ready)
        return JSONResponse(
            status_code=200 if status else 503,
            content={"status": "ready" if status else "not_ready"},
        )

    @app.get("/api/v1/version")
    async def version() -> dict[str, str]:
        return {"name": "enterprise-mcp-server", "version": __version__}

    @app.get("/api/v1/capabilities")
    async def capabilities(user: Principal = Depends(principal)) -> dict[str, Any]:
        return {"capabilities": runtime.authorized_capabilities(user)}

    @app.get("/api/v1/audit/events")
    async def audit_events(
        limit: int = 20,
        user: Principal = Depends(principal),
    ) -> dict[str, Any]:
        return {"events": await runtime.audit.recent(user, limit)}

    @app.get("/metrics", include_in_schema=False)
    async def metrics() -> Response:
        return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

    app.mount("/mcp", mcp_app)
    return app
