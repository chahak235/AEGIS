"""Unit tests for the detection rules. No database needed: rules are pure logic.

Each rule has POSITIVE tests (it fires when it should) and NEGATIVE tests
(it stays quiet when it should). Both matter: a rule that never fires is
useless, and a rule that always fires buries analysts in false alarms.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

from app.detection.rules import RULES, sliding_window_groups

T0 = datetime(2026, 10, 11, 10, 0, 0, tzinfo=timezone.utc)
RULE = {rule.code: rule for rule in RULES}


@dataclass
class FakeEvent:
    event_type: str
    occurred_at: datetime
    outcome: str = "failure"
    actor_id: str = "user-123"
    id: UUID = field(default_factory=uuid4)


def failures(count, every=timedelta(seconds=10), start=T0):
    return [FakeEvent("auth.login.failed", start + i * every) for i in range(count)]


def success(at):
    return FakeEvent("auth.login.success", at, outcome="success")


# --- The sliding-window building block --------------------------------------

def test_window_is_inclusive_at_the_edge():
    # 5 events exactly 5 minutes apart from first to last: still inside the window.
    events = failures(5, every=timedelta(seconds=75))  # 0, 75, 150, 225, 300 s
    assert len(sliding_window_groups(events, timedelta(minutes=5), 5)) == 1


def test_window_one_second_too_wide_does_not_match():
    events = failures(5, every=timedelta(seconds=75.25))  # last one at 301 s
    assert sliding_window_groups(events, timedelta(minutes=5), 5) == []


def test_overlapping_matches_merge_into_one_group():
    groups = sliding_window_groups(failures(7), timedelta(minutes=5), 5)
    assert len(groups) == 1
    assert len(groups[0]) == 7


def test_far_apart_bursts_stay_separate():
    burst1 = failures(5, start=T0)
    burst2 = failures(5, start=T0 + timedelta(hours=1))
    assert len(sliding_window_groups(burst1 + burst2, timedelta(minutes=5), 5)) == 2


def test_input_order_does_not_matter():
    events = failures(5)
    events.reverse()  # events can arrive out of order over the network
    assert len(sliding_window_groups(events, timedelta(minutes=5), 5)) == 1


# --- AUTH-001: repeated failed logins ---------------------------------------

def test_auth001_fires_on_five_failures():
    groups = RULE["AUTH-001"].find(failures(5))
    assert len(groups) == 1 and len(groups[0]) == 5


def test_auth001_quiet_on_four_failures():
    assert RULE["AUTH-001"].find(failures(4)) == []


def test_auth001_ignores_successful_logins():
    events = failures(4) + [success(T0 + timedelta(seconds=45))]
    assert RULE["AUTH-001"].find(events) == []


def test_auth001_explanation_says_what_and_why():
    rule = RULE["AUTH-001"]
    text = rule.explain(rule.find(failures(6))[0])
    assert "6 failed logins for user-123" in text
    assert "at least 5 within 5 min" in text


# --- AUTH-002: failures followed by success ---------------------------------

def test_auth002_fires_on_three_failures_then_success():
    events = failures(3) + [success(T0 + timedelta(minutes=1))]
    groups = RULE["AUTH-002"].find(events)
    assert len(groups) == 1
    assert groups[0][-1].event_type == "auth.login.success"
    assert len(groups[0]) == 4


def test_auth002_quiet_on_two_failures_then_success():
    events = failures(2) + [success(T0 + timedelta(minutes=1))]
    assert RULE["AUTH-002"].find(events) == []


def test_auth002_quiet_when_success_comes_first():
    events = [success(T0 - timedelta(seconds=1))] + failures(3)
    assert RULE["AUTH-002"].find(events) == []


def test_auth002_quiet_when_failures_are_too_old():
    events = failures(3) + [success(T0 + timedelta(minutes=11))]
    assert RULE["AUTH-002"].find(events) == []


# --- ACCESS-001: repeated access denied --------------------------------------

def test_access001_fires_on_five_denied():
    events = [FakeEvent("api.request", T0 + timedelta(seconds=i), outcome="denied") for i in range(5)]
    assert len(RULE["ACCESS-001"].find(events)) == 1


def test_access001_quiet_on_failures_that_are_not_denied():
    assert RULE["ACCESS-001"].find(failures(10)) == []


# --- ACCOUNT-001: sensitive account change -----------------------------------

def test_account001_fires_on_every_permission_change():
    events = [
        FakeEvent("account.permission.changed", T0, outcome="success"),
        FakeEvent("account.permission.changed", T0 + timedelta(hours=2), outcome="success"),
    ]
    groups = RULE["ACCOUNT-001"].find(events)
    assert len(groups) == 2
    assert "Permission change on account user-123" in RULE["ACCOUNT-001"].explain(groups[0])


def test_account001_quiet_on_other_events():
    assert RULE["ACCOUNT-001"].find(failures(3)) == []


# --- API-001: unusual request volume -----------------------------------------

def api_requests(count):
    return [
        FakeEvent("api.request", T0 + timedelta(milliseconds=500 * i), outcome="success")
        for i in range(count)
    ]


def test_api001_fires_on_100_requests_in_a_minute():
    assert len(RULE["API-001"].find(api_requests(100))) == 1


def test_api001_quiet_on_99_requests():
    assert RULE["API-001"].find(api_requests(99)) == []


# --- The catalogue as a whole ------------------------------------------------

def test_rule_codes_are_unique():
    codes = [rule.code for rule in RULES]
    assert len(codes) == len(set(codes))


def test_every_rule_has_a_valid_severity():
    assert {rule.severity for rule in RULES} <= {"low", "medium", "high"}
