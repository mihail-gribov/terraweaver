"""Read the world against the expectations written down for each batch.

The expectations live in `experiments/expected/*.json`, drafted once by
`draft_expectations.py` and corrected by hand. Nothing here reads a sentence: this is a lookup,
so what it reports is the world and not a parser's opinion of the facts.

A later telling replaces an earlier one, so what a fact owes is measured only if it is the
last word on its subject and predicate; the ones it replaced are owed as history instead.

    .venv/bin/python experiments/check_expected.py <a run directory> [--by 10]
"""
import argparse
import json
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from terraweaver import authoring, growth, ontology as ont      # noqa: E402
from terraweaver.runtime import WorldRuntime                    # noqa: E402

WHERE = ROOT / "experiments" / "expected"


def written_down(upto: int | None):
    """Every expectation somebody has written down, in order, with the replaced ones marked."""
    owed, last = [], {}
    for path in sorted(WHERE.glob("*.json")):
        for one in json.loads(path.read_text())["facts"]:
            if upto is not None and one["fact"] > upto:
                continue
            expect = one.get("expect")
            if not expect:
                continue
            key = (expect["subject"], expect["predicate"])
            if key in last:
                owed[last[key]] = dict(owed[last[key]], superseded=True)
            last[key] = len(owed)
            owed.append({"fact": one["fact"], "said": one["said"], **expect})
    return owed


def open_world(run: Path) -> WorldRuntime:
    work = Path(tempfile.mkdtemp(prefix="tw-chk-"))
    shutil.copytree(run / "grown", work / "grown")
    shutil.copy(run / "world.db", work / "world.db")
    specs = growth.apply_growth(ont.base_specs(ROOT / "ontology" / "core"),
                                growth.load_grown(work / "grown"))
    runtime = WorldRuntime(str(work / "world.db"), fixture=None, specs=specs, selves=True)
    authoring.install(runtime.world, work / "grown")
    ont.set_world(runtime.world)
    return runtime


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("run", type=Path)
    parser.add_argument("--upto", type=int, default=None)
    parser.add_argument("--by", type=int, default=0)
    parser.add_argument("--show", type=int, default=8)
    args = parser.parse_args()

    runtime = open_world(args.run.resolve())
    # Whatever each class calls the thing, read from its own declaration. Reading `name` and
    # `full_name` only made thirty-six works invisible — they are `ArtisticWork`, and a work has
    # a title — so every fact about an author, a performer or what somebody is famous for read
    # as a fact the world had lost.
    by_name: dict = {}
    for cls in runtime.world.classes.values():
        if cls._spec.get("relation"):
            continue
        declared = [a["name"] for a in cls._spec.get("attributes", [])]
        keys = [k for k in ("name", "full_name", "title", "label") if k in declared]
        for entity in runtime.world.all(cls.__name__, limit=None, history=True):
            said = next((getattr(entity, k, None) for k in keys if getattr(entity, k, None)), None)
            if said:
                by_name.setdefault(said, []).append(entity)

    def named(text: str):
        if text in by_name:
            return by_name[text]
        for name, got in by_name.items():
            if name and (name in text or text in name) and abs(len(name) - len(text)) < 6:
                return got
        return []

    owed = [one for one in written_down(args.upto) if not one.get("superseded")]
    tally = {"as owed": 0, "backwards": 0, "no link": 0, "missing": 0}
    verdicts = {}
    for one in owed:
        subjects, objects = named(one["subject"]), named(one["object"])
        if not subjects or not objects:
            verdict = "missing"
        else:
            verdict = "no link"
            for entity in subjects:
                for link in entity.relations():
                    far = link.object if link.subject == entity else link.subject
                    if far in objects:
                        kind = type(link)._spec["relation"]["kind"]
                        turned = (kind.endswith(("_by", "_of")) or kind.startswith("is_")
                                  or one.get("either"))
                        verdict = ("as owed" if link.subject == entity or turned else "backwards")
                        if verdict == "as owed":
                            break
                if verdict == "as owed":
                    break
        tally[verdict] += 1
        verdicts[one["fact"]] = (verdict, one["said"])

    print(f"{len(owed)} expectations written down and still standing "
          f"(the ones a later telling replaced are owed as history, not as what holds)\n")
    for how in ("as owed", "backwards", "no link", "missing"):
        print(f"   {how:<10} {tally[how]:>4}   {100 * tally[how] // max(len(owed), 1)}%")
    if args.by:
        print("\n   by batch:")
        for lo in range(1, max(verdicts) + 1, args.by):
            here = [v for n, v in verdicts.items() if lo <= n < lo + args.by]
            if here:
                right = sum(1 for v, _ in here if v == "as owed")
                print(f"     {lo:>3}-{lo + args.by - 1:<3}  {right}/{len(here)}")
    shown = [(n, v, s) for n, (v, s) in sorted(verdicts.items()) if v != "as owed"]
    print()
    for number, how, said in shown[: args.show]:
        print(f"   {number:>3} [{how}] {said[:70]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
