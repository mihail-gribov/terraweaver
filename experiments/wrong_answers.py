"""Every wrong answer of a run, put at the stage it was lost: writing, reading, or answering.

    .venv/bin/python experiments/wrong_answers.py <a run directory> <results.json>

Read off the world the questions were asked of, and nothing else — no model, free. For each wrong
answer the fact the gold answer comes from is found among the expectations, and the world is asked
three things in order:

    written    did the host ever put a link between the subject and the gold, at any time?
    read       does that link still hold, between findable things, with nothing beside it?
    answered   the world holds the gold and only the gold — so the answer was lost in the asking

The first "no" is the stage. Written down on 2026-10-02 after a day of laying run9's answers out by
hand: the first version of that table was wrong because it read three copies of Germany as one
(docs/now.md), so the copies of a name are counted before its links are read.
"""
import argparse
import collections
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "experiments"))

from check_expected import open_world, written_down   # noqa: E402

NOT_RECORDED = ("not recorded", "nothing is recorded", "nothing recorded", "no record",
                "not formally", "does not record", "doesn't record", "is not in the world")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("run", type=Path)
    parser.add_argument("results", type=Path)
    parser.add_argument("--show", type=int, default=50)
    parser.add_argument("--held", action="store_true",
                        help="print what the world holds about the thing each question asks of")
    args = parser.parse_args()

    runs = json.loads(args.results.read_text())["runs"]
    wrong = [one for one in runs if not one.get("correct")]
    world = open_world(args.run.resolve()).world

    by_image: dict = collections.defaultdict(list)
    by_record: dict = collections.defaultdict(list)
    for name, cls in world.classes.items():
        if cls._spec.get("relation"):
            continue
        keys = [k for k in ("name", "full_name", "title", "label")
                if any(a["name"] == k for a in cls._spec.get("attributes", []))]
        for entity in world.all(name, limit=None, history=True):
            shown = next((getattr(entity, k, None) for k in keys if getattr(entity, k, None)), None)
            if shown:
                by_image[str(shown).strip().lower()].append(entity)
            for one in world.facts.about(entity.subject_id):
                if one.slot in keys and isinstance(one.value, str):
                    by_record[one.value.strip().lower()].append(entity)

    def look(where: dict, text: str) -> list:
        wanted = str(text or "").strip().lower()
        if wanted in where:
            return where[wanted]
        for name, got in where.items():
            if name and (name in wanted or wanted in name) and abs(len(name) - len(wanted)) < 6:
                return got
        return []

    def links(entity, ever: bool) -> list:
        try:
            return entity.relations(any_time=ever, history=ever)
        except Exception:  # noqa: BLE001 - a thing whose links cannot be read is joined to nothing
            return []

    def between(subjects, objects, ever: bool) -> list:
        out = []
        for entity in subjects:
            for link in links(entity, ever):
                far = link.object if link.subject == entity else link.subject
                if far in objects:
                    out.append((entity, link))
        return out

    def unread(link) -> bool:
        return bool((type(link)._spec.get("relation") or {}).get("free"))

    def in_prose(entities, text) -> bool:
        wanted = str(text or "").strip().lower()
        return any(wanted and wanted in str(line).lower()
                   for entity in entities for line in (getattr(entity, "descriptions", None) or []))

    expectations = written_down(None)
    stages: dict = collections.Counter()
    shapes: dict = collections.Counter()
    lines: dict = collections.defaultdict(list)
    for one in wrong:
        gold = [g.strip().lower() for g in one["gold"]]
        question = one["question"].lower()
        # The gold is at either end: "The CEO of Microsoft is Steve Jobs" is written down as
        # Steve Jobs ceo_of Microsoft, and the question asks about Microsoft.
        told = [(e, "object") for e in expectations if str(e["object"]).strip().lower() in gold]
        told += [(e, "subject") for e in expectations if str(e["subject"]).strip().lower() in gold]
        about = [(e, end) for e, end in told
                 if str(e["subject" if end == "object" else "object"]).strip().lower() in question]
        if not about:
            stage, shape, held = "unknown", "no expectation names the gold", ""
        else:
            fact, end = max(about, key=lambda pair: pair[0]["fact"])
            asked_about = fact["subject" if end == "object" else "object"]
            subjects = look(by_image, asked_about) or look(by_record, asked_about)
            objects = look(by_image, fact[end]) or look(by_record, fact[end])
            lost = [side for side, text in (("subject", asked_about), ("gold", fact[end]))
                    if not look(by_image, text) and look(by_record, text)]
            held = "; ".join(sorted({link.display_name()[:70] for entity in subjects
                                     for link in links(entity, False)}))[:300]
            ever = between(subjects, objects, ever=True)
            now = between(subjects, objects, ever=False)
            if not ever:
                stage = "writing"
                if not subjects or not objects:
                    shape = f"the {'subject' if not subjects else 'gold'} was never made a thing"
                elif in_prose(subjects, fact["object"]) or in_prose(objects, fact["subject"]):
                    shape = "said in prose, never as a link"
                else:
                    shape = "both things there, never linked"
            elif lost:
                stage, shape = "reading", f"the {' and '.join(lost)} lost its name"
            elif not now:
                stage, shape = "reading", "linked, then ended"
            else:
                # A link nobody has read yet is a bare one: it stands beside the typed link it
                # would have been joined to, and takes no part in which telling holds.
                kinds = {type(link)._spec["relation"]["kind"] for _, link in now}
                others = [link for entity, _ in now for link in links(entity, False)
                          if (link.object if link.subject == entity else link.subject) not in objects]
                typed_beside = [link for link in others if not unread(link)
                                and type(link)._spec["relation"]["kind"] in kinds]
                unread_beside = [link for link in others if unread(link)]
                if len(subjects) > 1 or len(objects) > 1:
                    stage, shape = "answering", f"held, on one of {len(subjects)}x{len(objects)} copies"
                elif typed_beside:
                    stage, shape = "reading", "held beside another typed value that did not give way"
                elif unread_beside:
                    stage, shape = "reading", "held beside a telling the reading never reached"
                elif all(unread(link) for _, link in now):
                    stage, shape = "reading", "held only as words the reading never reached"
                else:
                    stage, shape = "answering", "the world held the gold and only the gold"
        said_none = any(word in one["answer"].lower() for word in NOT_RECORDED)
        stages[stage] += 1
        shapes[(stage, shape)] += 1
        lines[(stage, shape)].append(
            f"{one['question'][:60]:<60}  gold {one['gold'][0][:24]!r}  said "
            f"{'(not recorded)' if said_none else repr(one['answer'][:40])}"
            + (f"\n            holds: {held}" if args.held and held else ""))

    print(f"{len(runs)} questions, {len(runs) - len(wrong)} right, {len(wrong)} wrong\n")
    for stage in ("writing", "reading", "answering", "unknown"):
        if not stages[stage]:
            continue
        print(f"{stage:<10} {stages[stage]:>3}")
        for (s, shape), n in shapes.most_common():
            if s == stage:
                print(f"   {n:>3}  {shape}")
    print()
    for (stage, shape), found in sorted(lines.items()):
        print(f"--- {stage}: {shape}")
        for line in found[: args.show]:
            print(f"      {line}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
