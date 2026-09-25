"""Experiment zero: a world with no classes, and a host left to invent them.

    .venv/bin/python benchmarks/run_blank.py --questions 20        # the FactConsolidation slice

The world starts with the mechanism and no vocabulary: define a class with a description, declare
an attribute, define a relation type with its cardinality and whether it holds one at a time,
and two calls for looking before inventing. Everything else is the world as usual — statements
with sources, periods, history, identity questions, tags, meaning, rebuild.

Then the same 455 facts and the same 20 questions our fixed classes answered 12/20, so that what
the host invents has a number beside it. The number is not the point. What is the point: how many
classes it defines, how many are the same idea twice, whether the vocabulary converges as the
batches go by, and what it declares functional in time — because that last one is what makes
"who is it now" answerable at all.
"""
import argparse
import json
import sqlite3
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import factconsolidation as fc
import host as hosting

ROOT = Path(__file__).resolve().parent.parent
RESULTS = ROOT / "benchmarks" / "results"

PRIMER = """\
This world starts empty: it has no classes at all. You decide what kinds of things exist in it \
and what they are called, as you go.

What you can do:

    world.classes_like("a sport")         — is there already a class for this? Look before inventing.
    world.attributes_like("spoken language") — attributes that already mean roughly this.
    world.anything_like("rugby")          — is there already a thing called this, of any kind?
    Position = world.define("Position", "a role a player occupies in a team sport",
                            identified_by="name")
    world.attribute(Position, "sport", "the sport this position belongs to")
    world.define_relation("heads", "who currently leads an organisation",
                          subject=Person, object=Organization,
                          cardinality="one-to-many")

Two things the world insists on. Every class, attribute and relation type needs a description of \
what it is — that is what a later lookup searches. And an attribute for something that can \
change must be a value, not free text: several tellings of prose sit side by side and none of \
them replaces the others, so "what is it now" stops having an answer.

`cardinality` on a relation has to be said, and it is about **one moment**: "many-to-one" when \
this thing has one of those at a time (an employer, a spouse, a citizenship somebody changes) and \
a new one ends the last, "one-to-many" when it is the other end that has one, "many-to-many" when \
they simply accumulate. Get it wrong one way and asking later gives back the first answer you were \
ever told; wrong the other way and hiring somebody ends the last person's job.

Three habits that matter more than the modelling you choose:

- **When something does not fit, extend the vocabulary — never squeeze it.** A fact you cannot \
  place is a class or a relation type you have not defined yet. Writing it as prose in a \
  description, or skipping it, loses it: prose cannot be superseded and cannot be searched by \
  value.
- **Look before you invent, every time.** One idea should be one class and one name.
- **One thing is one thing.** Before creating something, `world.anything_like("its name")` — \
  the same word becoming four kinds of thing makes every answer about it wrong.

After defining, it is an ordinary world: Class.ensure(...), a.relate(b, "kind"), periods, \
history, comments. Say what you need and build as you go — nothing is waiting for you."""

RECORD = """\
It is {when}. Here are facts I am telling you, in the order I learned them. Record all of them, \
defining whatever classes and relation types you need as you go. Look before you invent: if a \
class or an attribute for something already exists, use it rather than making a second word for \
the same idea.

If one of these says something different from what is already recorded about the same thing, \
what I am telling you now is what holds, and the earlier one stopped holding today.

If one of them does not fit anything you have defined, define what it needs — a class, an \
attribute or a relation type — rather than dropping it or writing it into a description.

{facts}"""

ASK = """\
Today is {when}. {question}

Answer from what is recorded, with the value and nothing else. If a thing was recorded more than \
once over time, give the one that holds now, not the first one."""


