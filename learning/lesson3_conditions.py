# AEGIS learning script 3: conditions and string basics

event_type = "Auth.Login.Failed"
actor_id = "user-123"
failed_attempts = 7
threshold = 5
login_succeeded = False

# Normalize: make the text consistent
event_type = event_type.lower()
print("Normalized event type:", event_type)

# Rule-like decision
if event_type.startswith("auth.") and failed_attempts >= threshold:
    if failed_attempts >= threshold * 2:
        severity = "high"
    elif failed_attempts > threshold:
        severity = "medium"
    else:
        severity = "low"
    print(f"DETECTION: {actor_id} reached {failed_attempts} failures -> severity {severity}")
elif not login_succeeded:
    print("Failed login, but below threshold. No detection.")
else:
    print("Nothing suspicious.")
