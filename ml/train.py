"""Train, evaluate and save the AEGIS anomaly model (Isolation Forest).

Run from the project folder (virtual environment active):

    python ml/train.py

What it does, step by step:
  1. Generate synthetic NORMAL windows, split into train / validation / test.
  2. Generate synthetic ATTACK windows (5 kinds), split into validation / test.
  3. Cut every window into the SAME sub-windows live detection checks
     (app.ml.detector.live_windows) and turn them into features.
  4. Train Isolation Forest on NORMAL training data only.
     (It learns what normal looks like; anything far from it is "anomalous".)
  5. Pick the alarm thresholds on the validation set so that only ~1% of
     normal windows would raise an alarm (target false-positive rate).
     A window counts as flagged if ANY of its sub-windows is flagged,
     exactly like live detection.
  6. Measure precision / recall / F1 on the untouched TEST set, per attack
     type, and compare with the hand-written rules on the same windows.
  7. Save the model + metadata into backend/app/ml/model/, and write the
     evaluation report to docs/ml-evaluation.md.

Everything uses fixed random seeds, so running it again gives the same model.
"""

from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

import joblib
import numpy as np
import sklearn
from sklearn.ensemble import IsolationForest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT / "ml"))

from app.detection.rules import RULES  # noqa: E402
from app.ml.detector import live_windows  # noqa: E402
from app.ml.features import FEATURE_NAMES, FEATURE_SCHEMA_VERSION, extract  # noqa: E402
from synthetic import ATTACKS, Generator  # noqa: E402

SEED = 42
MODEL_VERSION = "iforest-v1"
TARGET_FALSE_POSITIVE_RATE = 0.01
N_NORMAL = {"train": 6000, "val": 1500, "test": 1500}
N_ATTACK_PER_KIND = {"val": 75, "test": 75}
MODEL_DIR = ROOT / "backend" / "app" / "ml" / "model"
REPORT = ROOT / "docs" / "ml-evaluation.md"


def build_split(gen: Generator, n_normal: int, n_attack: int):
    windows, labels = [], []
    for _ in range(n_normal):
        windows.append(gen.normal())
        labels.append("normal")
    for kind in ATTACKS:
        for _ in range(n_attack):
            windows.append(getattr(gen, kind)())
            labels.append(kind)
    return windows, np.array(labels)


def sub_window_rows(window) -> np.ndarray:
    """Features of every sub-window the LIVE detector would check for this activity."""
    return np.array([extract(w) for w in live_windows(window)])


def max_z(X: np.ndarray, mean: np.ndarray, std: np.ndarray) -> np.ndarray:
    """For each row: the biggest number of standard deviations ABOVE normal of any feature."""
    return ((X - mean) / std).max(axis=1)


def per_window(model, windows, mean, std):
    """For each window: the LOWEST Isolation Forest score and the HIGHEST z-score over
    all its sub-windows. Live detection raises an alarm if ANY sub-window is anomalous,
    so these are exactly the numbers that decide whether the window is flagged."""
    rows = [sub_window_rows(w) for w in windows]
    X = np.vstack(rows)
    starts = np.r_[0, np.cumsum([len(r) for r in rows])[:-1]]
    lowest_score = np.minimum.reduceat(model.score_samples(X), starts)
    highest_z = np.maximum.reduceat(max_z(X, mean, std), starts)
    return lowest_score, highest_z


def rules_flag(window) -> bool:
    """Would any hand-written rule fire on this window? (Baseline for comparison.)"""
    return any(rule.find(window) for rule in RULES)


def metrics(flagged: np.ndarray, labels: np.ndarray) -> dict:
    is_attack = labels != "normal"
    tp = int(np.sum(flagged & is_attack))
    fp = int(np.sum(flagged & ~is_attack))
    fn = int(np.sum(~flagged & is_attack))
    tn = int(np.sum(~flagged & ~is_attack))
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {"tp": tp, "fp": fp, "fn": fn, "tn": tn, "precision": round(precision, 3),
            "recall": round(recall, 3), "f1": round(f1, 3),
            "false_positive_rate": round(fp / (fp + tn), 4) if fp + tn else 0.0}


def per_kind_recall(flagged: np.ndarray, labels: np.ndarray) -> dict:
    return {kind: round(float(np.mean(flagged[labels == kind])), 3) for kind in ATTACKS}


