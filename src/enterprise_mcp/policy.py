"""Default-deny authorization policy."""

from dataclasses import dataclass

from enterprise_mcp.domain import (
    AuthorizationError,
    CapabilityDescriptor,
    Decision,
    Principal,
    RiskClass,
)


@dataclass(frozen=True, slots=True)
class PolicyDecision:
    decision: Decision
    reason: str


class PolicyEngine:
    """Small built-in policy engine; replaceable with OPA/Cedar adapters later."""

    def authorize(
        self,
        principal: Principal,
        capability: CapabilityDescriptor,
    ) -> PolicyDecision:
        permission = capability.permission
        if "*" not in principal.permissions and permission not in principal.permissions:
            return PolicyDecision(Decision.DENY, "missing required permission")
        if capability.risk in {RiskClass.R3, RiskClass.R4}:
            return PolicyDecision(Decision.APPROVAL, "sensitive capability requires approval")
        return PolicyDecision(Decision.ALLOW, "permission granted")

    def require(
        self,
        principal: Principal,
        capability: CapabilityDescriptor,
    ) -> PolicyDecision:
        decision = self.authorize(principal, capability)
        if decision.decision is Decision.DENY:
            raise AuthorizationError(decision.reason)
        if decision.decision is Decision.APPROVAL:
            raise AuthorizationError("approval_required")
        return decision
