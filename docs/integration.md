# Integration: Sending Events to AEGIS from Your Applications

> How another system (your web app, a script, a log shipper) reports events, and how the dashboard talks to the API.

## 1. The contract in one line

`POST /api/v1/events` with header `X-API-Key: <key>` and a JSON body ([api.md](api.md#events)) → `201` (stored) or `200` (already had it).

Get a key: dashboard → **Admin** → **API keys** → name it → **Create key** → copy it at once.
Store it in **that** application's secret settings (environment variable), never in its code.

## 2. Examples

**PowerShell**

```powershell
$headers = @{ "X-API-Key" = $env:AEGIS_API_KEY }
$body = @{
  event_type  = "auth.login.failed"
  occurred_at = (Get-Date).ToUniversalTime().ToString("o")
  source      = "web-app"
  actor_id    = "user-123"
  outcome     = "failure"
  resource    = "/login"
  event_id    = [guid]::NewGuid().ToString()
} | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:8000/api/v1/events" -Headers $headers -ContentType "application/json" -Body $body
```

**Python** (with retries done right)

```python
import os, time, uuid
from datetime import datetime, timezone
import httpx

def send_event(event_type, actor_id, outcome, resource=None, details=None):
    event = {
        "event_id": str(uuid.uuid4()),          # chosen ONCE, reused on every retry
        "event_type": event_type,
        "occurred_at": datetime.now(timezone.utc).isoformat(),
        "source": "web-app",
        "actor_id": actor_id,
        "outcome": outcome,
        "resource": resource,
        "details": details or {},
    }
    for attempt in range(5):
        try:
            r = httpx.post("http://127.0.0.1:8000/api/v1/events", json=event,
                           headers={"X-API-Key": os.environ["AEGIS_API_KEY"]}, timeout=5)
            if r.status_code == 429:                        # rate limited: wait as told
                time.sleep(int(r.headers.get("Retry-After", "1")))
                continue
            r.raise_for_status()
            return r.json()
        except httpx.TransportError:                         # network hiccup: back off and retry
            time.sleep(2 ** attempt)
    raise RuntimeError("AEGIS unreachable; keep the event and send it later")
```

**JavaScript** (Node 18+ or browser-side code you control)

```js
await fetch("http://127.0.0.1:8000/api/v1/events", {
  method: "POST",
  headers: { "Content-Type": "application/json", "X-API-Key": process.env.AEGIS_API_KEY },
  body: JSON.stringify({
    event_id: crypto.randomUUID(),
    event_type: "api.request",
    occurred_at: new Date().toISOString(),
    source: "shop-api",
    actor_id: "user-123",
    outcome: "denied",
    resource: "/admin/export",
  }),
});
```

## 3. Rules for reliable senders

| Rule | Why |
|---|---|
| Generate `event_id` once per event and reuse it on retries | AEGIS stores it once: no fake "5 failed logins" from 1 failure sent 5 times |
| Send `occurred_at` from the moment it happened, with timezone | Late or batched events still land in the right time window |
| Retry on network errors and 5xx with growing waits (1 s, 2 s, 4 s…) | "Exponential backoff" avoids hammering a struggling server |
| On 429, wait `Retry-After` seconds | The limit is 1200 events/min per sender |
| **Don't** retry 4xx except 429 | 401 = bad key, 422 = bad data. Retrying won't help; fix the cause |
| Never put passwords, tokens or full card numbers in `details` | AEGIS stores events for investigation; minimise sensitive data |

## 4. Event types the detectors understand

| `event_type` | `outcome` | Used by |
|---|---|---|
| `auth.login.failed` | `failure` | AUTH-001, AUTH-002, ML-001 |
| `auth.login.success` | `success` | AUTH-002, ML-001 |
| `account.permission.changed` | `success` | ACCOUNT-001 |
| `api.request` | `success` / `denied` | API-001, ACCESS-001 (denied), ML-001 |
| anything else matching `word.word…` | any | stored and searchable; ML-001 counts it |

## 5. How the dashboard integrates with the API

- All calls go through `frontend/src/api.ts`: it adds the token, turns errors into readable messages, and logs out on 401.
- **Development:** the dashboard on `:5173` forwards `/api` to `:8000` (Vite proxy), so there are no CORS issues.
- **Production:**
  - **Docker:** nginx serves the dashboard and forwards `/api` to the `api` container. Same address, no CORS needed.
  - **Vercel + Cloud Run** (different addresses):
    - build the dashboard with `VITE_API_URL=https://<your-api>`;
    - set the API's `CORS_ORIGINS=https://<your-dashboard>`.
- **Types:** `frontend/src/types.ts` mirrors `backend/app/schemas.py`. When you change a schema, change both. TypeScript then points at every place that needs updating.

## 6. Integrating with real log sources (future)

Real environments ship logs with agents such as **Fluent Bit**, **Vector** or **Filebeat**, or via **syslog**.
The usual pattern is a small adapter that:
1. reads the native format (e.g. nginx access logs);
2. maps each line to the AEGIS event schema;
3. posts it with an API key, using the retry rules above.

The event schema is deliberately close to common models such as **ECS** (Elastic Common Schema) and **OCSF**, so such adapters stay thin.
