"""The first batch of facts, given to a recorder agent as a task.

Not a benchmark: no questions are asked and nothing is scored. The point is to watch one agent
take a task, record facts into a base world, and settle what the world raises about them — the
exchange that every measurement afterwards rests on. Its whole dialogue is kept, because the
thing being looked at is what the agent and the world said to each other.

    .venv/bin/python experiments/first_batch.py --facts 10
"""
import argparse
import json
import re
import sqlite3
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "benchmarks"))

import factconsolidation as fc              # noqa: E402
import host as hosting                      # noqa: E402

from experiments.base_run import PRIMER, RECORD, start_base_server  # noqa: E402

RESULTS = ROOT / "experiments" / "results" / "batches"


def census(db: Path) -> dict:
    """What is in the world, in the few numbers that say whether it was built or filled."""
    conn = sqlite3.connect(db)
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    # Image tables are key-value — one row per attribute, not per entity. Counting rows here
    # reported a hundred people from ten facts and made the first run unreadable.
    def count(t):
        if t not in tables:
            return 0
        if t.startswith("facts_") or t in ("runs", "questions"):
            return conn.execute(f"SELECT count(*) FROM '{t}'").fetchone()[0]
        return conn.execute(f"SELECT count(DISTINCT instance_id) FROM '{t}'").fetchone()[0]
    grown = sorted(t for t in tables
                   if not t.startswith(("facts_", "reasoning_", "sqlite_"))
                   and t not in {"instances", "values_", "comments", "runs", "questions", "texts",
                                 "periods", "said", "subjects", "meanings", "name_choices",
                                 "entity_access", "value_history", "world_variables", "procedures",
                                 "self_files", "Thing", "Person", "Agent", "Related", "Task"})
    return {
        "things": count("Thing"), "people": count("Person"), "free links": count("Related"),
        "typed links": sum(count(t) for t in grown), "types made": len(grown),
        "statements": sum(count(t) for t in tables if t.startswith("facts_")),
        "questions open": conn.execute(
            "SELECT count(*) FROM questions WHERE closed_at IS NULL").fetchone()[0]
        if "questions" in tables else 0,
        "undecided": conn.execute(
            "SELECT count(*) FROM questions WHERE closed_at IS NULL AND put_to_user_at IS NULL"
        ).fetchone()[0] if "questions" in tables else 0,
        "runs": count("runs"), "tasks": count("Task"),
    }


