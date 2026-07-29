"""Enterprise RAG Platform connector."""

from typing import Any

import httpx

from enterprise_mcp.domain import DependencyError, Provenance, ToolResult


class KnowledgeConnector:
    def __init__(self, base_url: str | None, client: httpx.AsyncClient) -> None:
        self._base_url = base_url.rstrip("/") if base_url else None
        self._client = client

    async def search(
        self,
        collection: str,
        query: str,
        top_k: int = 5,
    ) -> ToolResult:
        if not self._base_url:
            return ToolResult(
                data={
                    "results": [
                        {
                            "text": "The demo knowledge base is operating in offline mode.",
                            "score": 1.0,
                            "document_id": "offline-demo",
                        }
                    ]
                },
                provenance=[
                    Provenance(
                        uri=f"enterprise://knowledge/{collection}/documents/offline-demo",
                        title="Offline demo document",
                        revision="demo-v1",
                    )
                ],
            )
        try:
            response = await self._client.post(
                f"{self._base_url}/search",
                json={"collection": collection, "query": query, "top_k": min(top_k, 20)},
            )
            response.raise_for_status()
            payload: dict[str, Any] = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise DependencyError("knowledge service is unavailable") from exc
        results = payload.get("results", [])
        provenance = [
            Provenance(
                uri=f"enterprise://knowledge/{collection}/documents/{item.get('document_id')}",
                title=str(item.get("title", "Knowledge document")),
                revision=item.get("revision"),
            )
            for item in results
            if isinstance(item, dict) and item.get("document_id")
        ]
        return ToolResult(data={"results": results}, provenance=provenance)
