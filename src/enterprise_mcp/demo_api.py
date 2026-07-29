"""Synthetic knowledge and REST service used by the local demo."""

from typing import Any

from fastapi import FastAPI
from pydantic import BaseModel, Field

app = FastAPI(title="Enterprise MCP Demo Service")


class SearchRequest(BaseModel):
    collection: str
    query: str
    top_k: int = Field(default=5, ge=1, le=20)


@app.get("/status")
async def status() -> dict[str, str]:
    return {"status": "operational", "service": "synthetic-enterprise-api"}


@app.post("/search")
async def search(request: SearchRequest) -> dict[str, list[dict[str, Any]]]:
    documents = [
        {
            "document_id": "security-policy",
            "title": "Enterprise Security Policy",
            "text": "Sensitive tools require explicit authorization and complete audit evidence.",
            "score": 0.93,
            "revision": "demo-v1",
        },
        {
            "document_id": "pricing-policy",
            "title": "Pricing Approval Policy",
            "text": "Pricing exceptions above the configured threshold require manager approval.",
            "score": 0.87,
            "revision": "demo-v1",
        },
    ]
    return {"results": documents[: request.top_k]}
