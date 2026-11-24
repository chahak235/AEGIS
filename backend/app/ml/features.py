"""Feature extraction: describe one account's activity in one time window as numbers.

A machine-learning model can't read events. It reads a row of numbers. Each
number is a "feature". Picking good features is most of the work in practical
ML: the model can only notice what the features describe.

The SAME function is used when training and when detecting live. If training
and live code computed features differently ("training/serving skew"), the
model would be judging numbers it never learned about.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import timedelta

from app.detection.rules import (
    EventLike,
    is_api_request,
    is_denied,
    is_failed_login,
    is_successful_login,
)

WINDOW = timedelta(minutes=10)

# Order matters: the model sees a list of numbers in exactly this order.
# Changing this list means retraining (and bumping FEATURE_SCHEMA_VERSION).
FEATURE_NAMES = (
    "event_count",           # how much activity in total
    "failed_logins",
    "successful_logins",
    "denied",                # "you're not allowed to do that"
    "api_requests",
    "distinct_event_types",  # how varied the activity is
    "distinct_resources",    # how many different things were touched (scanning?)
    "failure_ratio",         # share of events that failed or were denied (0..1)
)
FEATURE_SCHEMA_VERSION = 1


def extract(events: Sequence[EventLike], resources: Sequence[str | None] | None = None) -> list[float]:
    """Features for one window of one account's events.

    `resources` may be passed separately because the rules' EventLike doesn't
    require a `resource`; real Event rows have one, so we read it if present.
    """
    if resources is None:
        resources = [getattr(e, "resource", None) for e in events]
    total = len(events)
    failed = sum(1 for e in events if is_failed_login(e))
    denied = sum(1 for e in events if is_denied(e))
    bad = sum(1 for e in events if e.outcome in ("failure", "denied"))
    return [
        float(total),
        float(failed),
        float(sum(1 for e in events if is_successful_login(e))),
        float(denied),
        float(sum(1 for e in events if is_api_request(e))),
        float(len({e.event_type for e in events})),
        float(len({r for r in resources if r})),
        (bad / total) if total else 0.0,
    ]
