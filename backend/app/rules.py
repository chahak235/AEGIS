"""AEGIS detection rules (learning version, no timestamps yet)."""


def make_event(event_type, actor_id):
    """Build a minimal event dict."""
    return {"event_type": event_type, "actor_id": actor_id}


def is_auth_event(event):
    """Return True if the event type belongs to the auth group."""
    return event["event_type"].startswith("auth.")


def count_failed_by_actor(events):
    """Return a dict mapping each actor_id to its number of failed logins."""
    counts = {}
    for event in events:
        if event["event_type"] == "auth.login.failed":
            actor = event["actor_id"]
            counts[actor] = counts.get(actor, 0) + 1
    return counts


def detect_repeated_failures(events, threshold=5):
    """Rule AUTH-001 (simplified): return a list of detection dicts."""
    detections = []
    counts = count_failed_by_actor(events)
    for actor, count in counts.items():
        if count >= threshold:
            detections.append({
                "rule_id": "AUTH-001",
                "actor_id": actor,
                "failed_count": count,
                "threshold": threshold,
                "explanation": f"{actor} had {count} failed logins (threshold {threshold})",
            })
    return detections
