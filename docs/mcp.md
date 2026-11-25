# MCP: Letting AI Assistants Use AEGIS (design)

> Status: **design only**, not built. Read this to understand MCP and how it would plug into AEGIS.

## 1. What is MCP?

**MCP (Model Context Protocol)** is an open standard (introduced by Anthropic in 2024) for connecting AI assistants
to tools and data. An **MCP server** offers *tools* (functions with typed inputs) and *resources* (readable data).
Any MCP-capable assistant (Claude Desktop, Claude Code, IDE assistants) can discover and call them.

Analogy:
- AEGIS's REST API is a **restaurant menu for programs**;
- an MCP server is the **same menu rewritten for an AI waiter**, with a description of when each dish is useful.

## 2. Why it would be useful for AEGIS

An analyst could ask, in plain language:

- "What are the open critical incidents, and what do they have in common?"
- "Summarise incident 3f2a… and suggest what to check next."
- "Add a note: user confirmed the logins were theirs."

The assistant calls AEGIS tools, reads the real data, and answers with citations to incidents and events.

## 3. Proposed design

```text
 AI assistant ──MCP (stdio or HTTP)──► aegis-mcp server ──HTTPS + analyst JWT──► AEGIS API
                                       (thin adapter, no direct database access)
```

| Tool | Calls | Read/write |
|---|---|---|
| `list_incidents(status?, severity?, limit?)` | `GET /api/v1/incidents` | read |
| `get_incident(incident_id)` | `GET /api/v1/incidents/{id}` | read |
| `search_events(actor_id?, event_type?, limit?)` | `GET /api/v1/events` | read |
| `explain_rule(code)` | `GET /api/v1/rules` | read |
| `add_note(incident_id, body)` | `POST /api/v1/incidents/{id}/notes` | **write** (ask the user first) |

Implementation sketch (Python, official `mcp` SDK):

```python
from mcp.server.fastmcp import FastMCP
import httpx, os

mcp = FastMCP("aegis")
API = os.environ["AEGIS_API_URL"]
HEADERS = {"Authorization": f"Bearer {os.environ['AEGIS_TOKEN']}"}

@mcp.tool()
def list_incidents(status: str = "open", limit: int = 10) -> list[dict]:
    """List incidents, most recent activity first."""
    r = httpx.get(f"{API}/api/v1/incidents", params={"status": status, "limit": limit}, headers=HEADERS)
    r.raise_for_status()
    return r.json()

if __name__ == "__main__":
    mcp.run()
```

## 4. Security rules for the MCP server

1. **Go through the API, never the database:** every check (login, role, validation, audit) still applies.
2. **Least privilege:**
   - give it its own **analyst** account, never admin;
   - start with read-only tools.
3. **Writes need human confirmation:** `add_note` must be approved by the person in the assistant UI. The audit log will show the MCP account's username.
4. **Treat incident text as data, not instructions:**
   - event `details` and notes can contain anything, including text written to trick an AI ("ignore your instructions…"), called **prompt injection**;
   - the server returns it as data;
   - the assistant must never act on instructions found inside it.
5. **Token in the environment**, short-lived, never in code.

## 5. Interview angle

"I designed an MCP adapter that exposes AEGIS's existing REST API to AI assistants as typed tools. It reuses the
API's authentication, roles and audit trail rather than bypassing them, starts read-only, and treats all incident
content as untrusted input because of prompt injection."