def main() -> None:
    gen = Generator(SEED)
    rng = np.random.default_rng(SEED)
    train_windows, _ = build_split(gen, N_NORMAL["train"], 0)
    val_windows, y_val = build_split(gen, N_NORMAL["val"], N_ATTACK_PER_KIND["val"])
    test_windows, y_test = build_split(gen, N_NORMAL["test"], N_ATTACK_PER_KIND["test"])

    # Training rows: up to 5 random sub-windows per normal window, cut exactly
    # the way live detection cuts them (start of a session, middle, end...).
    train_rows = []
    for w in train_windows:
        rows = sub_window_rows(w)
        pick = rng.choice(len(rows), size=min(5, len(rows)), replace=False)
        train_rows.append(rows[pick])
    X_train = np.vstack(train_rows)

    params = {"n_estimators": 200, "max_samples": 256, "random_state": SEED}
    model = IsolationForest(**params).fit(X_train)
    mean, std = X_train.mean(axis=0), X_train.std(axis=0)
    std[std == 0] = 1.0

    # Two complementary checks, each given HALF of the false-alarm budget:
    # (a) Isolation Forest: catches unusual COMBINATIONS of features.
    #     score_samples: HIGHER = more normal; alarm when BELOW its threshold.
    # (b) Extreme-value check: the largest z-score (how many standard deviations
    #     above normal any single feature is). Trees can't extrapolate: to a tree,
    #     400 requests looks the same as the busiest normal user's 90. (b) can.
    half = TARGET_FALSE_POSITIVE_RATE / 2
    val_score, val_z = per_window(model, val_windows, mean, std)
    normal = y_val == "normal"
    threshold = float(np.quantile(val_score[normal], half))
    z_threshold = float(np.quantile(val_z[normal], 1 - half))

    test_score, test_z = per_window(model, test_windows, mean, std)
    if_flagged = test_score < threshold
    z_flagged = test_z > z_threshold
    ml_flagged = if_flagged | z_flagged
    rule_flagged = np.array([rules_flag(w) for w in test_windows])
    either_flagged = ml_flagged | rule_flagged

    detectors = {"rules": rule_flagged, "iforest": if_flagged, "extreme_value": z_flagged,
                 "ml": ml_flagged, "rules_or_ml": either_flagged}
    results = {name: metrics(flags, y_test) for name, flags in detectors.items()}
    results["recall_by_attack"] = {name: per_kind_recall(flags, y_test) for name, flags in detectors.items()}

    metadata = {
        "model_name": "isolation_forest",
        "model_version": MODEL_VERSION,
        "feature_names": list(FEATURE_NAMES),
        "feature_schema_version": FEATURE_SCHEMA_VERSION,
        "threshold": threshold,
        "z_threshold": z_threshold,
        "threshold_method": (f"each check gets half of a {TARGET_FALSE_POSITIVE_RATE:.0%} false-alarm budget, "
                             "measured on normal validation windows"),
        # Normal-behaviour averages: used by the extreme-value check and to
        # explain WHICH features look unusual.
        "train_mean": mean.round(6).tolist(),
        "train_std": std.round(6).tolist(),
        "params": params,
        "training_rows": int(len(X_train)),
        "dataset": {"generator": "ml/synthetic.py", "seed": SEED, "normal": N_NORMAL,
                    "attacks_per_kind": N_ATTACK_PER_KIND, "attack_kinds": list(ATTACKS)},
        "test_results": results,
        "sklearn_version": sklearn.__version__,  # model files only load reliably in the same version
        "trained_on": date.today().isoformat(),
    }

    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, MODEL_DIR / "isolation_forest.joblib", compress=3)
    (MODEL_DIR / "metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    REPORT.write_text(render_report(metadata), encoding="utf-8")

    print(json.dumps(results, indent=2))
    print(f"Saved model to {MODEL_DIR} and report to {REPORT}")


def render_report(m: dict) -> str:
    r = m["test_results"]
    rows = "\n".join(
        f"| {name} | {r[key]['precision']} | {r[key]['recall']} | {r[key]['f1']} | "
        f"{r[key]['false_positive_rate']} | {r[key]['tp']} | {r[key]['fp']} | {r[key]['fn']} |"
        for name, key in (("Rules only", "rules"), ("Isolation Forest alone", "iforest"),
                          ("Extreme-value check alone", "extreme_value"),
                          ("ML-001 (Isolation Forest OR extreme-value)", "ml"),
                          ("Rules OR ML-001 (what AEGIS runs)", "rules_or_ml"))
    )
    kinds = "\n".join(
        f"| `{kind}` | {r['recall_by_attack']['rules'][kind]} | {r['recall_by_attack']['iforest'][kind]} | "
        f"{r['recall_by_attack']['extreme_value'][kind]} | {r['recall_by_attack']['ml'][kind]} | "
        f"{r['recall_by_attack']['rules_or_ml'][kind]} |"
        for kind in m["dataset"]["attack_kinds"]
    )
    features = "\n".join(
        f"| `{name}` | {mean} | {std} |"
        for name, mean, std in zip(m["feature_names"], m["train_mean"], m["train_std"], strict=True)
    )
    n = m["dataset"]
    return f"""# ML Evaluation Report: Isolation Forest (`{m['model_version']}`)

> **This file is generated by `python ml/train.py`.** Do not edit the numbers by hand: re-run the script.
> Trained on {m['trained_on']} with scikit-learn {m['sklearn_version']}, random seed {n['seed']}.

## 1. Honest summary first

- All data is **synthetic** (generated by `ml/synthetic.py`). These numbers describe how the model does on
  **our made-up scenarios**. They do **not** prove how it would do on a real company's traffic.
- The model was trained on **normal activity only** ({n['normal']['train']} windows, cut into {m['training_rows']} sub-windows
  exactly the way live detection cuts them) and never saw an attack while training.
- A test window counts as **flagged** if any sub-window the live detector checks is anomalous: the same
  decision AEGIS makes in production, so these numbers describe the real detector, not a simplified one.
- The alarm threshold was chosen on a separate **validation** set to target about
  **{TARGET_FALSE_POSITIVE_RATE:.0%} false alarms on normal activity**. All numbers below come from a third, untouched **test** set
  ({n['normal']['test']} normal windows + {n['attacks_per_kind']['test']} windows of each attack kind).
- **Treat very high scores with suspicion.** If recall is close to 1.0, the honest reading is that our synthetic
  attacks are *easy to tell apart* from our synthetic normal traffic, not that the model would be that good in
  real life. Real attackers try to look normal. Better data (real or harder synthetic scenarios) is the next step.
- **Rules OR ML has more false alarms than either alone.** Their false alarms add up. That's a real cost:
  analysts' time. Some of the rules' false alarms are expected by design: ACCOUNT-001 fires on every
  permission change, including legitimate ones (3% of synthetic normal windows contain one).

## 2. Results on the test set

| Detector | Precision | Recall | F1 | False-positive rate | True pos. | False pos. | Missed |
|---|---|---|---|---|---|---|---|
{rows}

- **Precision** = of all alarms, how many were real attacks.
- **Recall** = of all attacks, how many raised an alarm.
- **F1** = one number balancing both (their harmonic mean).
- **False-positive rate** = share of normal windows that wrongly raised an alarm.

## 3. Recall per attack kind (share of each attack kind that was caught)

| Attack kind | Rules | Isolation Forest | Extreme-value | ML-001 | Rules OR ML-001 |
|---|---|---|---|---|---|
{kinds}

What the columns show:

- `low_and_slow` is designed to stay just **under** every hand-written rule's threshold. No single number is
  extreme, but the **combination** is unusual: that's what the Isolation Forest is good at.
- `brute_force` and `scraping` are **extreme** on one or two features. The Isolation Forest alone misses them:
  tree models cannot **extrapolate**. A tree only learns "more than the busiest normal user", so 400 requests
  looks the same as 90. The extreme-value check (z-score) catches exactly these. That's why ML-001 uses both.

## 4. Features (what the model looks at)

One sample = one account's events in one **10-minute window**. Mean and standard deviation on normal training data:

| Feature | Normal mean | Normal std |
|---|---|---|
{features}

## 5. Model details

| Item | Value |
|---|---|
| Algorithm | Isolation Forest (scikit-learn) |
| Parameters | `{json.dumps(m['params'])}` |
| Isolation Forest threshold | `{m['threshold']:.4f}` (alarm when the score is below it) |
| Extreme-value threshold | `{m['z_threshold']:.2f}` standard deviations above normal |
| How thresholds were chosen | {m['threshold_method']} |
| Feature schema version | {m['feature_schema_version']} |
| Model file | `backend/app/ml/model/isolation_forest.joblib` |
| Metadata | `backend/app/ml/model/metadata.json` |

## 6. Limitations

- **Synthetic data**: real users are messier (night shifts, automation, holidays). Expect more false alarms on real traffic until retrained on it.
- **One window size** (10 min): very slow attacks spread over hours are invisible to it.
- **Per account only**: an attacker spreading guesses over many accounts ("password spraying") is not modelled.
- **No feedback loop yet**: analyst verdicts (false positive / true positive) are not fed back into training.
- **Pickled model**: the `.joblib` file must be loaded with the same scikit-learn version it was saved with.
"""


if __name__ == "__main__":
    main()
