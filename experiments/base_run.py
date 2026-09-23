"""The same 455 facts against the least a world can be.

    .venv/bin/python experiments/base_run.py --questions 20

Our fixed classes are a guess about what a person's world contains. This run takes the guess
away and leaves the base: somewhere to put a thing, a link with no type yet, the two parties the
world is between, and the calls to name what turns out to have a name. What the host builds on
top of that is the measurement — and what our classes are worth is the difference between this
and a run with them.

The number from the questions comes along, but it is not what this is for. These are:

    how much of what was recorded is prose, which nothing can supersede
    how many entities hold nothing but a name
    how many host runs ended in a refusal, and which
    what vocabulary the host arrived at, and what the world kept asking it for

The host driver, the benchmark data and the grading are `benchmarks/`, imported as they are.
"""
import argparse
import json
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "benchmarks"))

import factconsolidation as fc          # noqa: E402
import host as hosting                  # noqa: E402

from experiments.world_census import census  # noqa: E402

RESULTS = ROOT / "benchmarks" / "results"

PRIMER = """\
This world holds four classes and nothing else: Thing (anything at all — it has a name and \
whatever you say about it), Person, Agent, and Related (a link you have no type for yet). Two \
entities are already in it: world.owner, the person it belongs to, and world.me, you.

Everything else you define as you go:

    world.classes_like("a sport")            — is there already a class for this? Look first.
    world.classes_here()                     — every class this world has now, most used first
    world.anything_like("rugby")             — is there already a thing called this, of any kind?
    Sport = world.define("Sport", "a game people play and follow", identified_by="name")
    world.attribute(Person, "email", "the address they are written to at", type="email")
    world.define_relation("authorship", "who wrote what", nature="related_to",   # or part_of,
                          # kind_of, same_as, derived_from — the five a link can be
                          subject=Person, object=Book,
                          cardinality="one-to-many", over_time=False)

A fact with no class goes in as a Thing. A link needs a type, and the world will not invent \
one for you — say what the link is, then say the fact:

    world.define_relation("created_in", "where a game or a work first came about",
                          nature="related_to", cardinality="many-to-one", over_time=False)
    Thing.ensure(name="pesäpallo").relate(Thing.ensure(name="Finland"), "created_in")

Writing the link before its type raises, and the refusal hands you the exact call to write, so \
the cost of not knowing is one run, not a lost fact. `relate(x, "related", label="created in")` \
is the escape hatch for a link you cannot name at all, and it buys nothing: a labelled free \
link cannot be asked about by type, cannot supersede anything, and the world has nothing to \
check it against. Use it only when there is genuinely no word.

A nature is not a name. `part_of`, `kind_of`, `same_as`, `related_to` say how a link behaves; \
what the link is *called* is the fact's own word. "The capital of France is Paris" is a part_of \
link — Paris is part of France, that much is true — but recorded as `part_of` the word "capital" \
is gone, and the question it answers can no longer be asked. Define the word and give it the \
nature:

    world.define_relation("capital_of", "the city that is a country's seat of government",
                          nature="part_of", cardinality="one-to-one", over_time=False)

The same goes for reaching for a type you defined earlier because it is roughly the area: \
"is a citizen of" is not "is associated with the sport of". One word, one type; a type that \
collects several ideas answers for none of them.

The world says when your word reads like a type already here — it does not swap one for the \
other, because whether two words are one idea depends on what the user said, which you have and \
it does not. If they are one, `world.take_in(<the type>, "<the word>")` moves the links over. \
`world.wanted()` asks what is still untyped. A Thing that turns out to have a name of its own \
joins a class the same way: `thing.become("Sport")`, and nothing it holds is lost.

Two things the world insists on. Every class, attribute and relation type needs a description \
of what it is — that is what a later lookup searches. And `over_time` on a relation has to be \
said: True when a thing has one current holder and a new one ends the last (an employer, a \
spouse), False when they simply accumulate. Without it, asking later gives the first answer you \
were ever told.

How this goes, every time:

    start_task("record what I am about to tell you about X", "recording")
    ... your runs ...
    finish_task

The world answers every fact. It says what it assumed, what it could not tell apart, and what \
it still needs — and it will not let the task close while any of that is still nobody's \
decision. `[undecided N]` on a run is the running count; `world.undecided()` reaches them all \
(they hang on the links you made, not on one entity). Settle each:

    q.answer("...")          you know
    q.for_the_user("...")    you genuinely cannot — it goes to the user and stops blocking
    q.drop("...")            it was never a real doubt, and say why

Handing one to the user is not failing. Guessing at it is.

Time is said, never assumed. A relation that holds one at a time is a relation with a date in \
it, and the world no longer fills that in for you. Say when, in whatever words you have: \
`starts="now"`, `"yesterday"`, `"3 years ago"`, `"in 2006"`, `date(2006, 1, 1)` — or, when all \
you know is which side of something it falls on, `starts=before(now())`, \
`starts=after(date(2006, 1, 1))`. If the fact came with no time at all, say nothing and the \
world records it undated rather than dating it today.

A name you want to keep at hand goes in with `world.pin(x, value, "what it is", keep=False)` \
for this task, or `keep=True` to outlive it. There is no default — the world will not choose \
for you.

Before you record anything, learn what is already here: call `world.classes_here()` for the whole list, \
and `describe_classes([...])` for the ones you are about to use. Do it once, now — what you know \
about this world decides what you build in it.

Three habits that matter more than the modelling you choose:

- **Never write a fact as a sentence to get it in.** Prose cannot be superseded and cannot be \
  searched by value. A Thing with a description is fine; "X is the CEO of Y" as a description \
  is a fact you have lost.
- **Never invent a value to satisfy a required field.** Leave it out. The record cannot tell \
  what you supplied from what the user said.
- **One thing is one thing.** Look before you create, and let one idea have one name."""

