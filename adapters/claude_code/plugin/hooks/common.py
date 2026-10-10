"""What the hooks share: where the memory is, how to call it, and whether this session is in it.

Standard library only, so the hooks run under any python3 without the project's venv.

The mode is per session: a session is in the personal world from `/personal` until
`/personal off`, or from its start when launched with PERSONAL_WORLD=on (`claude-personal`).
Outside it every hook does nothing, so the plugin can stay installed in sessions about code.
"""
import json
import os
import urllib.request
from pathlib import Path

MEMORY = os.environ.get("PERSONAL_MEMORY_URL", "http://127.0.0.1:7100")
SESSIONS = Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local" / "state")) / "personal-world" / "sessions"

ENTERED = ("This session is in the user's personal world: their memory is connected and on, "
           "and what it holds about each message is put beside it. Use the personal-memory "
           "skill: tell facts about the user the moment they come up, and ask the memory before "
           "saying you don't know something about the user. `/personal off` leaves the mode.")
LEFT = ("The session has left the user's personal world: messages are no longer read against "
        "the memory and nothing is recorded. The memory tools stay available if asked for.")


def call(path: str, body: dict | None = None, timeout: float = 120) -> str:
    data = json.dumps(body).encode() if body is not None else None
    request = urllib.request.Request(MEMORY + path, data=data,
                                     headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read().decode()


def is_on(session: str) -> bool:
    return bool(session) and (SESSIONS / session).exists()


def switch(session: str, on: bool) -> None:
    flag = SESSIONS / session
    if on:
        SESSIONS.mkdir(parents=True, exist_ok=True)
        flag.touch()
    else:
        flag.unlink(missing_ok=True)


def say(event: str, context: str) -> None:
    """Put text beside what the agent reads next."""
    print(json.dumps({"hookSpecificOutput": {"hookEventName": event, "additionalContext": context}}))
