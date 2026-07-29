import pytest
from pydantic import ValidationError as PydanticValidationError

from enterprise_mcp.domain import (
    CapabilityDescriptor,
    CapabilityKind,
    Decision,
    Principal,
    RiskClass,
)
from enterprise_mcp.policy import PolicyEngine
from enterprise_mcp.settings import Settings


def test_production_rejects_development_authentication() -> None:
    with pytest.raises(PydanticValidationError):
        Settings(environment="production", auth_mode="development")


def test_policy_denies_missing_permission() -> None:
    principal = Principal(tenant_id="a", subject_id="u")
    capability = CapabilityDescriptor(
        name="files.read",
        kind=CapabilityKind.TOOL,
        description="read",
        risk=RiskClass.R1,
        permission="tool:files.read:invoke",
    )
    assert PolicyEngine().authorize(principal, capability).decision is Decision.DENY


def test_policy_requires_approval_for_sensitive_capability() -> None:
    principal = Principal(
        tenant_id="a",
        subject_id="u",
        permissions=frozenset({"tool:email.send:invoke"}),
    )
    capability = CapabilityDescriptor(
        name="email.send",
        kind=CapabilityKind.TOOL,
        description="send",
        risk=RiskClass.R3,
        permission="tool:email.send:invoke",
    )
    assert PolicyEngine().authorize(principal, capability).decision is Decision.APPROVAL
