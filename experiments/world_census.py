"""What a world holds, counted — the grading that needs no model.

A benchmark score mixes two things: what the world kept, and whether the host found it. On
twenty questions the second swamps the first (one sigma is 2.2 questions), so a change that
moves structure is unmeasurable there. These counts move with the structure alone:

    entities holding nothing but a name   — facts that arrived and were dropped
    facts written as prose                — `descriptions`, which nothing can supersede
    links                                 — facts that stayed structured
    host runs that ended in an error      — friction, and where it came from

    .venv/bin/python experiments/world_census.py /tmp/tw-restructured3/world.db
"""
import collections
import json
import re
import sqlite3
import sys

BORING = {"full_name", "name", "title", "created_at", "accessed_at", "valid_from", "valid_until"}


def census(path: str) -> dict:
    db = sqlite3.connect(path)
    named = empty = filled = 0
    slots: collections.Counter = collections.Counter()
    for class_name, in db.execute("SELECT DISTINCT class_name FROM instances"):
        held: dict = collections.defaultdict(dict)
        for instance_id, attr, value in db.execute(
                f'SELECT instance_id, attr, value FROM "{class_name}"'):
            held[instance_id][attr] = value
        for attrs in held.values():
            named += 1
            real = [a for a, v in attrs.items() if a not in BORING and v not in ("null", "[]", None)]
            slots.update(real)
            empty, filled = (empty + 1, filled) if not real else (empty, filled + 1)

    runs = list(db.execute("SELECT error FROM runs"))
    failures: collections.Counter = collections.Counter()
    for (error,) in runs:
        if not error:
            continue
        last = error.strip().splitlines()[-1]
        failures[re.sub(r"'[^']*'", "'…'", last)[:70]] += 1
    return {"entities": named, "name_only": empty, "with_content": filled,
            "slots": dict(slots.most_common(10)),
            "runs": len(runs), "failed": sum(failures.values()),
            "failures": dict(failures.most_common(8))}


if __name__ == "__main__":
    for world in sys.argv[1:]:
        print(f"--- {world}")
        print(json.dumps(census(world), ensure_ascii=False, indent=2))
