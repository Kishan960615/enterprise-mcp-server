"""Command-line entry point."""

import argparse

import uvicorn

from enterprise_mcp.mcp_server import mcp
from enterprise_mcp.settings import get_settings


def main() -> None:
    parser = argparse.ArgumentParser(description="Enterprise MCP Server")
    parser.add_argument("--transport", choices=["http", "stdio"], default="http")
    args = parser.parse_args()
    settings = get_settings()
    if args.transport == "stdio":
        if settings.auth_mode != "development":
            raise SystemExit("stdio is only supported with explicit development authentication")
        mcp.run(transport="stdio")
        return
    uvicorn.run(
        "enterprise_mcp.app:create_app",
        factory=True,
        host=settings.host,
        port=settings.port,
    )


if __name__ == "__main__":
    main()
