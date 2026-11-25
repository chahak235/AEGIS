# Login, Tokens (JWT), Roles and API Keys

> Code:
> - `backend/app/security.py`: hashing, tokens, keys;
> - `backend/app/deps.py`: who is calling, and are they allowed;
> - `backend/app/api/v1/auth.py`: login endpoint;
> - `backend/app/api/v1/users.py`: users and API keys.
>
> Tests: `backend/tests/test_auth.py` (26 tests, mostly about keeping the WRONG people out).

## 1. Two questions every request must answer

| Question | Name | AEGIS answer | Failure |
|---|---|---|---|
| **Who are you?** | Authentication | A login token (people) or an API key (systems) | **401** |
| **Are you allowed to do this?** | Authorization | Your role: `analyst` or `admin` | **403** |

Analogy: at an airport, your **passport** proves who you are (authentication). Your **boarding pass** decides which plane you may board (authorization).

## 2. Passwords: stored as Argon2id hashes, never as passwords

- **Hash:** a one-way scramble. `hash("my password")` gives a long string. You can check a password against it, but you can't turn it back.
- **Salt:** random data mixed in, so two users with the same password get different hashes. That defeats pre-computed "rainbow tables".
- **Why Argon2id:** it's deliberately **slow and memory-hungry**. Someone who steals the database can only test a few guesses per second per password, not billions. OWASP recommends it (Open Web Application Security Project).
- **Without hashing:** one database leak = every password exposed. People reuse passwords, so it would also expose their email and bank accounts.
- **Alternatives:** bcrypt (fine, older); scrypt; PBKDF2 (weakest of these against GPUs). Never plain SHA-256 for passwords: it's too fast.
- **Upgrades:** if hashing settings get stronger later, `password_needs_rehash` re-hashes at the next successful login.

Minimum length 12. Length beats complexity rules.

## 3. Login tokens (JWT)

After a correct password, AEGIS gives the browser a **JWT** (JSON Web Token): three base64 parts, `header.claims.signature`.

```json
{"sub": "<user id>", "username": "alice", "role": "analyst",
 "iss": "aegis", "aud": "aegis-api", "iat": 1764000000, "exp": 1764001800}
```

- **Signed, not encrypted.** Anyone can *read* the claims. Only AEGIS, which holds `JWT_SECRET`, can *create* a valid signature. Change one character and the signature no longer matches.
- **Short-lived:** 30 minutes (`ACCESS_TOKEN_MINUTES`). A stolen token is useful for less time.
- **What AEGIS checks on every request:**
  1. signature (HS256 with `JWT_SECRET`);
  2. expiry;
  3. issuer `aegis`;
  4. audience `aegis-api`;
  5. required claims present;
  6. **the user still exists and is active** (database lookup). So deactivating a user locks them out immediately, even with an unexpired token.
- **The algorithm is fixed by the server** (`algorithms=["HS256"]`). The classic attack sends a token with `"alg": "none"` (no signature) and hopes the server trusts the token's own header. There's a test for it.
- **Why JWT:** stateless and standard, it works for browsers, scripts and mobile apps alike.
- **Trade-offs:**
  - A JWT can't be "un-issued". We handle that with the active-user check and short expiry.
  - Alternatives: server-side sessions (a session ID in an httpOnly cookie) or OAuth 2 / OpenID Connect with an identity provider (Google, Okta, Microsoft Entra). Those are for company single sign-on: the natural next step for a real deployment.

**Where the dashboard keeps it:**
- `sessionStorage`, which is cleared when the tab closes.
- Any script on the page could read it, so the dashboard loads **no** third-party scripts, and nginx sends a strict Content-Security-Policy.
- The stronger alternative, an httpOnly cookie, needs CSRF protection. It's on the roadmap.

## 4. Roles

| Action | analyst | admin |
|---|---|---|
| Read events, detections, rules, incidents, stats | ✅ | ✅ |
| Send events (while logged in) | ✅ | ✅ |
| Change incident status / assignment, add notes, read an incident's history | ✅ | ✅ |
| Read the **whole** audit log | ❌ 403 | ✅ |
| Manage users and API keys | ❌ 403 | ✅ |

How it's enforced: `require_roles(...)` in `deps.py`, attached to whole routers (`dependencies=[Depends(admin_only)]`), so a new endpoint can't "forget" the check.
Admins **can't demote or deactivate themselves** (409). Otherwise a mis-click could leave nobody able to fix it.

## 5. API keys (for systems, not people)

- Format: `aeg_1a2b3c4d_<43 random characters>`. The prefix lets humans tell keys apart.
- **Shown once** at creation. AEGIS stores only a SHA-256 hash.
  - SHA-256 is fine here, unlike for passwords: the key is long and random, so there's nothing to guess.
- **Can only send events.** A leaked key can't read incidents (the tests check this).
- **Revoked, not deleted:** old audit records still make sense; `last_used_at` shows whether a key is still used.

## 6. Brute-force protection

- **Rate limits on login:**
  - 20 attempts per 5 min per IP (one machine guessing many accounts);
  - 10 per 5 min per username (many machines guessing one account).
  - Over the limit → **429** + `Retry-After`. Checked **before** the password, so a blocked attacker learns nothing.
- **Same answer** for "no such user" and "wrong password", and the **same timing**: unknown users are checked against a dummy hash.
- **AEGIS watches itself:**
  - every login attempt to AEGIS becomes an event (`source: "aegis"`);
  - 5 wrong passwords for one username → **AUTH-001** fires and an incident opens, about an attack on AEGIS itself.
- Every login success/failure is also in the audit log.

## 7. Creating the first admin

The very first admin can't be created through the API (nobody can log in yet). Use the command line, from `backend/` with the virtual environment active:

```powershell
python -m app.cli create-user admin --role admin
```

It asks for the password twice, without showing it. More users can then be added on the dashboard's **Admin** page.

## 8. Interview questions

- *Authentication vs authorization?* Section 1.
- *How do you store passwords?* Argon2id: slow, salted, one-way (section 2).
- *What's inside a JWT and is it encrypted?* Signed claims, readable by anyone, forgeable by no one without the secret (section 3).
- *How do you revoke a JWT?* Short expiry + check the user is active on every request; a deny-list is the heavier alternative.
- *How do you stop password guessing?* Rate limits per IP and per username, identical errors and timing, and detection of the attack itself (section 6).
- *Why are API keys hashed with SHA-256 but passwords with Argon2?* Entropy: random keys can't be guessed; human passwords can.
