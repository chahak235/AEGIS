"""Incident lifecycle rules. Pure logic: no database, no web. Tested in test_incident_lifecycle.py.

Statuses and allowed moves (a "state machine"):

    open ──────────► acknowledged ──► investigating ──► resolved ──► closed
      │                   │                 ▲               │
      │                   └─────────────────┼──► resolved   │
      └──► investigating / resolved         └───── reopen ──┘

* open          : nobody has looked yet.
* acknowledged  : an analyst has seen it ("I'm on it").
* investigating : actively being worked on.
* resolved      : a conclusion was reached (needs a resolution category).
* closed        : final. Nothing can change any more.

Why a state machine? Without one, an incident could jump from "closed" back to
"open" with no trace, or be "resolved" without saying what the conclusion was.
Clear rules make the history trustworthy and auditable.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import timedelta

STATUSES = ("open", "acknowledged", "investigating", "resolved", "closed")

ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    "open": {"acknowledged", "investigating", "resolved"},
    "acknowledged": {"investigating", "resolved"},
    "investigating": {"resolved"},
    "resolved": {"closed", "investigating"},  # "investigating" here = reopen
    "closed": set(),
}

# Incidents in these statuses still collect new detections.
ACTIVE_STATUSES = ("open", "acknowledged", "investigating")

# What the analyst concluded.
RESOLUTIONS = ("true_positive", "false_positive", "benign", "duplicate")

SEVERITIES = ("low", "medium", "high", "critical")

# A new detection joins an active incident for the same account if the
# incident had activity within this long before the detection started.
CORRELATION_WINDOW = timedelta(hours=1)

# This many DIFFERENT rules firing for one account in one incident raises the
# severity by one level: several kinds of suspicious behaviour together are
# more worrying than any one alone.
ESCALATE_AT_DISTINCT_RULES = 3


class InvalidTransition(ValueError):
    """Raised when someone tries a status change the state machine forbids."""


def check_transition(current: str, new: str) -> None:
    if new not in STATUSES:
        raise InvalidTransition(f"Unknown status '{new}'.")
    if new not in ALLOWED_TRANSITIONS[current]:
        allowed = ", ".join(sorted(ALLOWED_TRANSITIONS[current])) or "nothing (final status)"
        raise InvalidTransition(
            f"Cannot change status from '{current}' to '{new}'. Allowed from '{current}': {allowed}."
        )


def severity_rank(severity: str) -> int:
    return SEVERITIES.index(severity)


def incident_severity(detection_severities: Iterable[str], distinct_rules: int) -> str:
    """Highest detection severity, raised one level when many different rules fired."""
    rank = max(severity_rank(s) for s in detection_severities)
    if distinct_rules >= ESCALATE_AT_DISTINCT_RULES:
        rank = min(rank + 1, len(SEVERITIES) - 1)
    return SEVERITIES[rank]


def incident_title(actor_id: str, rule_names: Iterable[str]) -> str:
    names = list(dict.fromkeys(rule_names))  # unique, keep first-seen order
    return f"Suspicious activity on {actor_id}: {', '.join(names)}"[:300]
