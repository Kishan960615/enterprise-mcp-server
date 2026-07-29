"""Framework-independent domain models and errors."""

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class RiskClass(StrEnum):
    R0 = "R0"
    R1 = "R1"
    R2 = "R2"
    R3 = "R3"
    R4 = "R4"


class Decision(StrEnum):
    ALLOW = "allow"
    DENY = "deny"
    APPROVAL = "approval"


class CapabilityKind(StrEnum):
    TOOL = "tool"
    RESOURCE = "resource"
    PROMPT = "prompt"


class Principal(BaseModel):
    model_config = ConfigDict(frozen=True)

    tenant_id: str
    subject_id: str
    roles: frozenset[str] = frozenset()
    permissions: frozenset[str] = frozenset()
    attributes: dict[str, str] = Field(default_factory=dict)


class CapabilityDescriptor(BaseModel):
    model_config = ConfigDict(frozen=True)

    name: str
    kind: CapabilityKind
    description: str
    risk: RiskClass
    permission: str
    connector: str | None = None


class Provenance(BaseModel):
    uri: str
    title: str
    revision: str | None = None


class ToolResult(BaseModel):
    data: Any
    provenance: list[Provenance] = Field(default_factory=list)
    truncated: bool = False


@dataclass(frozen=True, slots=True)
class InvocationContext:
    request_id: str
    principal: Principal
    deadline_seconds: float
    metadata: dict[str, str] = field(default_factory=dict)


class EnterpriseMcpError(Exception):
    code = "internal_error"


class AuthenticationError(EnterpriseMcpError):
    code = "authentication_required"


class AuthorizationError(EnterpriseMcpError):
    code = "permission_denied"


class ValidationError(EnterpriseMcpError):
    code = "invalid_arguments"


class DependencyError(EnterpriseMcpError):
    code = "dependency_unavailable"


class ResultLimitError(EnterpriseMcpError):
    code = "result_too_large"
