"""Incidents: grouping related detections into one investigation.

lifecycle.py   - the rules of the game: statuses, allowed moves, severity. Pure logic.
correlation.py - deciding which incident a new detection belongs to (uses the database).
"""
