# Security Design

The server treats clients, tool arguments, retrieved content, downstream responses, and plugins as untrusted.

## Controls

- exact issuer/audience/algorithm token validation;
- caller-independent tenant derivation;
- default-deny permission checks;
- no arbitrary SQL, URLs, paths, or GitHub repositories;
- bounded time, concurrency, rows, files, and results;
- no raw arguments in audit records;
- development authentication rejected in production;
- non-root, read-only-compatible container.

## Required production work

Wire the selected FastMCP OIDC provider into Streamable HTTP, store connector credentials in a secret manager, deploy PostgreSQL migrations separately, restrict network egress, and forward telemetry/audit records to managed backends.
