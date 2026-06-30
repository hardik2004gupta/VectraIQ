# Security Policy

## Supported Versions

| Version | Supported |
|---|---|
| `main` branch | ✅ Active security fixes |
| Tagged releases | ✅ Critical fixes only |
| Older branches | ❌ No support |

## Reporting a Vulnerability

**Do not open a public GitHub issue for security vulnerabilities.**

Please report security issues directly to the maintainer:

- **Email:** nikunjhardik2006@gmail.com
- **Subject line:** `[SECURITY] VectraIQ — <brief description>`

Include:
1. Description of the vulnerability
2. Steps to reproduce
3. Potential impact assessment
4. Any suggested mitigations

You will receive an acknowledgement within **48 hours** and a resolution timeline within **7 days**.

## Security Architecture

VectraIQ implements defense-in-depth across 10 layers:

1. **Pydantic field validators** — regex injection-pattern detection on all user inputs at the model layer
2. **JWT bearer authentication** — HS256 tokens with configurable TTL on all `/query` and `/admin` endpoints
3. **Per-user rate limiting** — sliding window enforced via Redis (in-memory fallback)
4. **Daily token budget** — per-user OpenAI token cap prevents abuse
5. **Input restructuring** — tiktoken-based truncation prevents context overflow
6. **LLM-Guard input scan** — PromptInjection + Toxicity scanner before LLM invocation
7. **PII redaction (input)** — redacts PII from user queries before retrieval
8. **Spotlighting** — XML-tagged retrieved context with security preamble isolates user data from system instructions
9. **Hardened system prompt** — domain restrictions and behavioral rules injected at every LLM call
10. **PII redaction (output)** — redacts PII from generated answers before returning to client

## Known Limitations

- SQL approval (`/query/sql/execute`) is not user-scoped — any authenticated user can resume any SQL thread by thread ID. This is a known issue tracked internally.
- Redis `cache.clear()` does not clear remote Upstash entries due to HTTP API limitations.
- No refresh token mechanism; expired JWTs require re-authentication.

## Security Headers

All responses include:
- `X-Content-Type-Options: nosniff`
- `X-Frame-Options: DENY`
- `Referrer-Policy: strict-origin-when-cross-origin`
- `Content-Security-Policy: default-src 'none'; connect-src 'self'; frame-ancestors 'none'`
- `Permissions-Policy: camera=(), microphone=(), geolocation=(), payment=()`

## Dependency Security

Dependencies are audited via `pip-audit` in CI on every push to `main`. See `.github/workflows/ci.yml`.
