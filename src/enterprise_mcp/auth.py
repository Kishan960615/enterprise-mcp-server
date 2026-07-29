"""Authentication and request principal resolution."""

from collections.abc import Mapping
from typing import Any

import httpx
import jwt
from jwt import PyJWKClient

from enterprise_mcp.domain import AuthenticationError, Principal
from enterprise_mcp.settings import Settings


class PrincipalResolver:
    """Resolve a verified principal from HTTP headers or development settings."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._jwk_client = (
            PyJWKClient(settings.oidc_jwks_url, cache_keys=True) if settings.oidc_jwks_url else None
        )

    def development_principal(self) -> Principal:
        if self._settings.auth_mode != "development":
            raise AuthenticationError("development authentication is disabled")
        return Principal(
            tenant_id=self._settings.development_tenant,
            subject_id=self._settings.development_subject,
            roles=frozenset({"developer"}),
            permissions=frozenset({"*"}),
        )

    def from_headers(self, headers: Mapping[str, str]) -> Principal:
        if self._settings.auth_mode == "development":
            return self.development_principal()
        authorization = headers.get("authorization", "")
        if not authorization.startswith("Bearer "):
            raise AuthenticationError("a bearer token is required")
        return self._decode_token(authorization.removeprefix("Bearer ").strip())

    def _decode_token(self, token: str) -> Principal:
        if not self._jwk_client:
            raise AuthenticationError("OIDC is not configured")
        try:
            signing_key = self._jwk_client.get_signing_key_from_jwt(token)
            claims: dict[str, Any] = jwt.decode(
                token,
                signing_key.key,
                algorithms=["RS256", "ES256"],
                audience=self._settings.oidc_audience,
                issuer=self._settings.oidc_issuer,
                options={"require": ["exp", "iat", "sub"]},
            )
        except (jwt.PyJWTError, httpx.HTTPError, ValueError) as exc:
            raise AuthenticationError("token validation failed") from exc
        tenant = claims.get("tenant_id")
        subject = claims.get("sub")
        if not isinstance(tenant, str) or not isinstance(subject, str):
            raise AuthenticationError("required identity claims are missing")
        roles = _string_set(claims.get("roles"))
        permissions = _string_set(claims.get("permissions"))
        return Principal(
            tenant_id=tenant,
            subject_id=subject,
            roles=frozenset(roles),
            permissions=frozenset(permissions),
        )


def _string_set(value: object) -> set[str]:
    if not isinstance(value, list):
        return set()
    return {item for item in value if isinstance(item, str)}
