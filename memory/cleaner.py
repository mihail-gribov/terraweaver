"""The cleaner: removes what has outlived its time, of every kind the world keeps.

    .venv/bin/python -m memory.cleaner --memory main        # what it removed

Everything with a TTL (memory/ttl.py: 90 days) is counted from its last use:

- things found for tasks: from the last time a task found or read them; what has been with the
  user — named in an answer the agent got, or in the user's memory — has no TTL;
- programs of the task registry: from the last time they ran.

What is removed is removed for good — records, texts, files. The user's own memory is never
touched here: what the user told goes only when the user asks for it to.

It runs before every task (memory/solve.py), and can be run on its own.
"""
import argparse
from datetime import datetime
from pathlib import Path

from memory.programs import Programs
from memory.tools import Shelf, spoken

ROOT = Path(__file__).resolve().parents[1]


def clean(memory: Shelf, programs: Programs | None = None, now: datetime | None = None, log=print) -> dict:
    """Remove what is past its time: {"items": {collection: [names]}, "programs": [names]}."""
    removed = {"items": {}, "programs": []}
    collections = memory.path / "collections"
    for path in sorted(collections.glob("*/")) if collections.exists() else []:
        gone = Shelf(path).expire(lambda name: spoken(memory, name), now)
        if gone:
            removed["items"][path.name] = gone
            log(f"collection {path.name}: {len(gone)} items unused for their TTL, removed")
    removed["programs"] = (programs or Programs()).expire(now)
    for name in removed["programs"]:
        log(f"program {name}: not run for its TTL, removed")
    return removed


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--memory", default="main", help="var/memory/<name>: the user's memory")
    args = parser.parse_args()
    removed = clean(Shelf(ROOT / "var" / "memory" / args.memory))
    if not removed["items"] and not removed["programs"]:
        print("nothing past its time")


if __name__ == "__main__":
    main()
