"""PreToolUse on the memory's writes (`tell`, `add_memory`, `forget`): outside the personal world
nothing is written.

Measured: with the mode off, the agent still recorded "the user is allergic to cats" on its own —
the skill and the server's instructions are there in every session the plugin is loaded in. So
"off" is enforced here, in code: reading stays open, writing is refused with the way back in.
"""
import json
import sys

from common import is_on


def main() -> None:
    event = json.load(sys.stdin)
    if is_on(event.get("session_id", "")):
        return
    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "permissionDecision": "deny",
        "permissionDecisionReason": "This session is not in the user's personal world, so nothing "
                                    "is recorded. Don't retry; if the user wants it kept, they can "
                                    "run /personal."}}))


if __name__ == "__main__":
    main()
