# AEGIS learning script 6: functions

def count_failed_by_actor(events):
    """Return a dict mapping each actor_id to its number of failed logins."""
    counts = {}
    for event in events:
        if event["event_type"] == "auth.login.failed":
            actor = event["actor_id"]
            counts[actor] = counts.get(actor, 0) + 1
    return counts


def detect_repeated_failures(events, threshold=5):
    """Rule AUTH-001 (simplified): return a list of detections."""
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


def make_event(event_type, actor_id):
    return {"event_type": event_type, "actor_id": actor_id}


# Build test data using our function
events = []
for _ in range(5):
    events.append(make_event("auth.login.failed", "user-123"))
events.append(make_event("auth.login.failed", "user-456"))
events.append(make_event("auth.login.success", "user-123"))

# Call the rule with the default threshold
found = detect_repeated_failures(events)
print("Detections (threshold 5):", len(found))
for detection in found:
    print(detection["rule_id"], "-", detection["explanation"])

# Call again with a different threshold
found_low = detect_repeated_failures(events, threshold=1)
print("Detections (threshold 1):", len(found_low))

# A function with no return gives None
print("make_event result:", make_event("api.request", "user-9"))
