"""How far the images of a world are from what its record says: rebuild it, and diff.

    .venv/bin/python experiments/image_vs_record.py <a run directory> [--show 5]

The image is meant to be a cache of the record (docs/architecture.md, "How a world serves an
agent", rule 4): assembled from the statements and nothing else. So a world whose images are right
rebuilds into itself. Whatever comes out different was written into an image without being said,
or said and never shown — and which attributes differ says which door did it. Free, no models, on
a copy: the world under measurement is not touched.
"""
import argparse
import collections
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "experiments"))

from check_expected import open_world  # noqa: E402

# Bookkeeping that differs by construction and says nothing about facts: when a thing was last
# looked at, and when its row was first written.
CLOCKS = {"accessed_at", "created_at"}


def snapshot(conn, classes) -> tuple[dict, dict]:
    """(class of every instance, every image row as (instance, attr) -> value)."""
    tables = {n for (n,) in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
    kinds = dict(conn.execute("SELECT id, class_name FROM instances"))
    rows = {}
    for name in classes:
        if name not in tables:
            continue
        for instance, attr, value in conn.execute(f'SELECT instance_id, attr, value FROM "{name}"'):
            if kinds.get(instance) == name:
                rows[(instance, attr)] = value
    return kinds, rows


def empty(value) -> bool:
    return value in (None, "null", "[]", '""')


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("run", type=Path)
    parser.add_argument("--show", type=int, default=5)
    args = parser.parse_args()

    world = open_world(args.run.resolve()).world
    conn = world.store.conn
    own = {n for n, c in world.classes.items() if (c._spec or {}).get("own")}
    kinds_before, before = snapshot(conn, world.classes)
    world.rebuild()
    kinds_after, after = snapshot(conn, world.classes)

    gone = [i for i, k in kinds_before.items() if i not in kinds_after and k not in own]
    # A copy the identity rule glued onto another of the same name is not lost: its statements
    # are there and now build the other image. Only one with nothing in the record is.
    merged = [i for i in gone if world.facts.about(i)]
    gone = [i for i in gone if i not in merged]
    new = [i for i in kinds_after if i not in kinds_before]
    moved = [(i, kinds_before[i], kinds_after[i]) for i in kinds_before
             if i in kinds_after and kinds_before[i] != kinds_after[i]]
    kept = {i for i in kinds_before if i in kinds_after and kinds_before[i] == kinds_after[i]}

    differ = collections.Counter()
    lost = collections.Counter()      # the image held a value, the record shows none
    gained = collections.Counter()    # the record shows a value the image did not hold
    examples = collections.defaultdict(list)
    for key in set(before) | set(after):
        instance, attr = key
        if instance not in kept or attr in CLOCKS:
            continue
        was, now = before.get(key), after.get(key)
        if was == now or (empty(was) and empty(now)):
            continue
        name = kinds_before[instance]
        bucket = lost if empty(now) else gained if empty(was) else differ
        bucket[(name, attr)] += 1
        if len(examples[(name, attr)]) < args.show:
            examples[(name, attr)].append(f"{instance[:8]}  {str(was)[:50]!s:<50} -> {str(now)[:50]}")

    print(f"{len(kinds_before)} instances before, {len(kinds_after)} after the rebuild "
          f"({len(own)} own classes left out of the count of lost ones)\n")
    print(f"   lost entirely      {len(gone)}   (in the image, nowhere in the record)")
    print(f"   merged             {len(merged)}   (copies the identity rule glued onto another)")
    print(f"   new                {len(new)}")
    print(f"   another class      {len(moved)}")
    print(f"   values: shown only by the image {sum(lost.values())}, only by the record "
          f"{sum(gained.values())}, different {sum(differ.values())}\n")
    by_class = collections.Counter(kinds_before[i] for i in gone)
    if by_class:
        print("   lost entirely, by class: " + ", ".join(f"{k} {n}" for k, n in by_class.most_common(10)))
    for title, counts in (("only in the image (the record says nothing)", lost),
                          ("only in the record (the image never showed it)", gained),
                          ("different", differ)):
        if not counts:
            continue
        print(f"\n--- {title}")
        for (name, attr), n in counts.most_common(15):
            print(f"   {n:>4}  {name}.{attr}")
            for line in examples[(name, attr)][:2]:
                print(f"            {line}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