RECORD = """\
It is {when}. Here are facts I am telling you, in the order I learned them. Record all of them.

If one of these says something different from what is already recorded about the same thing, \
what I am telling you now is what holds. I am not telling you when it changed — only that this \
is what is true now — so do not write a date you were not given.

If one of them does not fit what you have so far, put it in as a Thing, define the link type \
you need and say it, and carry on. Do not drop it and do not write it out as a sentence.

Say what each Thing is, in one line: `london.describe("the city Thomas Kyd was born in")`, and \
what each link is: `born.describe("Thomas Kyd's birthplace")`. Not for entities of a class that \
already says what they are — a Person called Amy Winehouse is accounted for, and a line about \
her would either be the fact again or something nobody told you. What it is in this world and why it turned up — not what you happen \
to know about it: "the capital city of the United States" is an encyclopaedia entry nobody \
said, "the city Pedro Pierluisi worked in" is the reason it is here. A name is a handle, not an \
account, and this line is the only description of the thing the world did not write itself — so \
it is the only thing it can check its own structure against later. The task will not close \
without it.

When you have recorded them all, settle whatever the world left undecided — `world.undecided()` \
— and then ask `world.wanted()` and define what it keeps asking you for: \
each shape there is a word you have now written several times with no type behind it, always \
between the same two kinds of thing. Define the type, then `world.take_in(<the type>, "<the \
word>")` so the links already written join it. A word left untyped is a question you will not \
be able to answer later.

{facts}"""

ASK = """\
Today is {when}. {question}

Answer from what is recorded, with the value and nothing else. If a thing was recorded more \
than once over time, give the one that holds now, not the first one."""


def start_base_server(db: Path, port: int) -> subprocess.Popen:
    """A world server holding the base and nothing else.

    `benchmarks/host.py` starts the ones the other runners use, and this mode is not its
    business, so it is started here rather than by adding a flag to somebody else's file.
    """
    import urllib.request

    server = subprocess.Popen(
        [sys.executable, "-m", "terraweaver.server", "--db", str(db), "--port", str(port),
         "--base"], cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(120):
        if server.poll() is not None:
            raise RuntimeError(f"base world server on {port} died on startup "
                               f"(exit {server.returncode}) — is the port free?")
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=1)
            return server
        except OSError:
            time.sleep(0.5)
    server.kill()
    raise RuntimeError(f"base world server on {port} didn't answer in a minute")


def vocabulary(db: Path) -> dict:
    """What the host arrived at, read out of the world it built it in."""
    if not db.exists():
        return {}
    conn = sqlite3.connect(db)
    tables = [r[0] for r in conn.execute("select name from sqlite_master where type='table'")]
    return {"classes": sorted(t[len("facts_"):] for t in tables if t.startswith("facts_"))}


