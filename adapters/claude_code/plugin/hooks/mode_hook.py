"""SessionStart: a session launched in the personal world starts in it, and stays in it.

Launched with PERSONAL_WORLD=on, the session is switched on at start. A session already in the
mode is reminded of it after a compaction or a resume, since the line that said so may be gone.
"""
import json
import sys

from common import ENTERED, is_on, launched_on, say, switch


def main() -> None:
    event = json.load(sys.stdin)
    session = event.get("session_id", "")
    if event.get("source") == "startup" and launched_on():
        switch(session, True)
    if is_on(session):
        say("SessionStart", ENTERED)


if __name__ == "__main__":
    main()
