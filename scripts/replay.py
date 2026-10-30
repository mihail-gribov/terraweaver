"""A run replayed as an animation, one 1920×1080 page: the conversation on the left, the memory on the
right — the deciding blocks and the four stores — every step taken from the run's own trace.

Writing: each message of the user's passes the gate, is resolved against the agent's message when
there was one, is kept in the journal; the graph decides whether to read it and what it adds to the
user's world, the topics and the portraits. Reading: the last message, the one the agent answers,
shows what was found in each store, the note the memory made of it, and the agent's reply.

Run: .venv/bin/python scripts/replay.py benchmarks/runs/demo-recall-birthday-... [--out page.html]
  or, after a live session with the plugin: .venv/bin/python scripts/replay.py var/memory/<name>
"""
import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from memory.graph import PARTS, USER  # noqa: E402

TEMPLATE = Path(__file__).with_name("replay.html")
sys.path.insert(0, str(Path(__file__).parent))
from demo_recall import FILLER  # noqa: E402

# The work talk the demo stories are padded with: shown as a time-lapse whatever the memory did with
# it — a line of it that got read goes by as fast as one that was stopped.
FILLER_TEXTS = {" ".join(text.split()) for talk in FILLER for _, text in talk}


def lines(path: Path) -> list[dict]:
    return [json.loads(l) for l in path.read_text().splitlines() if l.strip()] if path.exists() else []


def world_items(links: list[dict]) -> list[dict]:
    """The links of the fixed parts, as a person's card shows them: whose, which part, what."""
    out = []
    for l in links:
        part = l.get("relation")
        if part not in PARTS:
            continue
        who, value = l["from"], l["to"]
        if value == USER and PARTS[part].who:
            # "Mila — spouse → the user": a card of Mila's, titled by what she is to the user.
            out.append({"who": who, "part": "is the user's", "value": part.replace("_", " "), "ended": bool(l.get("ended"))})
        else:
            out.append({"who": "the user" if who == USER else who, "part": part.replace("_", " "), "value": value,
                        "ended": bool(l.get("ended"))})
    return out


def _later(clock: str) -> str:
    """A minute after a time of day, for the messages the trace keeps no time of."""
    try:
        h, m = map(int, clock.split(":"))
    except ValueError:
        return clock
    m += 1
    return f"{(h + m // 60) % 24:02d}:{m % 60:02d}"


