# AEGIS Development Log

## Phase 0: Environment and repository
- Created Python virtual environment, Git repository, .gitignore, README.
- Initial commit pushed to GitHub (verified in Lesson 1).

## Phase 1, Lesson 1: First Python script
- Learned: terminal, current directory, what the Python interpreter does, what a virtual environment does.
- Implemented: learning/first_script.py (prints a message, an example event type, and the interpreter path).
- Verified: script runs using the interpreter inside .venv.
- Limitations: no tests yet; nothing AEGIS-specific is implemented.

## Phase 1, Lesson 2: Variables and data types
- Learned: variables, str/int/float/bool/None, comparison operators, f-strings.
- Implemented: learning/lesson2_types.py (an example event as variables, plus a threshold comparison).
- Verified: output matched the expected result.
- Debugging practised: TypeError (str + int), NameError (typo), assignment vs comparison.
- Limitations: values are hard-coded; no real event structure yet.

## Phase 1, Lesson 3: Conditions and string basics
- Learned: if/elif/else, indentation, and/or/not, .lower(), .startswith(), f-strings.
- Implemented: learning/lesson3_conditions.py (normalizes an event type, applies a threshold rule with a severity ladder).
- Verified: output matched the expected result.
- Limitations: one hard-coded event; no loops yet, so cannot process many events.

## Phase 1, Lesson 4: Lists and loops
- Learned: lists, indexing (including negative), len(), append(), for loops, enumerate, the counter pattern.
- Implemented: learning/lesson4_loops.py (counts failed logins across a list of events and applies a threshold).
- Verified: output matched the expected result (5 failures, detection raised).
- Limitations: counts all events together; ignores which account and time window, so it is not a real AUTH-001 yet.
