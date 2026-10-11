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

## Phase 1, Lesson 5: Dictionaries
- Learned: dict key-value pairs, d[key] vs d.get(key, default), .items(), nested list of dicts, per-key counting.
- Implemented: learning/lesson5_dicts.py (events as dicts, failed logins counted per account, threshold rule applied per account).
- Verified: output matched the expected result (user-123 detected, user-456 not).
- Limitations: no timestamps, so no time window yet; data is still hard-coded.

## Phase 1, Lesson 6: Functions
- Learned: def, parameters vs arguments, return vs print, default and keyword arguments, docstrings, local scope.
- Implemented: learning/lesson6_functions.py (count_failed_by_actor, detect_repeated_failures returning explainable detection dicts, make_event helper).
- Verified: output matched the expected result.
- Limitations: no time window or timestamps; no automated tests yet (manual checking only).

## Phase 1, Lesson 7: Modules, packages and first tests
- Learned: modules vs packages, import forms, sys.path, pytest basics, assert, arrange/act/assert, boundary testing.
- Implemented: backend/app/rules.py (AUTH-001 simplified rule, helpers), backend/tests/test_rules.py (8 tests), pytest.ini, requirements-dev.txt.
- Verified: 8 tests pass. Deliberately introduced a >= to > bug; 2 tests failed as expected; bug reverted and all 8 passed again.
- Limitations: rule ignores timestamps and time windows; events are minimal dicts without validation.
