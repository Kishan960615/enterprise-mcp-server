"""Immutable capability registry and plugin contracts."""

from collections.abc import Awaitable, Callable, Iterable
from dataclasses import dataclass
from typing import Any, Protocol

from pydantic import BaseModel, ConfigDict, Field

from enterprise_mcp.domain import CapabilityDescriptor, InvocationContext, ToolResult

ToolHandler = Callable[[InvocationContext, dict[str, Any]], Awaitable[ToolResult]]


class PluginManifest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str
    version: str
    plugin_api_version: str = "1"
    description: str = ""
    egress_hosts: list[str] = Field(default_factory=list)


class CapabilityProvider(Protocol):
    def manifest(self) -> PluginManifest: ...

    def tools(self) -> Iterable["RegisteredTool"]: ...

    async def health(self) -> bool: ...


@dataclass(frozen=True, slots=True)
class RegisteredTool:
    descriptor: CapabilityDescriptor
    handler: ToolHandler


class CapabilityRegistry:
    """Build-once registry that rejects duplicate capability names."""

    def __init__(self) -> None:
        self._tools: dict[str, RegisteredTool] = {}
        self._sealed = False

    def register_tool(self, tool: RegisteredTool) -> None:
        if self._sealed:
            raise RuntimeError("registry is sealed")
        if tool.descriptor.name in self._tools:
            raise ValueError(f"duplicate capability: {tool.descriptor.name}")
        self._tools[tool.descriptor.name] = tool

    def seal(self) -> None:
        self._sealed = True

    def tool(self, name: str) -> RegisteredTool:
        try:
            return self._tools[name]
        except KeyError as exc:
            raise KeyError(f"unknown capability: {name}") from exc

    def tools(self) -> tuple[RegisteredTool, ...]:
        return tuple(self._tools.values())
