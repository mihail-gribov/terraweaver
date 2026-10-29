"""Intake: one message of the user's, read with the agent's message just before it, into what the
memory keeps and what it is asked.

    .venv/bin/python -m memory.intake.intake --dialogue experiments/results/13_dialogues/concert-20261027-193801/run.json
    .venv/bin/python -m memory.intake.intake --memops A01_remember
    .venv/bin/python -m memory.intake.intake --longmemeval 3

Agreed with the user, 2026-10-27/28 (docs/TODO.md, "Sorting what the user says"), simple for now.
The rewrite sees two messages only, the agent's and the user's after it: what came earlier the
memory already holds, and shown it the model took its references from there (2026-10-28).

1. **The decision model, on the last four messages of the session**: does the user's message hold
   anything about their personal life, or a request? "up to 400" is the vacuum's budget only with
   what the user said before. No — done, one call for a work message.
2. **The big Nemotron** (prompts/resolve_system.txt, the rewrite worded by the user): whether the
   message starts a new topic; the message rewritten to be understood without the agent's
   message — references resolved from it, everything else as the user said it, a word left as it
   is when the agent's message does not say what it means; and its questions copied out of the
   rewrite. Plain text, no check in code (the user: keep it simple).
3. **Each question** by the decision model: is it what the user asked, and its kind — to know or
   find, to the memory (forget, don't keep), or an action that is the agent's.

A message with nothing to resolve stands as the user wrote it. Nothing here is written anywhere:
it returns what the memory would do, to be measured before it goes into `say`.
"""
import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

# The personal gate reads the last few messages: "up to 400" after "what budget?" is about the
# vacuum the user spoke of before, and with the agent's message alone it scored 0.41 (2026-10-28).
WINDOW = 4
THINK_ROOM = 6000  # the resolver thinks: without it, conditions came and went between runs (2026-10-28)

PROMPTS = Path(__file__).resolve().parent / "prompts"  # every prompt, one file each: see its README


def prompt(name: str) -> str:
    return (PROMPTS / f"{name}.txt").read_text().strip()


def question(name: str) -> tuple[str, str, str]:
    """A yes/no question for the decision model: the question, the yes option, the no option."""
    asked, yes, no = prompt(name).splitlines()
    return asked, yes, no


FOR_MEMORY = question("for_memory")
SAME_QUESTION = question("same_question")
KINDS_ASKED, *_kinds = prompt("kinds").splitlines()
KINDS = [tuple(part.strip() for part in line.split(":", 1)) for line in _kinds]
RESOLVE_SYSTEM, RESOLVE = prompt("resolve_system"), prompt("resolve")

# Words that point into the conversation: a question taken out with one of these left bare does not
# stand alone. Checked by code — asked "can it be understood without the conversation?", the
# decision model gave a good question 0.31 and an unrelated one 0.59 (2026-10-28).
POINTERS = re.compile(r"\b(those|these|that one|this one|the (first|second|third|last|other) one|the latter|the former)\b",
                      re.IGNORECASE)


@dataclass
class Read:
    """What the memory would do with one message."""
    said: str
    new_topic: float = 0.0
    for_memory: float = 0.0
    information: list[str] = field(default_factory=list)
    requests: list[dict] = field(default_factory=list)   # {"text", "kind", "p"}
    dropped: list[dict] = field(default_factory=list)    # {"atom", "why"}
    note: str = ""

    def as_dict(self) -> dict:
        return dict(self.__dict__)


def window(messages: list[dict], upto: int) -> list[dict]:
    """The last WINDOW messages of the session up to and including messages[upto]."""
    now = messages[upto]
    return [m for m in messages[max(0, upto - WINDOW + 1):upto + 1]
            if (m.get("text") or "").strip() and m.get("session") == now.get("session")]


def exchange(messages: list[dict], upto: int) -> list[dict]:
    """messages[upto] with the agent's message just before it, when there is one in the same session:
    all the intake is shown. What came earlier the memory already holds."""
    now = messages[upto]
    before = messages[upto - 1] if upto else None
    if (before and before["role"] in ("agent", "assistant") and (before.get("text") or "").strip()
            and before.get("session") == now.get("session")):
        return [before, now]
    return [now]


