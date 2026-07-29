# Implementation Plan

The repository implements the specification in vertical slices:

1. Foundation: settings, lifecycle, MCP/ASGI, health.
2. Trust: principal resolution, policy, tenant context, audit.
3. Registry: immutable descriptors and plugin provider protocol.
4. Connectors: knowledge, SQL, REST, files, GitHub.
5. Operations: metrics, Docker Compose, synthetic demo service.
6. Quality: unit, security, API, and MCP integration tests.
7. Production: OIDC transport provider, Alembic jobs, Redis limits, plugin entry-point discovery, OpenTelemetry exporter, Kubernetes.

Every capability requires schema validation, permission/risk classification, limits, audit behavior, denial tests, and documentation.
