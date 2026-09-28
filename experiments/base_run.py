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
A world is made of three kinds of thing, and this one starts with the least of each: \
**entities** — Thing (anything that *is*: a city, a book, a sport) and Person, which is a kind \
of Thing; **links** between them; and **events** — Event, the one kind whose time is part of \
what it is. Also Agent, which is you. Two entities are already here: `world.owner`, the person \
it belongs to, and `world.me`, you.

**First, settle who you are talking about.** Once per thing the user names, before you record \
anything about it:

    paris = Thing.identify(name="Paris")[0]
    anna  = Person.identify(full_name="Anna Weber")[0]

It hands back who in this world could be meant, best first, and you choose — you have the \
conversation and it does not: read them against what the user said about who they mean. \
Nobody here of that name and it records them, so it is one call and never two. Then say everything else about the variable.

**Three things you can tell this world, and it does something different with each.** Most of \
what has gone wrong here was a fact put into the wrong one:

    a.relate(b, "...")           what joins two things, in the words the fact came in
    thing.describe("...")        what one thing is, and why it is here
    thing.attribute = value      a value of one thing — never another thing

**A link is said as a fact, in the words it came in.**

    paris.relate(france, "Paris is the capital of France")
    anna.relate(acme, "Anna has been an employee of Acme since 2019")

Two things handed over and the fact stated plainly. Nothing else to decide: no role, no \
argument order to get right, no date as a separate thing. The fact is in the world the moment \
you say it.

Afterwards it reads back under a word of its own, and the words this world already has are on \
the things themselves — to say and to read:

    paris.set_capital_of(france)        stating it — always one link at a time
    paris.capital_of      -> France     a value, where only one can hold
    anna.mother_of        -> [Boris]    a list, where several can

Never `paris.capital_of = france`: that slot is how the link reads back, not how it is written.

**Direction reads back, so read it back.** `a.set_<word>(b)` says a is the one the word is \
about, and the world hands you the sentence it made:

    kyd.set_born_in(london)   ->  "Thomas Kyd born in London"

Check that sentence, not a translation of it. A host that turned it into "Thomas Kyd is \
London's born_in" — which is not English and not what the world said — decided its correct \
links were backwards, expired them, and wrote them the other way round.

**State it, do not hint at it.** Nothing here works out what you meant from a narrative. You \
know what the user said, so say it outright:

    kyd.relate(london, "Thomas Kyd was born in London")     say it
    kyd.relate(london, "that is where he is from")          a riddle

**And it must be a fact about the two of them.** What one thing is *like* — "Anna is tall" — is \
a value and belongs on the thing. What a thing *is* — "Paris is a city" — is its class, and you \
do not have to name it: say it in words on the thing itself.

**A thing you have just recorded is only a name.** Say what it is, in your own words, and the \
world gives it a class when the task closes — it finds one or makes one, and fills in what your \
words gave:

    paris.describe("Paris is the capital of France, where the user lived until 2019")

If you forget, every run hands you the line to run next, with your own variable in it. That is \
a question about the work, not a complaint: answer it by describing the thing, and it closes \
itself.

**An event is the one thing that needs a time.** `Event.new(title=..., start_time=...)` — an \
event without a when is not an event. Nothing else is asked for a date: a capital, a language, \
an employer needs no beginning, and a later telling supersedes an earlier one without one. Say \
`starts=` when the user gave a date, and nothing at all when there is nothing to say.

**Writing a value nobody declared is fine** — it is taken and kept. Before the task closes \
you are asked what the word means and whether a later telling replaces it, because neither can \
be read off a value. Answer then; what you wrote stays.

**Ask rather than guess.** Everything here says what it is, and asking is cheap beside a turn \
spent undoing a guess:

    world.classes_here()                 every class there is now, most used first
    describe_classes(["Person"])         its attributes, its methods, the words it is linked by
    describe_methods(["describe"])       what one call does, in full, with examples
    world.anything_like("rugby")         is there already a thing called this, of any kind

The words this world has for links are on the things themselves, and `describe_classes` shows \
them. If you find none there for what the user told you, that is not a problem to solve: say \
the fact in words and it is recorded.

