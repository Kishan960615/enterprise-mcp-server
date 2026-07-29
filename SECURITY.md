# Security Policy

## Supported versions

Only the latest release receives security fixes while the project is pre-1.0.

## Reporting

Do not disclose vulnerabilities in a public issue. Use GitHub private vulnerability reporting when the repository is published.

## Design boundaries

- Production requires OIDC and PostgreSQL.
- Built-in integrations are read-only.
- SQL accepts one parsed SELECT statement and applies an outer row limit.
- REST calls use named preconfigured operations; callers cannot provide URLs.
- Files must resolve under a configured root.
- GitHub repositories must be explicitly allowlisted.
- Audit records contain input fingerprints and bounded metadata, not credentials.

See `docs/SECURITY_DESIGN.md` for the threat model and test requirements.