def fact_by_fact(db: Path, facts: list[str]) -> list[tuple]:
    """Each fact against what the world holds for it: (fact, verdict, what is there).

    Counting types and links said the last run was a success; reading it fact by fact said one
    in ten had been recorded as something else. Aggregates cannot see that, and only this can,
    so it runs every time rather than when somebody thinks to look.
    """
    conn = sqlite3.connect(db)
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}

    def rows(table):
        out: dict = {}
        for iid, attr, value in conn.execute(f"SELECT instance_id, attr, value FROM '{table}'"):
            out.setdefault(iid, {})[attr] = value
        return out

    # Every entity class, not a list of three. The agent builds its own — City, Continent,
    # Organization, Position — and a check that only reads Thing and Person cannot find London
    # in a world that holds it, then reports the fact missing. A table is a relation when it
    # holds subjects and objects; everything else is a kind of thing.
    plumbing = {"instances", "values_", "comments", "runs", "questions", "texts", "periods",
                "said", "subjects", "meanings", "name_choices", "entity_access", "value_history",
                "world_variables", "procedures", "self_files", "Task"}
    entity_tables, link_tables = [], []
    for table in sorted(tables):
        if table in plumbing or table.startswith(("facts_", "reasoning_", "sqlite_", "idx_")):
            continue
        held = {a for _, a, _ in conn.execute(f"SELECT * FROM '{table}' LIMIT 0") or []}
        attrs_here = {r[0] for r in conn.execute(f"SELECT DISTINCT attr FROM '{table}'")}
        (link_tables if {"subject", "object"} <= attrs_here else entity_tables).append(table)

    names: dict = {}
    for table in entity_tables:
        for iid, held in rows(table).items():
            raw = (held.get("name") or held.get("full_name") or held.get("title"))
            if raw:
                names[iid] = json.loads(raw) if raw.startswith('"') else raw

    def ref(raw):
        if not raw:
            return None
        value = json.loads(raw)
        return value.get("$ref") if isinstance(value, dict) else value

    links = []          # (subject name, type, object name)
    for table in link_tables:
        for held in rows(table).values():
            if "subject" not in held:
                continue
            label = json.loads(held["label"]) if held.get("label") else ""
            kind = f"{table}[{label}]" if label else table
            links.append((names.get(ref(held.get("subject"))), kind,
                          names.get(ref(held.get("object")))))

    known = sorted((n for n in names.values() if n), key=len, reverse=True)
    checked = []
    for fact in facts:
        # Longest first, and each match claims the characters it covers, so "Coco Chanel" takes
        # its own span and "Chanel" is still found at the other place it occurs. Skipping every
        # name contained in one already matched lost the shorter of two overlapping names
        # entirely — "Chanel was founded by Coco Chanel" read as one entity, and the fact was
        # reported missing from a world that held it.
        mentioned, taken = [], []
        low = fact.lower()
        for name in known:
            start = 0
            while True:
                at = low.find(name.lower(), start)
                if at < 0:
                    break
                span = (at, at + len(name))
                if not any(a < span[1] and span[0] < b for a, b in taken):
                    taken.append(span)
                    if name not in mentioned:
                        mentioned.append(name)
                    break
                start = at + 1
        if len(mentioned) < 2:
            checked.append((fact, "MISSING", f"only found: {', '.join(mentioned) or 'nothing'}"))
            continue
        a, b = mentioned[0], mentioned[1]
        hit = [l for l in links if {l[0], l[2]} == {a, b}]
        if not hit:
            checked.append((fact, "NO LINK", f"{a} / {b} are both there, nothing joins them"))
        else:
            subject, kind, obj = hit[0]
            shown = f"{subject} --{kind}--> {obj}"
            wanted = _which_way(fact, mentioned)
            if wanted and (subject, obj) != wanted:
                # Both ends right, the word right, and the sentence backwards. The world reads
                # a.relate(b, k) as "a is b's k", so this world says "Fatah is Mahmoud Abbas's
                # chairperson" — and it printed exactly that, and nobody read it.
                checked.append((fact, "WAY", f"{shown}  — reads backwards; the fact says "
                                             f"{wanted[0]} is {wanted[1]}'s"))
                continue
            said = _said_word(fact, mentioned)
            spelt = kind.lower().replace("_", "").replace("[", " ").replace("]", "")
            if said and not any(w[:5] in spelt for w in said):
                # A link between the right two things can still say the wrong thing. "The
                # director of the BBC" went in as ChairpersonOf and every count said the run
                # was clean, because a count cannot read.
                checked.append((fact, "WORD", f"{shown}  — the fact says "
                                              f"'{' '.join(said)}'"))
            else:
                checked.append((fact, "ok", shown))
    return checked


# "The chairperson of Fatah is Mahmoud Abbas" names the role first, the thing it belongs to
# second, and the holder last — so the holder is the subject. It is the one sentence shape in
# this material where the direction is not a matter of taste, which makes it the one worth
# checking automatically.
_ROLE_FIRST = re.compile(r"^The\s+(?P<role>[\w\s]+?)\s+of\s+(?P<whose>.+?)\s+is\s+(?P<who>.+?)\.?$",
                         re.IGNORECASE)


def _which_way(fact: str, names: list[str]) -> tuple | None:
    """(subject, object) the fact calls for, when its shape says so plainly."""
    hit = _ROLE_FIRST.match(fact.strip())
    if not hit:
        return None
    whose, who = hit.group("whose").strip(), hit.group("who").strip().rstrip(".")
    match = lambda text: next((n for n in names if n.lower() in text.lower()
                               or text.lower() in n.lower()), None)
    subject, obj = match(who), match(whose)
    if not (subject and obj and subject != obj):
        return None
    # "... is Mahmoud Abbas" names the holder; "... is located in Minneapolis" names a place
    # and a second verb, and the role is the headquarters rather than somebody holding office.
    # The difference is whether anything survives taking the name out of what follows "is".
    left = re.sub(re.escape(subject), "", who, flags=re.IGNORECASE).strip(" .,")
    return (subject, obj) if len(left) <= 2 else None


_NOT_THE_WORD = {"the", "of", "is", "a", "an", "in", "at", "to", "was", "were", "and", "city",
                 "continent", "country", "state", "for", "by", "on", "with", "it", "its", "this"}


def _said_word(fact: str, names: list[str]) -> list[str]:
    """The words of the fact that are neither the two things nor grammar — what it calls the link."""
    text = fact
    for name in names:
        text = re.sub(re.escape(name), " ", text, flags=re.IGNORECASE)
    words = [w for w in re.findall(r"[A-Za-z]+", text.lower()) if w not in _NOT_THE_WORD]
    return words


