"""Run the host's own failed code again, against the world as it is now.

A full benchmark costs an hour and real money, and by the time it lands the code has moved on.
But every world keeps what the host actually wrote and what it got back, so the cases that
argued for a fix can be re-tried directly — no model, no API, seconds.

Each failed run is replayed up to and including the line that raised, against a copy of that
world, so the entities it talks about are the ones it talked about. What comes back is the same
three-way answer as before: it passes now, it fails the same way, or it fails differently.

    .venv/bin/python experiments/replay.py /tmp/tw-fc-sh-rxqngt7c/world.db
    .venv/bin/python experiments/replay.py <world.db> --like "goes .* →"
"""
import argparse
import json
import re
import shutil
import sqlite3
import sys
import tempfile
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from terraweaver.runtime import WorldRuntime  # noqa: E402


def open_as_it_was(world: Path, work: Path) -> "WorldRuntime":
    """Open a copy of the world with the classes it had, not the ones we ship.

    A host that defined its own vocabulary wrote it into a `grown/` directory beside its world.
    Replaying without those, every line about a class the host invented fails for a reason that
    has nothing to do with what is being tested — which is how a replay reports a fix as a
    regression.
    """
    from terraweaver import authoring, ontology

    grown = next((d for d in (world.parent / "grown", world.parent.parent / "grown")
                  if d.is_dir()), None)
    if grown is None:
        return WorldRuntime(str(work))
    theirs = {json.loads(path.read_text())["name"]: json.loads(path.read_text())
              for path in sorted(grown.glob("*.json"))}
    core = ontology.base_specs(Path(__file__).resolve().parent.parent / "ontology" / "core")
    runtime = WorldRuntime(str(work), fixture=None, specs={**core, **theirs}, selves=True)
    authoring.install(runtime.world, work.parent / "grown")
    return runtime


def history(path: str) -> list[tuple[str, str]]:
    """Every run in the order it was made. The failures are replayed in their own company:
    a block three turns later uses a name the block before it bound, and replaying the failures
    alone answers NameError to every question."""
    db = sqlite3.connect(path)
    return [(code or "", error or "") for code, error in
            db.execute("SELECT code, error FROM runs ORDER BY rowid")]


def up_to_the_break(code: str, error: str) -> str:
    """The block as far as it got — the world reports the line, so the replay can stop there."""
    where = re.search(r"^line (\d+):", error, re.M)
    if not where:
        return code
    lines = code.splitlines()
    return "\n".join(lines[: int(where.group(1))])


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("world")
    parser.add_argument("--like", help="only judge errors matching this pattern")
    parser.add_argument("--show", type=int, default=6, help="how many differences to print")
    args = parser.parse_args()

    runs = history(args.world)
    work = Path(tempfile.mkdtemp(prefix="tw-replay-")) / "world.db"
    shutil.copy(args.world, work)
    runtime = open_as_it_was(Path(args.world), work)

    verdicts: Counter = Counter()
    changed = []
    watched = 0
    for number, (code, error) in enumerate(runs):
        if not code:
            continue
        got = runtime.run(up_to_the_break(code, error) if error else code, "replay")
        if not error or (args.like and not re.search(args.like, error)):
            continue                       # replayed for its side effects, not for a verdict
        watched += 1
        was = error.strip().splitlines()[-1]
        now = (got.get("error") or "").strip().splitlines()
        now = now[-1] if now else ""
        if not now:
            verdicts["passes now"] += 1
            changed.append(("passes now", was, ""))
        elif now.split(":")[0] == was.split(":")[0] and now[:60] == was[:60]:
            verdicts["same as before"] += 1
        else:
            verdicts["fails differently"] += 1
            changed.append(("fails differently", was, now))

    print(f"replayed {len(runs)} runs from {args.world}; {watched} of them had failed")
    for verdict, count in verdicts.most_common():
        print(f"  {count:>4}  {verdict}")
    for verdict, was, now in changed[: args.show]:
        print(f"\n[{verdict}]\n  было : {was[:110]}" + (f"\n  стало: {now[:110]}" if now else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
