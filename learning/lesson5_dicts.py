# AEGIS learning script 5: dictionaries

events = [
    {"event_type": "auth.login.failed", "actor_id": "user-123", "source": "10.0.0.5"},
    {"event_type": "auth.login.failed", "actor_id": "user-123", "source": "10.0.0.5"},
    {"event_type": "auth.login.failed", "actor_id": "user-456", "source": "10.0.0.9"},
    {"event_type": "auth.login.success", "actor_id": "user-123", "source": "10.0.0.5"},
    {"event_type": "auth.login.failed", "actor_id": "user-123", "source": "10.0.0.5"},
    {"event_type": "auth.login.failed", "actor_id": "user-123", "source": "10.0.0.5"},
    {"event_type": "auth.login.failed", "actor_id": "user-123", "source": "10.0.0.5"},
]
threshold = 5

# Access fields of one event
first = events[0]
print("First event actor:", first["actor_id"])
print("Missing field with get():", first.get("resource"))
print("Missing field with default:", first.get("resource", "unknown"))

# Count failed logins per account
failed_by_actor = {}
for event in events:
    if event["event_type"] == "auth.login.failed":
        actor = event["actor_id"]
        failed_by_actor[actor] = failed_by_actor.get(actor, 0) + 1

print("Failed counts:", failed_by_actor)

# Apply the rule to each account
for actor, count in failed_by_actor.items():
    if count >= threshold:
        print(f"DETECTION: {actor} had {count} failed logins (threshold {threshold})")
    else:
        print(f"OK: {actor} had {count} failed logins")