def build(run: Path, speed: float = 1.0) -> dict:
    heard, steps = lines(run / "heard.jsonl"), lines(run / "trace.jsonl")
    gates = [s for s in steps if s["step"] == "gate"]
    by_entry = {}
    for s in steps:
        if s["step"] in ("worth", "read"):
            by_entry.setdefault(s["entry"], {})[s["step"]] = s
    today = json.loads((run / "today.json").read_text()) if (run / "today.json").exists() else {}
    if not today:
        # A live session: the last message of the user's is the request, the agent's reply after it
        # (passed by the plugin's Stop hook) the answer.
        said = [(h["heard"][0]["role"], h["heard"][0]["text"]) for h in heard if h["heard"]]
        last = max((i for i, (role, _) in enumerate(said) if role == "user"), default=None)
        if last is not None:
            reply = next((text for role, text in said[last + 1:] if role != "user"), "")
            today = {"message": said[last][1], "reply": reply}
    journal = {}
    events, day, agent_before = [], None, False
    gi = 0
    order = [s for s in steps if s["step"] in ("gate", "kept")]
    users = [h for h in heard if h["heard"] and h["heard"][0]["role"] == "user"]
    last_user = users[-1]["heard"][0]["text"] if users else ""
    def mark_fast(since: int) -> None:
        # A message that never reached the graph, and the agent's reply to it, go by fast — and the
        # day it opened, when nothing else that day is read.
        for e in events[since:]:
            e["fast"] = True
        if since and events[since - 1]["kind"] == "day":
            events[since - 1]["fast"] = True

    start, clock = 0, "20:00"
    for h in heard:
        m = h["heard"][0] if h["heard"] else None
        if not m:
            continue
        if m["role"] != "user":
            clock = _later(clock)
            # The agent's reply to small talk goes by with it; a question of the agent's opens what
            # comes next, and is read at its pace.
            reply = events and events[-1].get("fast") and (not m["text"].rstrip().endswith("?")
                                                           or " ".join(m["text"].split()) in FILLER_TEXTS)
            events.append({"kind": "say", "role": "agent", "text": m["text"], "time": clock, **({"fast": True} if reply else {})})
            agent_before = True
            continue
        gate = gates[gi] if gi < len(gates) else None
        gi += 1
        # The kept step after this gate, if any.
        at = order.index(gate) if gate in order else -1
        k = order[at + 1] if at >= 0 and at + 1 < len(order) and order[at + 1]["step"] == "kept" else None
        new_day = (k.get("day") or "")[:10] if k else day
        day_before = day
        if new_day and new_day != day:
            day = new_day
            events.append({"kind": "day", "date": day})
        final = m["text"] == last_user and today
        if final:
            events.append({"kind": "mode", "to": "read"})
        start = len(events)
        clock = ((k.get("day") or "")[11:16] if k and new_day != day_before else "") or _later(clock)
        if final:
            clock = today.get("time", "21:14")
        events.append({"kind": "say", "role": "user", "text": m["text"], "time": clock})
        if final:
            break
        events.append({"kind": "gate", "p": gate["personal"] if gate else None, "kept": bool(k)})
        if k is None:
            agent_before = False
            mark_fast(start)
            continue
        if agent_before and gate and " ".join(gate["rewritten"].split()) != " ".join(m["text"].split()):
            events.append({"kind": "resolve", "said": m["text"], "to": gate["rewritten"]})
        else:
            events.append({"kind": "resolve", "skip": True})
        agent_before = False
        n = k["entry"]
        journal[n] = k["text"].split("\n(said:")[0]
        events.append({"kind": "journal", "entry": n, "day": (k.get("day") or "")[:10], "text": journal[n]})
        got = by_entry.get(n, {})
        w = got.get("worth")
        events.append({"kind": "worth", "entry": n, "p": w["p"] if w else None, "read": bool(w and w["read"])})
        r = got.get("read")
        if not r or " ".join(m["text"].split()) in FILLER_TEXTS:
            mark_fast(start)
        if r:
            events.append({"kind": "read", "entry": n, "world": world_items(r["links"]),
                           "topics": [{"name": t["name"], "added": t["added"]} for t in r["topics"]],
                           "portraits": [{"of": p["of"], "added": p["added"]} for p in r["portraits"]]})
    if today:
        recall = next((s for s in reversed(steps) if s["step"] == "recall" and s["message"] == today["message"]), None)
        gathered = "\n".join(recall["gathered"]) if recall else ""
        found = [n for n, text in journal.items() if text[:60] in gathered or text[:40] in gathered]
        who = sorted({name for name in re.findall(r"What the memory knows of ([^(\n]+?) \(", gathered)} - {USER})
        topics = re.findall(r'(?:We discussed this before|Possibly related): "([^"]+)"', gathered)
        events += [{"kind": "search", "entries": found}, {"kind": "world", "who": who + ["the user"]},
                   {"kind": "topic", "names": topics},
                   {"kind": "note", "text": (recall or {}).get("note", "")},
                   {"kind": "say", "role": "agent", "text": today.get("reply", ""), "final": True,
                    "time": _later(today.get("time", "21:14"))}]
    return {"title": run.name, "speed": speed, "events": events}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("run", type=Path)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--speed", type=float, default=1.0, help="the speed it plays at, to fit a video's timing")
    args = parser.parse_args()
    data = build(args.run, args.speed)
    out = args.out or args.run / "replay.html"
    page = TEMPLATE.read_text().replace("/*DATA*/null", json.dumps(data, ensure_ascii=False).replace("</", "<\\/"))
    out.write_text(page)
    print(f"{len(data['events'])} steps → {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
