from importlib.metadata import EntryPoint

import pytest

from enterprise_mcp.domain import (
    CapabilityDescriptor,
    CapabilityKind,
    InvocationContext,
    RiskClass,
    ToolResult,
)
from enterprise_mcp.plugins import PluginManager
from enterprise_mcp.registry import CapabilityRegistry, PluginManifest, RegisteredTool


class DemoProvider:
    def manifest(self) -> PluginManifest:
        return PluginManifest(name="demo", version="1.0.0")

    def tools(self) -> tuple[RegisteredTool, ...]:
        async def echo(context: InvocationContext, arguments: dict[str, object]) -> ToolResult:
            return ToolResult(data=arguments)

        return (
            RegisteredTool(
                CapabilityDescriptor(
                    name="demo.echo",
                    kind=CapabilityKind.TOOL,
                    description="Echo",
                    risk=RiskClass.R0,
                    permission="tool:demo.echo:invoke",
                ),
                echo,
            ),
        )

    async def health(self) -> bool:
        return True


def create_demo_provider() -> DemoProvider:
    return DemoProvider()


@pytest.mark.asyncio
async def test_plugin_manager_registers_allowlisted_provider() -> None:
    entry_point = EntryPoint(
        name="demo",
        value="test_plugins:create_demo_provider",
        group="enterprise_mcp.plugins",
    )
    registry = CapabilityRegistry()
    loaded = await PluginManager(frozenset({"demo"})).load_into(registry, (entry_point,))
    assert loaded[0]["name"] == "demo"
    assert registry.tool("demo.echo").descriptor.risk is RiskClass.R0
