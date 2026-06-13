# Security Policy

## Supported versions

pixbridge is pre-1.0. Security fixes are applied to the latest released
version on the `main` branch only.

## Reporting a vulnerability

Please **do not** open a public issue for security vulnerabilities.

Instead, report privately via
[GitHub's private vulnerability reporting](https://github.com/jdinkla/pixbridge/security/advisories/new),
or by email to **joern@dinkla.net**.

Include a description, affected version, reproduction steps, and impact. You can
expect an acknowledgement within a few business days. Once a fix is available,
the advisory will be published with appropriate credit.

## Scope and handling of secrets

This library calls third-party provider APIs (Gemini, OpenAI, xAI) using API
keys supplied via environment variables. Keys are never written to disk or
logged by pixbridge. When reporting issues, **never include real API keys** in
issues, PRs, or reproduction steps — redact them.
