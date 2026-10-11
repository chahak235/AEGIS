# AEGIS learning script 2: variables and data types

event_type = "auth.login.failed"
actor_id = "user-123"
failed_attempts = 5
threshold = 5
risk_score = 0.82
login_succeeded = False
resolution_note = None

print("event_type:", event_type, type(event_type))
print("actor_id:", actor_id, type(actor_id))
print("failed_attempts:", failed_attempts, type(failed_attempts))
print("risk_score:", risk_score, type(risk_score))
print("login_succeeded:", login_succeeded, type(login_succeeded))
print("resolution_note:", resolution_note, type(resolution_note))

threshold_reached = failed_attempts >= threshold
print("threshold_reached:", threshold_reached)

print(f"{actor_id} had {failed_attempts} failed attempts (threshold {threshold})")