How this goes, every time:

    start_task("record what I am about to tell you about X", "recording")
    ... your runs ...
    finish_task

The world answers every fact: what it assumed, what it could not tell apart, what it still \
needs. It will not close the task while any of that is nobody's decision. `[undecided N]` is \
the running count and `world.undecided()` reaches them all:

    q.answer("...")          you know
    q.for_the_user("...")    you genuinely cannot — it goes to the user and stops blocking
    q.drop("...")            it was never a real doubt, and say why

Handing one to the user is not failing. Guessing at it is.

Time is yours to say, because it is in what the user told you and nowhere here. In whatever \
words you have: `starts="in 2006"`, `"3 years ago"`, `date(2006, 1, 1)`, or `starts=now()` when \
it is simply now. Came with no time at all — say nothing, and it is recorded undated rather \
than dated today.

Three habits that matter more than any modelling you choose:

- **Never write a fact as a sentence on one thing to get it in.** "X is the CEO of Y" as a \
  description is a fact nothing can supersede and nothing can find. It is a link: say it as one.
- **Never invent a value to satisfy a field.** Leave it out. The record cannot tell what you \
  supplied from what the user said.
- **One thing is one thing.** Settle who you mean first, and let one idea have one name.
"""


ONE_DOOR = """\
A world is made of three kinds of thing: **entities** — Thing (anything at all) and Person; \
**events** — Event, the one kind whose time is part of what it is; and the **links** between \
them. Two entities are already here: world.owner, the person it belongs to, and world.me, you.

**Three things you can tell this world, and it does something different with each.**

    a.relate(b, "...")           what joins two things, in the words it came in
    a.set_<word>(b)              the same, where this world already has the word
    thing.describe("...")        what one thing is, and why it is here
    thing.attribute = value      what a thing's value is — never a thing

**A fact about two things goes through link, and you say it plainly:**

    anna = Person.new(full_name="Anna Weber")
    acme = Thing.ensure(name="Acme", nature="agent")
    anna.relate(acme, "Anna has been an employee of Acme since 2019")

Two things and the fact in words. You do not choose a type, a role, an order of ends, or a \
date as a separate thing — say it as the user said it, including when, and the rest is worked \
out. The two things you must give, because only you know which Anna is meant.

**State it, do not hint at it.** Nothing here works out what you meant from a narrative. You \
know what the user said, so say it outright — the relation named, both things in it, and the \
date if there was one:

    kyd.relate(london, "Thomas Kyd was born in London")             say it
    kyd.relate(london, "that is where he is from")                  a riddle

`is` is a good word for it: "Paris is the capital of France", "Anna is Boris's mother". What \
is not good is leaving out the thing the fact turns on.

**And it must be about the two of them.** What one thing is *like* — "Anna is tall" — is a \
value: `anna.height = "tall"`. What a thing *is* — "Paris is a city" — is its class or its \
nature. Put either through relate and it is kept, but as a link with no type, which cannot \
supersede anything and cannot be asked about.

**What a link becomes, so you can read it back.** A link joins two things and each end has a \
role — in "Paris is the capital of France" one end is the capital and the other the country. \
You do not name the roles; the world works them out from what you said. What they buy is this:

    paris.capital_of      ->  France          each end reads by its own role
    france.capital        ->  Paris           and the far end by the other
    anna.employee_of      ->  Acme            one at a time, so it is one thing
    anna.mother_of        ->  [Boris, Vera]   several at once, so it is a list

One thing or a list is not something anybody declares: it is how many may hold **at one \
moment**. One employer now and many over a life is one; several children at once is many.

**A later telling does not erase an earlier one.** Say Anna works somewhere else and the first \
stops holding where the second starts — both stay, each true in its turn, and "where does she \
work" answers with the one that holds. With no date given, the first is marked as ended \
without a day, because nobody said which day.

**Say the same fact the same way and it joins the same relation.** Two words for one idea is \
what to avoid: a world holding both "chair" and "chairperson" answers for neither. The world \
says when your words read like something it already has.

An attribute no class has is taken as you write it, with its type guessed from the value; \
before the task closes the world asks what it means and whether a later telling replaces it. \
The values you wrote stay either way.

