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

MEMORY = os.environ.get("PERSONAL_MEMORY_URL", "http://127.0.0.1:7110")
# Needed only when the memory serves the network (`--host 0.0.0.0`); localhost ignores it.
TOKEN = os.environ.get("PERSONAL_MEMORY_TOKEN", "")
SESSIONS = Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local" / "state")) / "personal-world" / "sessions"

ENTERED = ("This session is in the user's personal world: their memory is connected and on. It "
           "hears every message of this conversation, keeps what matters about the user, and puts "
           "what it holds about each message beside it. When you need something about the user it "
           "did not give, or something found for them, call the memory's `ask`. The memory gives "
           "facts; deciding is yours, with the user. `/personal off` leaves the mode.")
LEFT = ("The session has left the user's personal world: messages are no longer read against "
        "the memory and nothing is recorded. The memory tools stay available if asked for.")


def call(path: str, body: dict | None = None, timeout: float = 120) -> str:
    data = json.dumps(body).encode() if body is not None else None
    headers = {"Content-Type": "application/json"}
    if TOKEN:
        headers["Authorization"] = f"Bearer {TOKEN}"
    request = urllib.request.Request(MEMORY + path, data=data, headers=headers)
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read().decode()


def launched_on() -> bool:
    return os.environ.get("PERSONAL_WORLD", "").lower() in ("on", "1", "yes")


def is_on(session: str) -> bool:
    """On by its flag, or by the launch until `/personal off`: the launch is not left to
    SessionStart alone — on 2026-10-29 a first message under `claude -p` was passed before
    SessionStart had set the flag, and the memory never heard it."""
    if not session:
        return False
    return (SESSIONS / session).exists() or (launched_on() and not (SESSIONS / f"{session}.off").exists())


def switch(session: str, on: bool) -> None:
    flag, off = SESSIONS / session, SESSIONS / f"{session}.off"
    SESSIONS.mkdir(parents=True, exist_ok=True)
    if on:
        flag.touch()
        off.unlink(missing_ok=True)
    else:
        flag.unlink(missing_ok=True)
        off.touch()


def say(event: str, context: str) -> None:
    """Put text beside what the agent reads next."""
    print(json.dumps({"hookSpecificOutput": {"hookEventName": event, "additionalContext": context}}))
