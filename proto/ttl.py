"""How long what can outlive its use is kept: one TTL, for every kind (2026-10-27, the user's number).

Counted from the last use: a thing found for a task, from the last time a task found or read it; a
program, from the last time it ran. What has been with the user — named in an answer the agent
got, or in the user's own memory — has no TTL and lives until the user says to forget it.
"""
from datetime import timedelta

TTL = timedelta(days=90)