**Say what each thing is, in one line.** `london.describe("the city Thomas Kyd was born in")` — \
what it is in this world and why it turned up, not what you happen to know about it. "the \
capital city of the United States" is an encyclopaedia entry nobody said; "the city Pedro \
Pierluisi worked in" is the reason it is here. The task will not close without it.

**How this goes, every time:**

    start_task("record what I am about to tell you about X", "recording")
    ... your runs ...
    finish_task()

The world answers every fact: what it assumed, what it could not tell apart, what it noticed. \
Read what comes back. When it leaves a question, settle it — `q.answer("...")` when you know, \
`q.for_the_user("...")` when you genuinely cannot. Handing one to the user is not failing; \
guessing at it is.

Time is yours to say, because it is in what the user told you. Say it in the words they used \
and the world will read it. Nothing is dated that nobody dated.

Before you record anything, see what is here: `world.classes_here()` for the classes, \
`world.anything_like("Paris")` for whether a thing is already in. A second Anna made because \
nobody looked is the one mistake no later telling repairs."""


RECORD = """\
It is {when}. Here are facts I am telling you, in the order I learned them. Record all of them.

If one of these says something different from what is already recorded about the same thing, \
what I am telling you now is what holds. I am not telling you when it changed — only that this \
is what is true now — so do not write a date you were not given.

If one of them does not fit what you have so far, put it in as a Thing, define the link type \
you need and say it, and carry on. Do not drop it and do not write it out as a sentence.

A description says what the thing is; a sentence naming something *else* is a link, and the \
world will not close the task until you have written it as one. "Tokyo is the capital of Japan" \
is not a description of Tokyo — it is a fact about Tokyo and Japan, and in a description it is \
text: nothing contradicts it, nothing counts it, no question finds it. Say it as the fact it \
is — `a.relate(b, "...")` — and the word for it is found here afterwards.

Say what each Thing is, in one line, and say it about the thing itself: \
`london.describe("a city in England, the one the user keeps coming back to")`. What it is to \
something else is a link and belongs in one; put it here and the same fact goes in twice, from \
two ends, under two words. Not for entities of a class that \
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


def _the_key() -> bool:
    """Put every key where a child process will find it, from the places they are kept here.

    Returns whether there is an engineer to be had, which is what the callers ask about — but it
    loads them all, because the other one matters just as much and reading only `NEBIUS_API_KEY`
    was how the reading went on asking the engineer its closed questions long after the server had
    been given a decision model. Nothing in `terraweaver` reads `.env`; a key reaches a world from
    whoever started it, and this is that place for everything under `experiments/`.
    """
    import os

    for env in (ROOT / ".env", Path(os.path.expanduser("~/Projects/ai-safity/.env"))):
        if not env.exists():
            continue
        for line in env.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            name, value = line.split("=", 1)
            name, value = name.strip(), value.strip().strip('"')
            if value and not os.environ.get(name):
                os.environ[name] = value
    return bool(os.environ.get("NEBIUS_API_KEY"))


def start_base_server(db: Path, port: int, one_door: bool = False) -> subprocess.Popen:
    """A world server holding the base and nothing else.

    `benchmarks/host.py` starts the ones the other runners use, and this mode is not its
    business, so it is started here rather than by adding a flag to somebody else's file.
    """
    import urllib.request

    # The served world reads what a host says in words only when it has somebody to read with,
    # and it takes that from its environment (`server._with_a_reader`). Started without the key,
    # it says nothing and simply does not read — and a run then measures the door that is still
    # switched on while looking like a measurement of the one that is not. That happened once,
    # for ten facts and eleven minutes, and every sentence in that world came back unread.
    told = _the_key()
    if not told:
        print("!! NEBIUS_API_KEY is not set, so this world has no engineer: nothing said in "
              "words will be read into a link. What this run measures is the other door.",
              flush=True)

    server = subprocess.Popen(
        [sys.executable, "-m", "terraweaver.server", "--db", str(db), "--port", str(port),
         ] + (["--one-door"] if one_door else []),
        cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
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
