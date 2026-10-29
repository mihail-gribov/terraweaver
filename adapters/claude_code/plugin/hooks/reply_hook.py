"""Stop: in the personal world, the agent's reply goes to the memory's `say` as the agent's.

The user's "up to 400" is the budget only after the agent's "what budget?", and "ok, order it"
says what was ordered only after the agent named it. So the memory hears the agent's side too —
never as a fact of the user's life, only as what the user's next words answer. Run in the
foreground: the memory only holds the reply for the user's next message, a few milliseconds. An
`async` Stop hook never reached the memory under `claude -p` (2026-10-28): the process is gone first.
"""
import json
import sys

from common import call, is_on


def last_reply(transcript: str) -> str:
    """The agent's last text in the session's transcript (JSON lines)."""
    text = ""
    try:
        with open(transcript) as file:
            for line in file:
                try:
                    entry = json.loads(line)
                except ValueError:
                    continue
                message = entry.get("message") or {}
                if entry.get("type") != "assistant" or not isinstance(message, dict):
                    continue
                said = [c.get("text", "") for c in message.get("content") or [] if isinstance(c, dict) and c.get("type") == "text"]
                if any(said):
                    text = "\n".join(t for t in said if t)
    except OSError:
        return ""
    return text


def main() -> None:
    event = json.load(sys.stdin)
    if not is_on(event.get("session_id", "")):
        return
    reply = (event.get("last_assistant_message") or "").strip() or last_reply(event.get("transcript_path") or "")
    if not reply:
        return
    try:
        call("/say", {"messages": [{"role": "agent", "text": reply}]}, timeout=10)
    except Exception:  # noqa: BLE001 - a memory that is down misses the reply, nothing more
        return


if __name__ == "__main__":
    main()