def shown(win: list[dict]) -> str:
    who = {"user": "The user", "agent": "The assistant", "assistant": "The assistant"}
    lines = [f'{n}. {who.get(m["role"], m["role"])}: "{" ".join(m["text"].split())[:1500]}"' for n, m in enumerate(win, 1)]
    return prompt("conversation") + "\n" + "\n".join(lines)


def read(messages: list[dict], upto: int, decide, resolver) -> Read:
    """The intake of messages[upto], a message of the user's. `decide` is the decision model
    (noul, choice), `resolver` the big Nemotron (say)."""
    said = " ".join(messages[upto]["text"].split())
    out = Read(said)
    win = exchange(messages, upto)
    out.for_memory = decide.noul(shown(window(messages, upto)), *FOR_MEMORY)["p"]["yes"]
    if out.for_memory < 0.5:
        out.note = "nothing for the memory"
        return out
    got = resolver.say(RESOLVE_SYSTEM, RESOLVE.format(conversation=shown(win)), room=THINK_ROOM, thinking=True)
    try:
        parsed = json.loads(got[got.find("{"):got.rfind("}") + 1])
    except ValueError:
        out.note = "the resolver gave no JSON"
        parsed = {}
    out.new_topic = 1.0 if parsed.get("new_topic") is True else 0.0
    # No agent's message before it (a session's first): nothing to resolve, the message as said.
    out.information = [" ".join(str(parsed.get("message") or said).split()) if len(win) > 1 else said]
    for question in parsed.get("questions") or []:
        question = " ".join(str(question).split())
        context = f'{shown(win)}\n\nThe question, taken out of the last message: "{question}"'
        bare = POINTERS.search(question)
        if bare:
            out.dropped.append({"group": "questions", "atom": question, "why": f"points into the conversation: {bare.group(0)!r}"})
            continue
        if decide.noul(context, *SAME_QUESTION)["p"]["yes"] < 0.5:
            out.dropped.append({"group": "questions", "atom": question, "why": "not the user's question"})
            continue
        kind = decide.choice(context, KINDS_ASKED, KINDS)
        out.requests.append({"text": question, "kind": kind.get("choice"), "p": round(kind["p"].get(kind.get("choice"), 0), 2)})
    return out


def run(messages: list[dict], decide=None, resolver=None) -> list[Read]:
    """Every user message of a conversation, in order."""
    if decide is None or resolver is None:
        from memory.models import role
        decide, resolver = decide or role("sorter"), resolver or role("resolver")
    return [read(messages, i, decide, resolver) for i, m in enumerate(messages) if m["role"] == "user"]


def main() -> None:
    from memory.intake import sources
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--dialogue", help="a run.json of experiments/13_dialogues")
    group.add_argument("--memops", help="a MemOps sample, e.g. A01_remember")
    group.add_argument("--longmemeval", type=int, help="a LongMemEval question's index; its sessions, in order")
    parser.add_argument("--out", help="write every reading as JSON here")
    args = parser.parse_args()
    messages = (sources.dialogue(args.dialogue) if args.dialogue else
                sources.memops(args.memops) if args.memops else sources.longmemeval(args.longmemeval))
    readings = run(messages)
    for r in readings:
        print(f"\n> {r.said[:200]}\n  new topic {r.new_topic:.2f}, for the memory {r.for_memory:.2f}" +
              (f" — {r.note}" if r.note else ""))
        for a in r.information:
            print(f"  + {a}")
        for q in r.requests:
            print(f"  ? {q['text']}  ({q['kind']}, {q['p']})")
        for d in r.dropped:
            print(f"  x {d['atom']}  — {d['why']}")
    if args.out:
        with open(args.out, "w") as file:
            json.dump([r.as_dict() for r in readings], file, indent=1, ensure_ascii=False)


if __name__ == "__main__":
    sys.exit(main())
