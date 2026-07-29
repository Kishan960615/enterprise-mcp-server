"""Read-only GitHub connector."""

from typing import Any

import httpx

from enterprise_mcp.domain import DependencyError, Provenance, ToolResult, ValidationError


class GitHubConnector:
    def __init__(
        self,
        token: str | None,
        allowed_repositories: list[str],
        client: httpx.AsyncClient,
    ) -> None:
        self._token = token
        self._allowed = set(allowed_repositories)
        self._client = client

    def _require_repository(self, owner: str, repository: str) -> str:
        full_name = f"{owner}/{repository}"
        if full_name not in self._allowed:
            raise ValidationError("repository is not allowlisted")
        return full_name

    async def get_file(
        self,
        owner: str,
        repository: str,
        path: str,
        ref: str = "main",
    ) -> ToolResult:
        self._require_repository(owner, repository)
        headers = {"Accept": "application/vnd.github.raw+json"}
        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"
        url = f"https://api.github.com/repos/{owner}/{repository}/contents/{path}"
        try:
            response = await self._client.get(url, headers=headers, params={"ref": ref})
            response.raise_for_status()
            content = response.text
            metadata_response = await self._client.get(
                url,
                headers={**headers, "Accept": "application/vnd.github+json"},
                params={"ref": ref},
            )
            metadata_response.raise_for_status()
            metadata: dict[str, Any] = metadata_response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise DependencyError("GitHub is unavailable") from exc
        sha = str(metadata.get("sha", ref))
        return ToolResult(
            data={"content": content, "path": path, "sha": sha},
            provenance=[
                Provenance(
                    uri=f"enterprise://github/{owner}/{repository}/blob/{sha}/{path}",
                    title=f"{owner}/{repository}:{path}",
                    revision=sha,
                )
            ],
        )
