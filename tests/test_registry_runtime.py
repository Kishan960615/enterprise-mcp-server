import pytest

from enterprise_mcp.domain import CapabilityDescriptor, CapabilityKind, Principal, RiskClass
from enterprise_mcp.registry import CapabilityRegistry, RegisteredTool
from enterprise_mcp.runtime import Runtime
from enterprise_mcp.settings import Settings


async def _handler(context, arguments):  # type: ignore[no-untyped-def]
    raise AssertionError("not invoked")


def test_registry_rejects_duplicate_capabilities() -> None:
    registry = CapabilityRegistry()
    descriptor = CapabilityDescriptor(
        name="demo.read",
        kind=CapabilityKind.TOOL,
        description="demo",
        risk=RiskClass.R1,
        permission="tool:demo.read:invoke",
    )
    registry.register_tool(RegisteredTool(descriptor, _handler))
    with pytest.raises(ValueError, match="duplicate"):
        registry.register_tool(RegisteredTool(descriptor, _handler))


@pytest.mark.asyncio
async def test_runtime_invocation_is_audited(settings: Settings) -> None:
    runtime = Runtime(settings)
    await runtime.start()
    principal = Principal(
        tenant_id="tenant-a",
        subject_id="user-a",
        permissions=frozenset({"*"}),
    )
    try:
        result = await runtime.invoke(principal, "system.capabilities", {})
        assert result.data["capabilities"]
        events = await runtime.audit.recent(principal)
        assert events[0]["outcome"] == "success"
        assert events[0]["capability_name"] == "system.capabilities"
    finally:
        await runtime.close()
