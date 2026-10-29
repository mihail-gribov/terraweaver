"""UserPromptSubmit: switches the mode, and in the mode, passes the user's message to the memory's
`say` and puts its answer beside the message.

`/personal` and `/personal off` are seen here first, so the switch is made by code and not left
to the model reading the command. In the mode the agent does not have to remember that the memory
exists, or decide to pass anything: the memory hears every message, keeps what is worth keeping,
and what it holds about this one is already beside it. A memory that is down or slow costs
nothing but its absence — the hook never blocks the prompt.
"""
import json
import re
import sys

from common import ENTERED, LEFT, call, is_on, say, switch

SWITCH = re.compile(r"^/(?:personal-world:)?personal(?:\s+(on|off))?\s*$", re.IGNORECASE)


def main() -> None:
    event = json.load(sys.stdin)
    session = event.get("session_id", "")
    message = (event.get("prompt") or "").strip()
    command = SWITCH.match(message)
    if command:
        on = (command.group(1) or "on").lower() == "on"
        switch(session, on)
        say("UserPromptSubmit", ENTERED if on else LEFT)
        return
    if not message or not is_on(session):
        return
    try:
        found = call("/say", {"messages": [{"role": "user", "text": message}]}, timeout=110).strip()
    except Exception:  # noqa: BLE001 - no memory is no context, never a refused prompt
        return
    if not found or found.lower().rstrip(".") == "nothing":
        return
    say("UserPromptSubmit", "From the user's personal memory, which heard this message (what it "
                            "holds that bears on it; the user's latest word wins over it):\n" + found)


if __name__ == "__main__":
    main()
