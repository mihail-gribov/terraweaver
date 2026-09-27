"""Run the link inspector over a world.

    .venv/bin/python experiments/inspect_links.py experiments/results/batches/fixed100

Names the ends of any type that never said them (one open question per type, written down), then
judges each link (one closed question per link). Direction only: whether each end is the kind of
thing that belongs at its end. Whether the fact is true is not asked — this record deliberately
holds claims that contradict common knowledge and they are what it exists to keep.
"""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from terraweaver import authoring, growth, inspector, ontology as ont, outside  # noqa: E402
from terraweaver.runtime import WorldRuntime                                    # noqa: E402


def keys() -> None:
    for where in (ROOT / ".env", Path.home() / "Projects" / "ai-safity" / ".env"):
        if not where.exists():
            continue
        for line in where.read_text().splitlines():
            for name in ("TYPESAFE_API_KEY", "NEBIUS_API_KEY"):
                if line.startswith(name) and not os.environ.get(name):
                    os.environ[name] = line.split("=", 1)[1].strip().strip('"')


def main() -> int:
    keys()
    where = Path(sys.argv[1]).resolve()
    specs = growth.apply_growth(ont.base_specs(ROOT / "ontology" / "core"),
                                growth.load_grown(where / "grown"))
    rt = WorldRuntime(str(where / "world.db"), specs=specs, selves=True)
    authoring.install(rt.world, where / "grown")
    world = rt.world

    world.engineer = outside.namer(outside.Nemotron())
    unnamed = [n for n in inspector.unread_types(world)]
    print(f"{where.name}: {len(unnamed)} type(s) nobody has read")
    for name, lines in inspector.look_at_types(world, limit=100).items():
        for line in lines:
            print(f"  {name}: {line.splitlines()[0][:110]}")

    waiting = inspector.unread(world, limit=1000)
    print(f"\n{len(waiting)} link(s) nobody has read")
    tally = inspector.look(world, outside.judge(outside.Jev()), reader="jev-1.13.0", limit=1000)
    print("  " + ", ".join(f"{k} {v}" for k, v in tally.items() if v))
    print(f"  read again now: {len(inspector.unread(world, limit=1000))} (should be 0)")

    pairs = inspector.twins(world)
    if pairs:
        print("\ntypes that read like each other:")
        for a, b, score in pairs[:10]:
            print(f"  {a} ~ {b}   {score}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