def wanted_still(db: Path) -> list:
    """The types the world was still asking for when it stopped — the vocabulary it never got."""
    from terraweaver import relations
    from terraweaver.runtime import WorldRuntime

    try:
        return [{k: v for k, v in shape.items() if k != "links"}
                for shape in relations.free_shapes(WorldRuntime(str(db)).world)]
    except Exception as why:            # noqa: BLE001 - a census must not fail a finished run
        return [{"unread": str(why)[:200]}]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--hops", default="sh", choices=["sh", "mh"])
    parser.add_argument("--context", default="6k")
    parser.add_argument("--model", default="haiku")
    parser.add_argument("--questions", type=int, default=20)
    parser.add_argument("--chunk", type=int, default=25)
    parser.add_argument("--also", default="mh", choices=["sh", "mh", ""],
                        help="a second question set to ask the same world (default: mh)")
    parser.add_argument("--facts", type=int, default=0,
                        help="use only the first N facts — for checking the pipeline cheaply")
    parser.add_argument("--port", type=int, default=7070)
    args = parser.parse_args()

    variant = fc.load(args.hops, args.context)
    if args.facts:
        variant.facts = variant.facts[:args.facts]
    # Both question sets against the one world. They are asked of the same 455 facts, and
    # building the world is nearly all of the hour and nearly all of the money — so asking the
    # multi-hop set as well costs a few minutes and gives a second reading that needs no caveat
    # about the two worlds differing, because there is only one.
    asking = [(args.hops, variant.questions[:args.questions])]
    if args.also and args.also != args.hops:
        asking.append((args.also, fc.load(args.also, args.context).questions[:args.questions]))
    questions = asking[0][1]
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    out_dir = RESULTS / f"{stamp}-base-{variant.name}-{args.model}"
    out_dir.mkdir(parents=True, exist_ok=True)
    config = {"benchmark": variant.name, "ontology": "base — Thing, Related, Person, Agent",
              "facts": len(variant.facts), "questions": len(questions), "chunk": args.chunk,
              "host_model": args.model, "judge": "string match, no model",
              "commit": subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT,
                                       capture_output=True, text=True).stdout.strip(),
              "started": stamp}
    (out_dir / "config.json").write_text(json.dumps(config, indent=2))
    print(json.dumps(config, indent=2), flush=True)

    work = Path(tempfile.mkdtemp(prefix="tw-base-"))
    db = work / "world.db"
    log = out_dir / "host.jsonl"
    server = agent = None
    spent = {"turns": 0, "cost": 0.0}
    started = time.monotonic()
    results = []
    try:
        server = start_base_server(db, args.port)
        agent = hosting.World(work, "base", args.port)

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
            print(f"  {day} ({len(facts)} facts)  {got['turns']} turns  ${spent['cost']:.2f}  "
                  f"classes: {len(built.get('classes', []))}", flush=True)

        asked_on = (last_day + timedelta(days=1)).isoformat()
        for hops, these in asking:
            print(f"  — {hops} —", flush=True)
            for number, question in enumerate(these, 1):
                got = hosting.ask(agent, ASK.format(when=asked_on, question=question.text),
                                  agent.conversation(), None, log, args.model)
                spent["turns"] += got["turns"]
                spent["cost"] += got["cost"]
                right = fc.correct(got["text"], question.gold)
                results.append({"id": question.id, "hops": hops, "question": question.text,
                                "gold": question.gold, "answer": got["text"][:300],
                                "correct": right, "turns": got["turns"],
                                "cost": round(got["cost"], 3)})
                print(f"{'ok ' if right else '   '} {hops} {number:>3}/{len(these)} "
                      f"{question.gold} <- {got['text'][:70].replace(chr(10), ' ')}", flush=True)
    finally:
        if server:
            hosting.stop(server)
        if agent:
            hosting.forget_folder_memory(agent.cwd)

    by_hops = {}
    for hops, these in asking:
        mine = [r for r in results if r["hops"] == hops]
        by_hops[hops] = {"correct": sum(r["correct"] for r in mine), "of": len(mine)}
    # The world is kept beside its results. Building it is the hour and the money; the questions
    # are minutes and pennies, so a saved world is a place to debug readings for nothing — and
    # `fact_by_fact.py` reads it without a model at all.
    kept = out_dir / "world"
    kept.mkdir(exist_ok=True)
    if db.exists():
        shutil.copy(db, kept / "world.db")
        grown = db.parent / "grown"
        if grown.is_dir():
            shutil.copytree(grown, kept / "grown", dirs_exist_ok=True)

    summary = {"accuracy": round(sum(r["correct"] for r in results) / max(1, len(results)), 3),
               "by_hops": by_hops, "questions": len(results), "cost_usd": round(spent["cost"], 2),
               "turns": spent["turns"], "minutes": round((time.monotonic() - started) / 60, 1),
               "world": str(db)}
    built = {"vocabulary": vocabulary(db), "census": census(str(db)) if db.exists() else {},
             "still_wanted": wanted_still(db)}
    (out_dir / "results.json").write_text(json.dumps(
        {"config": config, "summary": summary, "built": built, "runs": results}, indent=2))
    print(json.dumps({**summary, **{k: v for k, v in built.items() if k != "census"}},
                     indent=2, ensure_ascii=False))
    print(json.dumps(built["census"], indent=2, ensure_ascii=False))
    print(out_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
