"""Replay every step into a fresh base world and check what it holds against what it must.

    .venv/bin/python experiments/story/run.py
    .venv/bin/python experiments/story/run.py --show   # print the state after each step
"""
import argparse
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from terraweaver import authoring, ontology          # noqa: E402
from terraweaver.runtime import WorldRuntime         # noqa: E402

from experiments.story.steps import STEPS            # noqa: E402

CORE = ROOT / "ontology" / "core"


def holding(world) -> set:
    """(type, from, to, holds) for every link in the world, however it was written."""
    out = set()
    for name, cls in world.classes.items():
        if not cls._spec.get("relation"):
            continue
        for link in world.all(name, limit=None, history=True):
            if link.subject is None or link.object is None:
                continue
            out.add((name, link.subject.display_name(), link.object.display_name(),
                     link.valid_until is None))
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--show", action="store_true")
    args = parser.parse_args()

    work = Path(tempfile.mkdtemp(prefix="tw-story-"))
    runtime = WorldRuntime(str(work / "world.db"), fixture=None, selves=True,
                           specs=ontology.base_specs(CORE))
    authoring.install(runtime.world, work / "grown")

    wrong = 0
    before = holding(runtime.world)
    for number, step in enumerate(STEPS, 1):
        got = runtime.run(step["code"], "story")
        after = holding(runtime.world)
        gained = {(t, a, b) for t, a, b, holds in after - before if holds}
        ended = {(t, a, b) for t, a, b, holds in after if not holds} - \
                {(t, a, b) for t, a, b, holds in before if not holds}
        before = after

        want_gained, want_ended = set(step.get("gained", [])), set(step.get("ended", []))
        missing = (want_gained - gained) | (want_ended - ended)
        extra = (gained - want_gained) | (ended - want_ended)
        ok = not missing and not extra and got["ok"]
        wrong += 0 if ok else 1
        print(f"{'✓' if ok else '✗'} {number:>3}. {step['said']}")
        if step.get("why"):
            print(f"       ({step['why']})")
        if not got["ok"]:
            print(f"       ОТКАЗ: {(got['error'] or '').splitlines()[-1][:110]}")
        for link in sorted(want_gained - gained):
            print(f"       не появилось: {link[0]}: {link[1]} → {link[2]}")
        for link in sorted(want_ended - ended):
            print(f"       не закрылось: {link[0]}: {link[1]} → {link[2]}")
        for link in sorted(gained - want_gained):
            print(f"       лишнее:       {link[0]}: {link[1]} → {link[2]}")
        for link in sorted(ended - want_ended):
            print(f"       зря закрыто:  {link[0]}: {link[1]} → {link[2]}")
        if args.show and (gained or ended):
            for link in sorted(gained):
                print(f"         + {link[0]}: {link[1]} → {link[2]}")
            for link in sorted(ended):
                print(f"         − {link[0]}: {link[1]} → {link[2]}")

    print(f"\nсошлось {len(STEPS) - wrong} из {len(STEPS)}")
    return 1 if wrong else 0


if __name__ == "__main__":
    raise SystemExit(main())
