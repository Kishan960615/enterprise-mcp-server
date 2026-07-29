import pytest

from enterprise_mcp.auth import PrincipalResolver
from enterprise_mcp.mcp_server import (
    configure,
    files_read,
    knowledge_answer,
    knowledge_search,
    sql_analyst,
    system_capabilities,
    tool_catalog,
)
from enterprise_mcp.runtime import Runtime
from enterprise_mcp.settings import Settings


def _function(component):
    return getattr(component, "fn", component)


def test_development_principal_is_explicit(settings: Settings) -> None:
    principal = PrincipalResolver(settings).development_principal()
    assert principal.tenant_id == "tenant-a"
    assert principal.permissions == frozenset({"*"})


@pytest.mark.asyncio
async def test_mcp_tool_wrappers_use_runtime(settings: Settings) -> None:
    runtime = Runtime(settings)
    await runtime.start()
    configure(runtime, PrincipalResolver(settings))
    try:
        capabilities = await _function(system_capabilities)()
        assert capabilities["data"]["capabilities"]
        knowledge = await _function(knowledge_search)("demo", "policy")
        assert knowledge["provenance"]
        file_result = await _function(files_read)("demo", "policy.md")
        assert "Least privilege" in file_result["data"]["content"]
        catalog = await _function(tool_catalog)()
        assert catalog["capabilities"]
    finally:
        await runtime.close()


def test_prompts_preserve_scope_and_safety() -> None:
    assert "Cite every material claim" in _function(knowledge_answer)("What?", "policies")
    assert "never request writes" in _function(sql_analyst)("Total invoices", "finance")
