"""Of the pairs where one fact replaces another, which reading the world holds.

The slice's real subject. A pair is the same sentence said twice with a different value at the
end; the world is right when it holds the later one, wrong when it holds the earlier, and has
lost the fact when it holds neither — usually because the two tellings landed on two entities
that happen to share a name.

    .venv/bin/python experiments/superseded.py <a run directory>
"""
import re
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "benchmarks"))

import factconsolidation as fc                      # noqa: E402
from terraweaver import authoring, growth, ontology as ont   # noqa: E402
from terraweaver.runtime import WorldRuntime        # noqa: E402


def pairs(facts: list[str], upto: int | None = None) -> list[tuple]:
    """(first, second, earlier fact, later fact) for every sentence said twice."""
    seen: dict = {}
    found = []
    for number, fact in enumerate(facts, 1):
        words = fact.rstrip(".").split()
        frame = next((" ".join(words[:cut]) for cut in range(len(words) - 1, 2, -1)
                      if len(" ".join(words[:cut])) > 18), "")
        if frame in seen:
            found.append((seen[frame], number, facts[seen[frame] - 1], fact))
        seen[frame] = number
    return [p for p in found if upto is None or p[1] <= upto]


def open_world(run: Path) -> WorldRuntime:
    work = Path(tempfile.mkdtemp(prefix="tw-sup-"))
    shutil.copytree(run / "grown", work / "grown")
    shutil.copy(run / "world.db", work / "world.db")
    specs = growth.apply_growth(ont.base_specs(ROOT / "ontology" / "core"),
                                growth.load_grown(work / "grown"))
    runtime = WorldRuntime(str(work / "world.db"), fixture=None, specs=specs, selves=True)
    authoring.install(runtime.world, work / "grown")
    ont.set_world(runtime.world)
    return runtime


def main() -> int:
    run = Path(sys.argv[1]).resolve()
    runtime = open_world(run)
    by_name: dict = {}
    for cls in runtime.world.classes.values():
        if cls._spec.get("relation"):
            continue
        for entity in runtime.world.all(cls.__name__, limit=None, history=True):
            said = getattr(entity, "name", None) or getattr(entity, "full_name", None)
            if said:
                by_name.setdefault(said, []).append(entity)

    facts = fc.load("sh", "6k").facts
    tally = {"later": 0, "earlier": 0, "neither": 0}
    lost = []
    for first, second, earlier, later in pairs(facts):
        was = earlier.rstrip(".").rsplit(" ", 1)[-1]
        now = later.rstrip(".").rsplit(" ", 1)[-1]
        subject = re.sub(r"^The [\w\s]+ of ", "", earlier.rstrip("."))
        subject = re.split(r" is | was ", subject)[0].strip()
        verdict = "neither"
        for entity in by_name.get(subject, []):
            for link in entity.relations():
                other = link.object if link.subject == entity else link.subject
                got = getattr(other, "name", None) or getattr(other, "full_name", None) or ""
                if got == now:
                    verdict = "later"
                elif got == was and verdict != "later":
                    verdict = "earlier"
        tally[verdict] += 1
        if verdict != "later":
            lost.append((second, verdict, later, len(by_name.get(subject, []))))

    total = sum(tally.values())
    print(f"{total} superseding pairs in the slice")
    for how, n in tally.items():
        print(f"   holds the {how:<8} {n:>3}   {100 * n // max(total, 1)}%")
    doubled = sum(1 for _, _, _, copies in lost if copies > 1)
    print(f"\n   of the {len(lost)} not holding the later one, {doubled} have the subject "
          f"recorded more than once")
    for number, verdict, fact, copies in lost[:8]:
        print(f"   {number:>3} [{verdict}{', ×' + str(copies) if copies > 1 else ''}] {fact[:70]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
