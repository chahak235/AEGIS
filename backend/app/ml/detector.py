"""ML-001: the trained Isolation Forest, wrapped so the engine can use it like any rule.

How a window is judged:
  1. Take an account's events in a 10-minute window.
  2. Turn them into features (same code as training).
  3. Two checks; either one raises the alarm:
     a. Isolation Forest score below its threshold -> unusual COMBINATION.
     b. Any feature far above normal (z-score above its threshold) -> EXTREME value.
        Needed because tree models can't extrapolate: to a tree, 400 requests
        looks like the busiest normal user's 90.
  4. Both thresholds were chosen on validation data during training (ml/train.py).

The explanation names the features furthest from normal (measured in
standard deviations, "z-scores"), so the analyst sees WHY, not just a number.

If the model file or scikit-learn is missing, ML-001 switches itself off and
logs a warning. The hand-written rules keep working. ML is an extra signal,
never a single point of failure.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Sequence
from functools import lru_cache
from pathlib import Path

from app.detection.rules import EventLike, Group, Rule, _by_time, _clock, merge_overlapping
from app.ml.features import FEATURE_NAMES, FEATURE_SCHEMA_VERSION, WINDOW, extract

logger = logging.getLogger(__name__)

MODEL_DIR = Path(__file__).parent / "model"
MAX_WINDOWS_PER_CHECK = 50  # bounds the work per incoming event


@lru_cache(maxsize=1)
def load():
    """Load the model once (first use), then reuse it. Returns (model, metadata) or None."""
    try:
        import joblib

        metadata = json.loads((MODEL_DIR / "metadata.json").read_text(encoding="utf-8"))
        if metadata["feature_names"] != list(FEATURE_NAMES) or \
                metadata["feature_schema_version"] != FEATURE_SCHEMA_VERSION:
            logger.warning("ML model was trained on different features; ML-001 disabled. Re-run ml/train.py.")
            return None
        model = joblib.load(MODEL_DIR / "isolation_forest.joblib")
        return model, metadata
    except Exception:
        logger.warning("ML model not available; ML-001 disabled", exc_info=True)
        return None


def live_windows(events: Sequence[EventLike]) -> list[Group]:
    """The 10-minute windows the live detector checks: one ending at each event
    (or at a sample of them when there are many), the latest always included.
    ml/train.py uses this SAME function, so training sees windows cut exactly
    like live ones (no training/serving skew)."""
    ordered = _by_time(events)
    if not ordered:
        return []
    step = max(1, len(ordered) // MAX_WINDOWS_PER_CHECK)
    ends = sorted(set(range(len(ordered) - 1, -1, -step)))
    windows, start = [], 0
    for end in ends:
        while ordered[end].occurred_at - ordered[start].occurred_at >= WINDOW:
            start += 1
        windows.append(ordered[start:end + 1])
    return windows


def anomaly_score(group: Group) -> float:
    loaded = load()
    if loaded is None:
        return 0.0
    model, _ = loaded
    return float(model.score_samples([extract(group)])[0])


def find(events: Sequence[EventLike]) -> list[Group]:
    loaded = load()
    if loaded is None or not events:
        return []
    model, metadata = loaded
    windows = live_windows(events)
    rows = [extract(w) for w in windows]
    scores = model.score_samples(rows)
    flagged = [w for w, row, s in zip(windows, rows, scores, strict=True)
               if s < metadata["threshold"] or _max_z(row, metadata) > metadata["z_threshold"]]
    return merge_overlapping(flagged)


def _z_scores(row: list[float], metadata: dict) -> list[float]:
    pairs = zip(row, metadata["train_mean"], metadata["train_std"], strict=True)
    return [(v - m) / s if s else 0.0 for v, m, s in pairs]


def _max_z(row: list[float], metadata: dict) -> float:
    return max(_z_scores(row, metadata))


def explain(group: Group) -> str:
    loaded = load()
    if loaded is None:
        return "ML model unavailable."
    _, metadata = loaded
    values = extract(group)
    z = _z_scores(values, metadata)
    ranked = sorted(zip(z, FEATURE_NAMES, values, metadata["train_mean"], strict=True), key=lambda t: -abs(t[0]))
    top = "; ".join(f"{name}={value:g} (normal about {mean:.1f})" for _, name, value, mean in ranked[:3])
    score = anomaly_score(group)
    reasons = []
    if score < metadata["threshold"]:
        reasons.append(f"unusual combination (Isolation Forest score {score:.3f} < {metadata['threshold']:.3f})")
    if max(z) > metadata["z_threshold"]:
        reasons.append(f"a value far above normal ({max(z):.1f} standard deviations > {metadata['z_threshold']:.1f})")
    why = " and ".join(reasons) or "unusual activity in part of this period"
    return (
        f"Anomalous activity for {group[0].actor_id} between {_clock(group[0].occurred_at)} and "
        f"{_clock(group[-1].occurred_at)}: {why} (model {metadata['model_version']}). "
        f"Most unusual: {top}. A statistical signal, not proof: check the evidence."
    )


def ml_rules() -> list[Rule]:
    """ML-001 if a model is available, otherwise nothing."""
    loaded = load()
    if loaded is None:
        return []
    _, metadata = loaded
    return [Rule(
        code="ML-001",
        name="Anomalous activity (machine learning)",
        description="An Isolation Forest trained on normal behaviour finds this account's "
                    "10-minute activity unusual. Catches combinations that no single rule covers.",
        severity="medium",
        window=WINDOW,
        threshold=1,
        find=find,
        explain=explain,
        source_type="ml",
        model_version=metadata["model_version"],
        score=anomaly_score,
    )]
