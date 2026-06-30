# SECURITY_HARDENING_REPORT.md — VectraIQ Phase 5

**Date:** 2026-06-30

---

## Security Architecture

VectraIQ implements 10 ordered security layers on every `/query` request:

```
Request
  │
  1. Pydantic field_validator (injection regex patterns)
  2. JWT bearer authentication
  3. Per-user sliding-window rate limit (Redis)
  4. Daily token budget (Redis)
  5. Input restructuring (tiktoken truncation)
  6. LLM-Guard: PromptInjection + Toxicity scanner
  7. PII redaction on input
  8. Spotlighting (XML-tagged retrieved context + security preamble)
  9. Hardened system prompt (domain restrictions + behavioral rules)
  10. PII redaction on output
  │
Response
```

---

## Phase 5 Changes

### SH-001 · Security headers middleware added

**File:** `vectraiq/middleware/security_headers.py`  
**Registered in:** `vectraiq/main.py`

All responses now include:

```
X-Content-Type-Options: nosniff
X-Frame-Options: DENY
Referrer-Policy: strict-origin-when-cross-origin
Permissions-Policy: camera=(), microphone=(), geolocation=(), payment=()
Content-Security-Policy: default-src 'none'; connect-src 'self'; frame-ancestors 'none'
```

The `Server` header (set by uvicorn, reveals server identity) is stripped.

**Rationale:** These headers address OWASP A05 (Security Misconfiguration) — specifically clickjacking, MIME sniffing, and information disclosure via server headers.

---

## OWASP Top 10 Assessment

| OWASP Risk | Status | Implementation |
|---|---|---|
| A01 Broken Access Control | ✅ Mitigated | JWT on all protected endpoints; `require_admin` dependency for admin routes |
| A02 Cryptographic Failures | ✅ Mitigated | bcrypt (12 rounds) for passwords; HS256 JWT with configurable secret |
| A03 Injection | ✅ Mitigated | Pydantic validators block known injection patterns; parameterized SQL queries; LLM-Guard PromptInjection scanner |
| A04 Insecure Design | ⚠️ Partial | SQL approval not user-scoped (known issue); no PKCE OAuth flow |
| A05 Security Misconfiguration | ✅ Mitigated | Security headers added; CORS restricted to `frontend_origins`; no wildcard origins |
| A06 Vulnerable Components | ✅ Monitored | `pip-audit` in CI on every push to main |
| A07 Auth Failures | ✅ Mitigated | Rate limiting on `/auth/login` (5/min); no username enumeration (generic "Invalid username or password") |
| A08 Software Integrity | ✅ Mitigated | `uv.lock` pins all dependency versions; Docker base image is pinned |
| A09 Logging Failures | ✅ Mitigated | Structured logging on all security events; request IDs for correlation |
| A10 SSRF | ✅ Mitigated | External HTTP calls only to configured endpoints (Qdrant, OpenAI, Upstash, Tavily); no user-controlled URL construction |

---

## OWASP LLM Top 10 Assessment

| OWASP LLM Risk | Status | Implementation |
|---|---|---|
| LLM01 Prompt Injection | ✅ Layered defense | Pydantic validators → LLM-Guard PromptInjection → Spotlighting → hardened system prompt |
| LLM02 Insecure Output Handling | ✅ Mitigated | Output PII redaction; answers are strings (no exec/eval of model output) |
| LLM03 Training Data Poisoning | N/A | Model is OpenAI-hosted; VectraIQ does not fine-tune |
| LLM04 Model Denial of Service | ✅ Mitigated | Daily token budget per user; input token limit (tiktoken truncation); rate limiting |
| LLM05 Supply Chain | ✅ Monitored | pip-audit in CI |
| LLM06 Sensitive Info Disclosure | ✅ Mitigated | PII redaction (input + output); domain-restricted system prompt |
| LLM07 Insecure Plugin Design | N/A | No LLM plugins; tools are controlled Pydantic functions |
| LLM08 Excessive Agency | ✅ Mitigated | SQL requires human approval before execution; read-only SQL enforced by prompt |
| LLM09 Overreliance | ✅ Addressed | Confidence scores returned; sources cited; disclaimer in system prompt |
| LLM10 Model Theft | N/A | Using OpenAI API; model weights not accessible |

---

## Known Security Issues

### SEC-001 · SQL approval not user-scoped (Medium)

**Endpoint:** `POST /query/sql/execute`  
**Issue:** Any authenticated user can resume any SQL thread by passing any `query_id` (LangGraph thread ID). There is no validation that the requesting user owns the thread.  
**Impact:** A user could approve another user's pending SQL query.  
**Recommended fix:** Store `{thread_id: user_id}` in Redis when the interrupt occurs. Verify on `/query/sql/execute` that `body.query_id` is owned by the requesting user.  
**Status:** Open — not fixed in Phase 5 (requires LangGraph session metadata changes).

---

## JWT Configuration Recommendations

| Setting | Current | Recommended for production |
|---|---|---|
| Algorithm | HS256 | RS256 (asymmetric) for multi-service deployments |
| Secret length | Configurable | Minimum 64 random bytes |
| Expiry | 60 min (configurable) | 15 min access + 7 day refresh |
| `JWT_SECRET` rotation | Manual | Rotate every 90 days; use secret manager (AWS Secrets Manager, Vault) |

---

## Secrets Management

**Current:** All secrets are environment variables read by `pydantic-settings`.  
**Recommended for production:**

1. Never commit `.env` files — `.env` is in `.gitignore`
2. Use Railway / Vercel environment variable dashboards for deployment
3. For self-hosted: use [Doppler](https://doppler.com) or [AWS Secrets Manager](https://aws.amazon.com/secrets-manager/)
4. `JWT_SECRET` must be at least 32 characters; use a secrets manager to generate and rotate it

---

## Dependency Audit

Run manually:
```bash
uv run pip-audit --requirement <(uv export --no-hashes)
```

Runs automatically in CI (`.github/workflows/ci.yml` `security-scan` job).

Frontend:
```bash
cd frontend && npm audit --audit-level=high
```

---

## Penetration Testing Checklist

Before public launch, perform manual testing of:

- [ ] JWT token manipulation (algorithm confusion, none algorithm)
- [ ] Rate limit bypass via IP rotation / X-Forwarded-For header forgery
- [ ] SQL injection in direct API calls (bypassing Pydantic layer)
- [ ] SSRF via crafted question text
- [ ] Prompt injection via uploaded documents (once `/documents/upload` is implemented)
- [ ] Insecure direct object reference on `/query/sql/execute` (known SEC-001)
- [ ] Admin endpoint access by guessing admin token claims
