"""Was each fact recorded the way it was told, and does the later one win?

The benchmark's own design does the hard part: every fact is a templated sentence, and where a
subject is spoken of twice the sentences differ only in the value at the end. So the frame —
everything up to that value — identifies what is being said about whom, and the last value given
is what should hold when the world is asked.

This reads the built world and answers three questions with no model in the loop:

    recorded      is the value anywhere in the world at all
    current       does the world hold the *last* value as the one that holds now
    stale         does it still hold an earlier one as current

    .venv/bin/python experiments/fact_by_fact.py <world.db> [--hops sh]
"""
import argparse
import collections
import json
import re
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "benchmarks"))

import factconsolidation as fc  # noqa: E402

VALUE = re.compile(r"^(.*\b(?:of|in|to|by|is|are)\s)(.+?)\.?$")


def frames(facts: list[str]) -> dict:
    """{what is said about whom: [values, in the order they were said]}."""
    said: dict = collections.defaultdict(list)
    for fact in facts:
        got = VALUE.match(fact)
        if got:
            said[got.group(1).strip()].append(got.group(2).strip())
    return said


def world_values(db: Path) -> tuple[dict, dict]:
    """Every name in the world, and for each entity the values that hold now and ever.

    Read from the image, which is where "now" lives: a link whose period has ended is not in it.
    """
    conn = sqlite3.connect(db)
    names, holds, ever = {}, collections.defaultdict(set), collections.defaultdict(set)
    per_class: dict = {}
    for class_name, in conn.execute("SELECT DISTINCT class_name FROM instances"):
        rows: dict = collections.defaultdict(dict)
        for instance_id, attr, value in conn.execute(
                f'SELECT instance_id, attr, value FROM "{class_name}"'):
            try:
                value = json.loads(value)
            except Exception:                  # noqa: BLE001 - unreadable is not a value
                pass
            rows[instance_id][attr] = value
        per_class[class_name] = rows
        for instance_id, row in rows.items():
            for key in ("full_name", "name", "title"):
                if isinstance(row.get(key), str):
                    names[instance_id] = row[key]
                    break
    for class_name, rows in per_class.items():
        for instance_id, row in rows.items():
            subject, obj = row.get("subject"), row.get("object")
            if isinstance(subject, dict) and isinstance(obj, dict):
                a, b = names.get(subject.get("$ref")), names.get(obj.get("$ref"))
                if a and b:
                    ever[a].add(b); ever[b].add(a)
                    if row.get("valid_until") in (None, "null"):
                        holds[a].add(b); holds[b].add(a)
                continue
            mine = names.get(instance_id)
            if not mine:
                continue
            for attr, value in row.items():
                if attr in ("full_name", "name", "title") or not isinstance(value, (str, list)):
                    continue
                for one in (value if isinstance(value, list) else [value]):
                    if isinstance(one, str) and one:
                        holds[mine].add(one); ever[mine].add(one)
    return names, {"holds": holds, "ever": ever}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("world")
    parser.add_argument("--hops", default="sh", choices=["sh", "mh"])
    parser.add_argument("--show", type=int, default=8)
    args = parser.parse_args()

    said = frames(fc.load(args.hops, "6k").facts)
    names, held = world_values(Path(args.world))
    known = sorted(set(names.values()), key=len, reverse=True)

    def whose(frame: str) -> str | None:
        """The entity a frame is about: the longest name in the world that the frame contains."""
        low = frame.lower()
        return next((n for n in known if n.lower() in low), None)

    counts = collections.Counter()
    wrong = []
    for frame, values in said.items():
        subject = whose(frame)
        if subject is None:
            counts["субъекта нет в мире"] += 1
            continue
        latest, earlier = values[-1], values[:-1]
        holds = {v.lower() for v in held["holds"].get(subject, ())}
        ever = {v.lower() for v in held["ever"].get(subject, ())}
        if latest.lower() in holds:
            counts["последнее держится"] += 1
        elif latest.lower() in ever:
            counts["последнее есть, но не держится"] += 1
            wrong.append((subject, frame, latest, "записано, но не нынешнее"))
        else:
            counts["последнего нет вовсе"] += 1
            wrong.append((subject, frame, latest, "не записано"))
        if earlier and any(v.lower() in holds for v in earlier):
            counts["прежнее всё ещё нынешнее"] += 1

    print(f"рамок: {sum(counts.values()) - counts['прежнее всё ещё нынешнее']}, "
          f"из них перекрытых: {sum(1 for v in said.values() if len(v) > 1)}")
    for key, n in counts.most_common():
        print(f"  {n:>4}  {key}")
    for subject, frame, latest, why in wrong[: args.show]:
        print(f"\n[{why}] {subject}")
        print(f"   «{frame} {latest}»")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
