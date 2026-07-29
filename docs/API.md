# API and MCP Contracts

## MCP

Endpoint: `/mcp/`

Supported surface: initialization, tool discovery/calls, resource read, and prompt discovery/get through FastMCP.

Errors use stable internal codes: `authentication_required`, `permission_denied`, `invalid_arguments`, `dependency_unavailable`, and `result_too_large`.

## Operational API

- `GET /health/live`
- `GET /health/ready`
- `GET /api/v1/version`
- `GET /api/v1/capabilities`
- `GET /api/v1/audit/events?limit=20`
- `GET /metrics`

Production disables interactive OpenAPI documentation by default.

## Result shape

```json
{
  "data": {},
  "provenance": [{"uri": "enterprise://...", "title": "Source", "revision": "sha"}],
  "truncated": false
}
```