def vocabulary(db: Path) -> dict:
    """What the host built, read out of the world it built it in.

    Besides the list of classes, one ratio per class: how much of what was said about its
    instances went into free text against how much went into declared values. Counting the shape
    of what was recorded is the deterministic version of "this host is writing prose where a
    value belongs" — no sentence is read, and a class high on this list is a class missing an
    attribute.
    """
    if not db.exists():
        return {}
    conn = sqlite3.connect(db)
    tables = [r[0] for r in conn.execute("select name from sqlite_master where type='table'")]
    classes = sorted(t[len("facts_"):] for t in tables if t.startswith("facts_"))
    counts, prose = {}, {}
    for name in classes:
        try:
            counts[name] = conn.execute(f'select count(*) from "facts_{name}"').fetchone()[0]
            said = conn.execute(
                'select sum(slot in (\'descriptions\', \'notes\', \'description\')), count(*) '
                f'from "facts_{name}"').fetchone()
            if said and said[1]:
                prose[name] = round((said[0] or 0) / said[1], 2)
        except sqlite3.Error:
            counts[name] = 0
    return {"classes": classes, "statements_per_class": counts,
            "share_written_as_prose": dict(sorted(prose.items(), key=lambda kv: -kv[1]))}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--hops", default="sh", choices=["sh", "mh"])
    parser.add_argument("--context", default="6k")
    parser.add_argument("--model", default="haiku")
    parser.add_argument("--questions", type=int, default=20)
    parser.add_argument("--chunk", type=int, default=25)
    parser.add_argument("--port", type=int, default=7060)
    args = parser.parse_args()

    variant = fc.load(args.hops, args.context)
    questions = variant.questions[:args.questions]
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    out_dir = RESULTS / f"{stamp}-blank-{variant.name}-{args.model}"
    out_dir.mkdir(parents=True, exist_ok=True)
    config = {"benchmark": variant.name, "ontology": "blank — the host defines it",
              "facts": len(variant.facts), "questions": len(questions), "chunk": args.chunk,
              "host_model": args.model, "judge": "string match, no model",
              "commit": subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT,
                                       capture_output=True, text=True).stdout.strip(),
              "self_reported": True, "started": stamp}
    (out_dir / "config.json").write_text(json.dumps(config, indent=2))
    print(json.dumps(config, indent=2), flush=True)

    work = Path(tempfile.mkdtemp(prefix="tw-blank-"))
    db = work / "world.db"
    log = out_dir / "host.jsonl"
    server = agent = None
    spent = {"turns": 0, "cost": 0.0}
    started = time.monotonic()
    results = []
    try:
        server = hosting.start_server(db, args.port, blank=True)
        agent = hosting.World(work, "blank", args.port)

        got = hosting.ask(agent, PRIMER, agent.conversation(), None, log, args.model)
        spent["turns"] += got["turns"]
        spent["cost"] += got["cost"]
        print(f"  primer: {got['turns']} turns  ${got['cost']:.2f}", flush=True)

        last_day = None
        for day, facts in variant.batches(args.chunk):
            last_day = day
            listed = "\n".join(f"- {fact}" for fact in facts)
            got = hosting.ask(agent, RECORD.format(when=day.isoformat(), facts=listed),
                              agent.conversation(), None, log, args.model)
            spent["turns"] += got["turns"]
            spent["cost"] += got["cost"]
            built = vocabulary(db)
            print(f"  {day} ({len(facts)} facts)  {got['turns']} turns  "
                  f"${spent['cost']:.2f}  classes: {len(built.get('classes', []))}", flush=True)

        asked_on = (last_day + timedelta(days=1)).isoformat()
        for number, question in enumerate(questions, 1):
            got = hosting.ask(agent, ASK.format(when=asked_on, question=question.text),
                              agent.conversation(), None, log, args.model)
            spent["turns"] += got["turns"]
            spent["cost"] += got["cost"]
            right = fc.correct(got["text"], question.gold)
            results.append({"id": question.id, "question": question.text, "gold": question.gold,
                            "answer": got["text"][:300], "correct": right})
            print(f"{'ok ' if right else '   '} {number:>3}/{len(questions)} {question.gold} "
                  f"<- {got['text'][:80].replace(chr(10), ' ')}", flush=True)
    finally:
        built = vocabulary(db)
        if server:
            hosting.stop(server)
        if agent:
            hosting.forget_folder_memory(agent.cwd)

    summary = {"accuracy": round(sum(r["correct"] for r in results) / max(1, len(results)), 3),
               "questions": len(results), "classes_defined": len(built.get("classes", [])),
               "vocabulary": built, "cost_usd": round(spent["cost"], 2),
               "turns": spent["turns"], "minutes": round((time.monotonic() - started) / 60, 1),
               "world": str(db)}
    (out_dir / "results.json").write_text(json.dumps(
        {"config": config, "summary": summary, "runs": results}, indent=2))
    print(json.dumps(summary, indent=2))
    print(out_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
