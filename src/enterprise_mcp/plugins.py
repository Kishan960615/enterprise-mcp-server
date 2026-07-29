"""Trusted build-time plugin discovery."""

from importlib.metadata import EntryPoint, entry_points
from typing import Any

from enterprise_mcp.registry import CapabilityProvider, CapabilityRegistry

PLUGIN_GROUP = "enterprise_mcp.plugins"
PLUGIN_API_VERSION = "1"


class PluginManager:
    """Load allowlisted plugin entry points and register them atomically at startup."""

    def __init__(self, allowed_plugins: frozenset[str] | None = None) -> None:
        self._allowed_plugins = allowed_plugins

    def discover(self) -> tuple[EntryPoint, ...]:
        return tuple(entry_points(group=PLUGIN_GROUP))

    async def load_into(
        self,
        registry: CapabilityRegistry,
        discovered: tuple[EntryPoint, ...] | None = None,
    ) -> list[dict[str, Any]]:
        loaded: list[dict[str, Any]] = []
        for entry_point in discovered if discovered is not None else self.discover():
            if self._allowed_plugins is not None and entry_point.name not in self._allowed_plugins:
                continue
            factory = entry_point.load()
            provider: CapabilityProvider = factory()
            manifest = provider.manifest()
            if manifest.plugin_api_version != PLUGIN_API_VERSION:
                raise ValueError(
                    f"plugin {manifest.name!r} requires unsupported API "
                    f"{manifest.plugin_api_version!r}"
                )
            if not await provider.health():
                raise RuntimeError(f"plugin {manifest.name!r} failed its health check")
            for tool in provider.tools():
                registry.register_tool(tool)
            loaded.append(
                {
                    "name": manifest.name,
                    "version": manifest.version,
                    "entry_point": entry_point.name,
                }
            )
        return loaded
