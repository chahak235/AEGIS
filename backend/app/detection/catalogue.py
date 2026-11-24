"""Every detector AEGIS runs: the hand-written rules plus (if available) the ML model.

The engine, the rules API and the incident titles all read this one list,
so they can never disagree about which detectors exist.
"""

from app.detection.rules import RULES, Rule
from app.ml.detector import ml_rules

ALL_RULES: list[Rule] = RULES + ml_rules()

RULES_BY_CODE = {rule.code: rule for rule in ALL_RULES}

# The engine fetches events this far either side of a new event, so every
# detector sees all the events it could need.
LOOKAROUND = max(rule.window for rule in ALL_RULES)
