"""For every expectation the world does not hold, why it does not hold it.

`check_expected.py` answers whether a fact is in the world. That is the number, and a number says
nothing about what to fix: 55 "no link" and 50 "missing" out of 316 on one run, with no way to tell
a fact the host never wrote from one written to a duplicate of the right thing.

So this reads the same expectations and, for each one that failed, says which of a handful of
shapes it is. Nothing here calls a model and nothing here writes: it is a lookup, run as often as
you like, and every count it prints can be checked by hand from what it names.

    .venv/bin/python experiments/why_it_failed.py var/run8/world [--upto 455] [--show 6]
"""
import argparse
import collections
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from check_expected import open_world, written_down    # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("run", type=Path)
    parser.add_argument("--upto", type=int, default=None)
    parser.add_argument("--show", type=int, default=6)
    args = parser.parse_args()

    runtime = open_world(args.run)
    world = runtime.world

    # Everything the world holds, by the name it holds it under and by the name the *record* holds
    # for it. The two differ, and the difference is one of the shapes below: a thing whose name is
    # in the record and not in its image is unfindable while the record is intact.
    by_image: dict = collections.defaultdict(list)
    by_record: dict = collections.defaultdict(list)
    nameless = []
    for name, cls in world.classes.items():
        if cls._spec.get("relation"):
            continue
        keys = [k for k in ("name", "full_name", "title", "label")
                if any(a["name"] == k for a in cls._spec.get("attributes", []))]
        for entity in world.all(name, limit=None, history=True):
            shown = next((getattr(entity, k, None) for k in keys if getattr(entity, k, None)), None)
            if shown:
                by_image[str(shown).strip().lower()].append(entity)
            said = [one.value for one in world.facts.about(entity.subject_id)
                    if one.slot in keys and isinstance(one.value, str)]
            for one in said:
                by_record[one.strip().lower()].append(entity)
            if said and not shown:
                nameless.append((entity, said[0]))

    def look(where: dict, text: str) -> list:
        wanted = str(text or "").strip().lower()
        if wanted in where:
            return where[wanted]
        for name, got in where.items():
            if name and (name in wanted or wanted in name) and abs(len(name) - len(wanted)) < 6:
                return got
        return []

    def joined(subjects: list, objects: list) -> bool:
        for entity in subjects:
            for link in entity.relations():
                far = link.object if link.subject == entity else link.subject
                if far in objects:
                    return True
        return False

    def in_prose(subjects: list, text: str) -> bool:
        """The fact is in this thing's own words instead of in a link."""
        wanted = str(text or "").strip().lower()
        for entity in subjects:
            said = [one for one in (getattr(entity, "descriptions", None) or [])
                    if isinstance(one, str)]
            for attr in type(entity)._spec.get("attributes", []):
                value = getattr(entity, attr["name"], None)
                if isinstance(value, str):
                    said.append(value)
            if any(wanted and wanted in one.lower() for one in said):
                return True
        return False

    why: dict = collections.Counter()
    examples: dict = collections.defaultdict(list)
    owed = [one for one in written_down(args.upto) if not one.get("superseded")]
    for one in owed:
        subjects, objects = look(by_image, one["subject"]), look(by_image, one["object"])
        if subjects and objects and joined(subjects, objects):
            continue                                        # the world holds it; not our business
        shape, detail = _shape(one, subjects, objects, by_record, look, joined, in_prose)
        why[shape] += 1
        examples[shape].append(f"{one['fact']:>3}  {one['said'][:64]}" + (f"   — {detail}" if detail else ""))

    print(f"{len(owed)} expectations standing, {sum(why.values())} the world does not hold.\n")
    for shape, count in why.most_common():
        print(f"   {count:>4}  {shape}")
    print()
    for shape, count in why.most_common():
        print(f"--- {shape} ({count})")
        for line in examples[shape][: args.show]:
            print(f"      {line}")
    return 0


def _shape(one, subjects, objects, by_record, look, joined, in_prose) -> tuple:
    """Which of the shapes this failure is, and what to say about it."""
    for side, found in (("subject", subjects), ("object", objects)):
        if found:
            continue
        # Not in the world under that name. The record may still hold the name — which is a thing
        # the world has and cannot find, not a thing it was never told.
        kept = look(by_record, one[side])
        if kept:
            return ("the name is in the record and not in the image",
                    f"{one[side]!r} is a {type(kept[0]).__name__} showing as {kept[0].display_name()!r}")
        if in_prose(subjects or [], one[side]):
            return ("said in prose about the other end, never made a thing",
                    f"{one[side]!r} is only words on {one['subject']!r}")
        return (f"the {side} was never put in the world", f"{one[side]!r}")
    # Both ends are there and nothing joins them.
    if in_prose(subjects, one["object"]) or in_prose(objects, one["subject"]):
        return ("both ends are there and the fact is in prose, not in a link", "")
    kinds = set()
    for entity in subjects:
        for link in entity.relations():
            kinds.add(type(link)._spec["relation"]["kind"])
    if len(subjects) > 1 or len(objects) > 1:
        return ("both ends are there twice over — the link is on another copy",
                f"{len(subjects)} of the subject, {len(objects)} of the object")
    return ("both ends are there and no link joins them",
            f"the subject holds: {', '.join(sorted(kinds)) or 'nothing'}")


if __name__ == "__main__":
    raise SystemExit(main())
