"""Onboarding: bringing a world up from the files that describe it.

A world is not only a database — it starts from what a person already keeps beside their work:
who they are, who the assistant is, and how the pair of them have arranged things. Reading that
in is onboarding, and it runs whenever a world is opened, not once at the beginning: the files
change, and the world follows them.

Today it does one thing — the two parties (`selves.py`): `USER.md` and its kin describe the
person, `soul.md` and its kin describe the assistant, and what they say becomes statements with
the file as their source, joining whatever conversation has said about the same two.

What belongs here and isn't built yet (`docs/TODO.md`):

- class additions and procedures declared in `AGENT.md` (`agentfile.py`, parked) — the two upper
  levels of change, written by a person rather than grown by the world;
- the first conversation: a world with nothing in it asking for the few things that make the
  rest of it useful, instead of waiting to be told;
- importing what already exists — contacts, a calendar — as statements from those sources.

Kept as its own step even while it does almost nothing, because the name is the thing that stops
this being four unrelated hooks in the runtime.
"""
from pathlib import Path

from terraweaver import selves


def onboard(world, home: Path | None) -> list[str]:
    """Read the world's own files into it. Returns what was read, for the log."""
    return selves.refresh(world, home)
