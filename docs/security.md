# Security: Threats, Controls and Known Gaps

> AEGIS handles security data, so it must be secure itself. This page lists what we defend against, how, and what is not done yet.
> Login and roles in depth: [auth.md](auth.md).

## 1. Threat model (who might attack, and how)

| # | Threat | Example | Main controls |
|---|---|---|---|
| T1 | Password guessing | Bot tries thousands of passwords | Argon2id, rate limits, identical errors/timing, AUTH-001 on AEGIS's own logins |
| T2 | Stolen token | Token copied from a laptop | 30-min expiry, active-user check every request, no third-party scripts, strict CSP |
| T3 | Leaked API key | Key pushed to a public repo | Keys can only *send* events; revocable; stored hashed; `last_used_at` visible |
| T4 | Privilege escalation | Analyst calls admin endpoints directly | Role checks on whole routers in the backend; tests for 403 |
| T5 | Bad or huge input | `"outcome":"banana"`, 100 MB payload | Pydantic validation, 8 KB `details` limit, length limits |
| T6 | Event flood / poisoning | Broken sender sends 1M events | 1200/min per sender rate limit; idempotent `event_id` |
| T7 | Tampering with history | Someone edits the audit log | PostgreSQL trigger blocks UPDATE/DELETE |
| T8 | Leaking secrets | DB password committed to Git | `.env` git-ignored; `.env.example` placeholders; `.dockerignore`; secrets via environment |
| T9 | Information leaks | Error pages show stack traces / DB address | Generic error messages; `/health/ready` hides error text; no headers/bodies in logs |
| T10 | Cross-site attacks | Evil site calls the API with the user's credentials | CORS allows only the dashboard's address; token sent in a header, not a cookie |
| T11 | Clickjacking / MIME tricks | Dashboard framed by an evil page | `X-Frame-Options: DENY`, `X-Content-Type-Options: nosniff`, CSP |

## 2. Controls by layer

- **Input:** every request body and query parameter has a Pydantic type and limits. Unknown values → 422.
- **Identity:** Argon2id passwords, signed JWT with fixed algorithm/issuer/audience, hashed API keys ([auth.md](auth.md)).
- **Access:** `any_user` / `admin_only` attached at router level. The frontend hides buttons, but **the backend decides**.
- **Abuse:** sliding-window rate limits (Redis-backed, shared across API copies).
- **Integrity:** foreign keys keep evidence from vanishing; transactions make changes all-or-nothing; the audit log is append-only in the database.
- **Secrets:** environment variables only. `JWT_SECRET` must be 32+ characters or the app refuses to issue tokens.
- **Transport:** in production, HTTPS everywhere (Cloud Run and Vercel provide it). `--proxy-headers` makes logs and rate limits see the real client IP behind the load balancer.
- **Containers:** the API runs as a non-root user; images contain no `.env`.
- **Logs:** JSON, with request IDs; never request headers or bodies (they hold tokens and passwords). Password changes are audited as `"changed"`, never the value.
- **Dependencies:** exact versions in `frontend/package-lock.json` and a pinned `scikit-learn`; `npm install` reported 0 known vulnerabilities.

## 3. If a secret leaks: what to do

1. **Rotate it first:**
   - DB password → change it in Neon;
   - `JWT_SECRET` → set a new value, which logs everyone out;
   - API key → revoke it on the Admin page.
2. Then remove it from the code. **Deleting the file is not enough:** Git history still has it. Rotation is what actually protects you.
3. Check the audit log and `last_used_at` for use during the exposure window.

## 4. Known gaps (honest list)

| Gap | Risk | Planned fix |
|---|---|---|
| Token in `sessionStorage` | A successful XSS could read it | httpOnly cookie + CSRF token |
| No refresh tokens / MFA | Users re-login every 30 min; a phished password is enough | Refresh-token rotation; TOTP or SSO (OIDC) |
| In-memory rate-limit fallback | Per process only when Redis is down | Documented; alert on fallback |
| Synchronous detection | A flood of events slows responses | Queue + worker |
| Dedup race | Two simultaneous requests could create two detections | Unique constraint or row lock |
| `/metrics` unauthenticated | Exposes operational numbers | Keep internal / behind auth in production |
| No automated dependency/SAST scanning yet | Known-vulnerable packages could slip in | Dependabot + `pip-audit` + CodeQL in CI |

## 5. Interview questions

- *How did you secure the API?* Walk through the layers in section 2.
- *What would you do if your JWT secret leaked?* Section 3: rotate first; history keeps old commits.
- *Why is hiding a button not security?* Anyone can call the API directly with curl. Only the backend's check counts.
- *What are your known weaknesses?* Section 4. Knowing them is a strength.
