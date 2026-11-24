"""The detection rules: what AEGIS considers suspicious.

Everything in this file is PURE logic: it takes a list of events and returns
groups of events that match a rule. It never touches the database or the web.
That makes every rule easy to test with hand-made events (tests/test_rules.py).

Vocabulary
----------
window    : how far apart in time events may be and still count together.
threshold : how many matching events are needed inside one window.
match     : a group of events that together satisfy a rule. Each match later
            becomes (or extends) one Detection row in the database.

All thresholds and windows are prototype choices for AEGIS, not industry
standards. They live in RULES at the bottom so they are easy to find and tune.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Protocol
from uuid import UUID


class EventLike(Protocol):
    """Anything with these attributes can be checked by a rule.

    The database model `app.models.Event` fits, and so does a tiny fake event
    in the tests. Rules don't care where the event came from.
    """

    id: UUID
    event_type: str
    occurred_at: datetime
    actor_id: str
    outcome: str


Group = list[EventLike]


@dataclass(frozen=True)
class Rule:
    code: str          # stable ID, e.g. "AUTH-001"; never reused for a different rule
    name: str
    description: str
    severity: str      # "low" | "medium" | "high"
    window: timedelta
    threshold: int
    find: Callable[[Sequence[EventLike]], list[Group]]   # events -> matching groups
    explain: Callable[[Group], str]                      # group  -> human sentence
    # Provenance. Hand-written rules keep the defaults; the ML rule fills them in.
    source_type: str = "rule"                            # "rule" | "ml"
    model_version: str | None = None
    score: Callable[[Group], float] | None = None        # group -> anomaly score (ML only)


# ---------------------------------------------------------------------------
# Building blocks
# ---------------------------------------------------------------------------

def _by_time(events: Sequence[EventLike]) -> Group:
    # Sort by time; the ID breaks ties so the order is always the same.
    return sorted(events, key=lambda e: (e.occurred_at, str(e.id)))


def _clock(moment: datetime) -> str:
    return moment.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


def _span(length: timedelta) -> str:
    seconds = int(length.total_seconds())
    return f"{seconds // 60} min" if seconds % 60 == 0 else f"{seconds} s"


def sliding_window_groups(
    events: Sequence[EventLike], window: timedelta, threshold: int
) -> list[Group]:
    """Find every stretch where at least `threshold` events fit inside `window`.

    How it works (the "two pointers" technique):
      * Sort events by time.
      * Move a right pointer `j` over the events one by one.
      * Move a left pointer `i` forward until events[i]..events[j] span at most `window`.
      * If that stretch holds at least `threshold` events, it is a match.
    Overlapping matches are merged into one group, so 7 failures in a row give
    ONE group of 7, not three overlapping groups of 5.

    Cost: each pointer only moves forward, so this is O(n) after sorting.
    """
    ordered = _by_time(events)
    spans: list[list[int]] = []   # [start_index, end_index] of each merged group
    i = 0
    for j in range(len(ordered)):
        while ordered[j].occurred_at - ordered[i].occurred_at > window:
            i += 1
        if j - i + 1 >= threshold:
            if spans and i <= spans[-1][1]:   # overlaps the previous group: extend it
                spans[-1][1] = j
            else:
                spans.append([i, j])
    return [ordered[start : end + 1] for start, end in spans]


def merge_overlapping(groups: list[Group]) -> list[Group]:
    """Merge groups that share at least one event."""
    merged: list[Group] = []
    for group in sorted(groups, key=lambda g: g[0].occurred_at):
        if merged and {e.id for e in merged[-1]} & {e.id for e in group}:
            union = {e.id: e for e in merged[-1] + group}
            merged[-1] = _by_time(list(union.values()))
        else:
            merged.append(group)
    return merged


def count_rule(
    *,
    code: str,
    name: str,
    description: str,
    severity: str,
    window: timedelta,
    threshold: int,
    is_relevant: Callable[[EventLike], bool],
    noun: str,
) -> Rule:
    """A rule of the form "at least N relevant events within W"."""

    def find(events: Sequence[EventLike]) -> list[Group]:
        return sliding_window_groups([e for e in events if is_relevant(e)], window, threshold)

    def explain(group: Group) -> str:
        return (
            f"{len(group)} {noun} for {group[0].actor_id} between "
            f"{_clock(group[0].occurred_at)} and {_clock(group[-1].occurred_at)} "
            f"(rule: at least {threshold} within {_span(window)})."
        )

    return Rule(code, name, description, severity, window, threshold, find, explain)


# ---------------------------------------------------------------------------
# What each event type means to the rules
# ---------------------------------------------------------------------------

def is_failed_login(e: EventLike) -> bool:
    return e.event_type == "auth.login.failed"


def is_successful_login(e: EventLike) -> bool:
    return e.event_type == "auth.login.success"


def is_denied(e: EventLike) -> bool:
    return e.outcome == "denied"


def is_permission_change(e: EventLike) -> bool:
    return e.event_type == "account.permission.changed"


def is_api_request(e: EventLike) -> bool:
    return e.event_type == "api.request"


# ---------------------------------------------------------------------------
# Rules that are not simple counts
# ---------------------------------------------------------------------------

AUTH_002_WINDOW = timedelta(minutes=10)
AUTH_002_MIN_FAILURES = 3


def _find_failures_then_success(events: Sequence[EventLike]) -> list[Group]:
    """For each successful login, look back AUTH_002_WINDOW for failed logins.

    Enough failures right before a success can mean the password was guessed.
    It can also just mean the user remembered their password, which is why this
    is a signal to investigate, not proof of an attack.
    """
    ordered = _by_time(events)
    failures = [e for e in ordered if is_failed_login(e)]
    groups: list[Group] = []
    for success in (e for e in ordered if is_successful_login(e)):
        before = [
            f for f in failures
            if success.occurred_at - AUTH_002_WINDOW <= f.occurred_at <= success.occurred_at
        ]
        if len(before) >= AUTH_002_MIN_FAILURES:
            groups.append(before + [success])
    return merge_overlapping(groups)


def _explain_failures_then_success(group: Group) -> str:
    failures = [e for e in group if is_failed_login(e)]
    success = [e for e in group if is_successful_login(e)][-1]
    return (
        f"{len(failures)} failed logins for {success.actor_id} followed by a successful "
        f"login at {_clock(success.occurred_at)} (rule: at least {AUTH_002_MIN_FAILURES} "
        f"failures within {_span(AUTH_002_WINDOW)} before a success)."
    )


def _find_permission_changes(events: Sequence[EventLike]) -> list[Group]:
    # Every single permission change is worth a look: one event, one group.
    return [[e] for e in _by_time(events) if is_permission_change(e)]


def _explain_permission_change(group: Group) -> str:
    e = group[0]
    return f"Permission change on account {e.actor_id} at {_clock(e.occurred_at)}."


# ---------------------------------------------------------------------------
# The rule catalogue
# ---------------------------------------------------------------------------

RULES: list[Rule] = [
    count_rule(
        code="AUTH-001",
        name="Repeated failed logins",
        description="Many failed logins for one account in a short time: possible password guessing.",
        severity="medium",
        window=timedelta(minutes=5),
        threshold=5,
        is_relevant=is_failed_login,
        noun="failed logins",
    ),
    Rule(
        code="AUTH-002",
        name="Failed logins followed by success",
        description="Several failed logins, then a success: the password may have been guessed.",
        severity="high",
        window=AUTH_002_WINDOW,
        threshold=AUTH_002_MIN_FAILURES,
        find=_find_failures_then_success,
        explain=_explain_failures_then_success,
    ),
    count_rule(
        code="ACCESS-001",
        name="Repeated access denied",
        description="One account keeps trying things it is not allowed to do.",
        severity="medium",
        window=timedelta(minutes=5),
        threshold=5,
        is_relevant=is_denied,
        noun="denied requests",
    ),
    Rule(
        code="ACCOUNT-001",
        name="Sensitive account change",
        description="An account's permissions changed. Rare and powerful, so always reviewed.",
        severity="high",
        window=timedelta(0),
        threshold=1,
        find=_find_permission_changes,
        explain=_explain_permission_change,
    ),
    count_rule(
        code="API-001",
        name="Unusual request volume",
        description="One account sends far more API requests than a person normally would.",
        severity="medium",
        window=timedelta(minutes=1),
        threshold=100,
        is_relevant=is_api_request,
        noun="API requests",
    ),
]

# The engine fetches events this far either side of a new event, so every rule
# sees all the events it could possibly need.
LOOKAROUND = max(rule.window for rule in RULES)
