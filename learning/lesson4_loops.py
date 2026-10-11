# AEGIS learning script 4: lists and loops

events = [
    "auth.login.failed",
    "auth.login.failed",
    "auth.login.failed",
    "auth.login.success",
    "access.denied",
    "auth.login.failed",
    "auth.login.failed",
]
threshold = 5

print("Total events:", len(events))
print("First event:", events[0])
print("Last event:", events[-1])

failed_count = 0
for position, event in enumerate(events, start=1):
    print(position, event)
    if event == "auth.login.failed":
        failed_count += 1

print("Failed login count:", failed_count)

if failed_count >= threshold:
    print(f"DETECTION: {failed_count} failed logins reached threshold {threshold}")
else:
    print("No detection.")
