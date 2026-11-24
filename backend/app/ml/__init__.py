"""Machine-learning anomaly detection.

features.py - turns a group of events into numbers ("features"). Used by BOTH
              training (ml/train.py) and live detection, so the model always
              sees numbers computed exactly the same way.
detector.py - loads the trained model and wraps it as the ML-001 rule.
model/      - the trained model file and its metadata (version, threshold, stats).
"""
