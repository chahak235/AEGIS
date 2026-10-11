from app.rules import (
    count_failed_by_actor,
    detect_repeated_failures,
    is_auth_event,
    make_event,
)


def failed_events(actor_id, how_many):
    """Test helper: build a list of failed-login events for one actor."""
    events = []
    for _ in range(how_many):
        events.append(make_event("auth.login.failed", actor_id))
    return events


def test_empty_list_gives_no_detections():
    assert detect_repeated_failures([]) == []


def test_below_threshold_gives_no_detections():
    events = failed_events("user-1", 4)
    assert detect_repeated_failures(events, threshold=5) == []


def test_at_threshold_gives_one_detection():
    events = failed_events("user-1", 5)
    result = detect_repeated_failures(events, threshold=5)
    assert len(result) == 1
    assert result[0]["rule_id"] == "AUTH-001"
    assert result[0]["actor_id"] == "user-1"
    assert result[0]["failed_count"] == 5


def test_failures_are_counted_per_actor():
    events = failed_events("user-1", 3) + failed_events("user-2", 3)
    assert count_failed_by_actor(events) == {"user-1": 3, "user-2": 3}
    assert detect_repeated_failures(events, threshold=5) == []


def test_success_events_are_not_counted():
    events = failed_events("user-1", 2)
    events.append(make_event("auth.login.success", "user-1"))
    assert count_failed_by_actor(events) == {"user-1": 2}


def test_custom_threshold():
    events = failed_events("user-1", 2)
    assert len(detect_repeated_failures(events, threshold=2)) == 1
    assert len(detect_repeated_failures(events, threshold=3)) == 0


def test_is_auth_event_true():
    assert is_auth_event(make_event("auth.login.failed", "u1")) is True


def test_is_auth_event_false():
    assert is_auth_event(make_event("api.request", "u1")) is False
