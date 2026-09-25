"""Read what nobody has read yet, in a world that already exists.

The reading happens when a task closes, because that is where nothing is waiting on it. But a
close can pass with nothing read — a world served without an engineer reads nothing at all, and
that is not an error anywhere, it is simply a world that cannot read yet. The record is unharmed:
an untyped link holds its two things and the words it was said in, and the row that says nobody
has read it is still open.

So this is the catch-up. It opens a world as it stands, gives it an engineer, and goes over
everything still unread — the facts said in words, and the things that came in as bare names.
Nothing here is special to being late: it is the same pass the close runs, run on purpose.

    .venv/bin/python experiments/catch_up.py <world.db> [--grown <dir>]
"""
import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from terraweaver import authoring, ontology, outside, portraits, sentences  # noqa: E402
from terraweaver.runtime import WorldRuntime  # noqa: E402

from experiments.base_run import _the_key  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("db", type=Path)
    parser.add_argument("--grown", type=Path, default=None)
    parser.add_argument("--limit", type=int, default=200)
    args = parser.parse_args()

    if not _the_key():
        print("NEBIUS_API_KEY is not set, so there is no engineer and nothing to catch up with.")
        return 1

    grown = args.grown or args.db.parent / "grown"
    specs = ontology.load_specs(ROOT / "ontology" / "core", grown_dir=grown)
    runtime = WorldRuntime(str(args.db), fixture=None, specs=specs, selves=False)
    authoring.install(runtime.world, grown)
    runtime.world.engineer = outside.Nemotron(ttl=120)

    said, waiting = sentences.count(runtime.world)
    asked, unread = portraits.count(runtime.world)
    print(f"{waiting} of {said} facts said in words are unread; "
          f"{unread} account(s) of {asked} bare name(s) are unread.\n", flush=True)

    if waiting:
        got = sentences.formalise(runtime.world, runtime.world.engineer, limit=args.limit)
        print("facts said in words:", got, flush=True)
    if unread:
        got = portraits.formalise(runtime.world, runtime.world.engineer, limit=args.limit,
                                  run=runtime._the_world_writes)
        runtime._hand_back_what_moved(got.pop("moved", []))
        print("things that came in as names:", got, flush=True)

    print("\n--- links the world holds now")
    for name, cls in sorted(runtime.world.classes.items()):
        rel = cls._spec.get("relation")
        if not rel:
            continue
        for link in runtime.world.all(name, limit=None, history=True):
            if getattr(link, "subject", None) is None:
                continue
            held = "" if getattr(link, "valid_until", None) is None else "  (ended)"
            print(f"    {link.display_name()[:96]}{held}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