def tasks_of(db: Path) -> list[tuple]:
    """How each task the agent opened ended — the one thing it cannot fake."""
    conn = sqlite3.connect(db)
    rows = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='Task'").fetchall()
    if not rows:
        return []
    held: dict = {}
    for iid, attr, value in conn.execute("SELECT instance_id, attr, value FROM 'Task'"):
        held.setdefault(iid, {})[attr] = value
    return [(t.get("stated"), t.get("mode"), t.get("runs"), t.get("closed_as"))
            for t in held.values()]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--facts", type=int, default=10, help="how many to give it")
    parser.add_argument("--from", dest="start", type=int, default=1,
                        help="the first fact, counting from 1")
    parser.add_argument("--into", type=Path, default=None,
                        help="a run directory to carry on in, so the world already holds what "
                             "the last batch put there")
    parser.add_argument("--model", default="haiku")
    parser.add_argument("--port", type=int, default=7093)
    args = parser.parse_args()

    every = fc.load("sh", "6k").facts
    facts = every[args.start - 1: args.start - 1 + args.facts]
    if args.into:
        # The same world, one batch after another: the only way to see whether a type made for
        # the first batch is reused by the second or written again under another name.
        # Absolute: the host runs in a folder of its own and resolves the MCP config path
        # against it, so a relative one becomes <host folder>/<relative path> and is not found.
        work = args.into.resolve()
        work.mkdir(parents=True, exist_ok=True)
    else:
        work = RESULTS / f"{datetime.now():%Y%m%d-%H%M%S}-{args.facts}facts-{args.model}"
        work.mkdir(parents=True, exist_ok=True)
    db, log = work / "world.db", work / "dialogue.jsonl"
    carried = census(db) if db.exists() else None

    print(f"facts {args.start}-{args.start + len(facts) - 1} to a recorder agent ({args.model}).")
    if carried:
        print(f"carrying on in a world that already holds {carried['typed links']} typed link(s) "
              f"in {carried['types made']} type(s).")
    print(f"kept in {work}\n", flush=True)
    for i, fact in enumerate(facts, 1):
        print(f"  {i:>2}. {fact}")
    print(flush=True)

    server = agent = None
    spent = {"turns": 0, "cost": 0.0}
    started = time.monotonic()
    try:
        server = start_base_server(db, args.port)
        agent = hosting.World(work, "batch", args.port)

        primed = hosting.ask(agent, PRIMER, agent.conversation(), None, log, args.model)
        spent["turns"] += primed["turns"]; spent["cost"] += primed["cost"]
        print(f"primer: {primed['turns']} turns, ${primed['cost']:.2f}", flush=True)

        listed = "\n".join(f"- {fact}" for fact in facts)
        told = hosting.ask(agent, RECORD.format(when="a day I am not telling you", facts=listed),
                           agent.conversation(), None, log, args.model)
        spent["turns"] += told["turns"]; spent["cost"] += told["cost"]
        print(f"recording: {told['turns']} turns, ${told['cost']:.2f}", flush=True)
        print("\n--- what the agent said at the end:")
        print((told["text"] or "").strip()[:1200])
    finally:
        if server:
            hosting.stop(server)
        if agent:
            hosting.forget_folder_memory(agent.cwd)

    print("\n--- the world it built")
    for name, number in census(db).items():
        print(f"  {name:<16} {number}")
    print("\n--- each fact against what the world holds")
    verdicts = fact_by_fact(db, facts)
    for number, (fact, verdict, what) in enumerate(verdicts, args.start):
        mark = "OK  " if verdict == "ok" else f"{verdict:<4}"
        print(f"  {mark} {number:>2}. {fact[:52]:<54} {what[:70]}")
    wrong = [v for v in verdicts if v[1] != "ok"]
    print(f"  — {len(verdicts) - len(wrong)}/{len(verdicts)} joined; "
          f"read the types above: a link can be there and still say the wrong thing.")

    print("\n--- the tasks it opened")
    for stated, mode, runs, closed in tasks_of(db) or [("(none opened)", "", "", "")]:
        print(f"  {str(stated)[:60]:<62} {mode} runs={runs} closed={closed}")
    print(f"\n{spent['turns']} turns, ${spent['cost']:.2f}, "
          f"{(time.monotonic() - started) / 60:.1f} min")
    print(f"dialogue: {log}")
    (work / "census.json").write_text(json.dumps(census(db), indent=2))
    if carried:
        after = census(db)
        print("\n--- what this batch added")
        for name in ("things", "people", "typed links", "types made", "free links"):
            before, now = carried.get(name, 0), after.get(name, 0)
            print(f"  {name:<14} {before} -> {now}  ({now - before:+d})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
