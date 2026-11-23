"""Unit tests for incident lifecycle rules (no database)."""

import pytest

from app.incidents.lifecycle import (
    ALLOWED_TRANSITIONS,
    STATUSES,
    InvalidTransition,
    check_transition,
    incident_severity,
    incident_title,
)


@pytest.mark.parametrize(
    "current, new",
    [
        ("open", "acknowledged"),
        ("open", "resolved"),
        ("acknowledged", "investigating"),
        ("investigating", "resolved"),
        ("resolved", "closed"),
        ("resolved", "investigating"),  # reopen
    ],
)
def test_allowed_transitions(current, new):
    check_transition(current, new)  # must not raise


@pytest.mark.parametrize(
    "current, new",
    [
        ("closed", "open"),           # closed is final
        ("closed", "investigating"),
        ("investigating", "open"),    # no going back to "nobody looked yet"
        ("open", "closed"),           # must be resolved (with a conclusion) first
        ("resolved", "open"),
    ],
)
def test_forbidden_transitions(current, new):
    with pytest.raises(InvalidTransition):
        check_transition(current, new)


def test_error_message_lists_what_is_allowed():
    with pytest.raises(InvalidTransition, match="Allowed from 'investigating': resolved"):
        check_transition("investigating", "open")


def test_every_status_has_a_transition_entry():
    assert set(ALLOWED_TRANSITIONS) == set(STATUSES)


def test_severity_is_the_highest_detection_severity():
    assert incident_severity(["medium", "high", "medium"], distinct_rules=2) == "high"


def test_three_different_rules_raise_severity_one_level():
    assert incident_severity(["medium", "high", "medium"], distinct_rules=3) == "critical"


def test_severity_never_goes_above_critical():
    assert incident_severity(["critical"], distinct_rules=5) == "critical"


def test_title_lists_each_rule_once():
    title = incident_title("bob", ["Repeated failed logins", "Repeated failed logins", "X"])
    assert title == "Suspicious activity on bob: Repeated failed logins, X"
