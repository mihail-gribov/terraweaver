"""Tags: one shape, counted, and reviewed when new material arrives.

Run: .venv/bin/python tests/test_tags.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from terraweaver import open_world
from terraweaver import tags as tagging

failures: list[str] = []


def check(name: str, condition: bool, detail: str = "") -> None:
    print(f"{'PASS' if condition else 'FAIL'}  {name}" + (f"  — {detail}" if detail and not condition else ""))
    if not condition:
        failures.append(name)


def main() -> int:
    w = open_world()
    w.run('for name, tags in [("Ana Borg", ["job-search", "berlin"]), ("Ben Cruz", ["job search"]),\n'
          '                   ("Cara Dahl", ["Job-Search", "berlin"]), ("Dee Ek", ["to-read"]),\n'
          '                   ("Eve Faber", ["berlin"])]:\n'
          '    Person.new(full_name=name, tags=tags)', "host")

    # --- one shape, so a tag typed three ways is one tag ---
    vocabulary = w.world.tags()
    check("three ways of writing one tag are one tag", vocabulary["job-search"]["count"] == 3,
          str({t: e["count"] for t, e in vocabulary.items()}))
    check("and the entity holds it in that one form",
          w.classes["Person"].get(full_name="Cara Dahl").tags == ["job-search", "berlin"],
          str(w.classes["Person"].get(full_name="Cara Dahl").tags))
    typed = [s.value for s in w.world.facts.all() if s.slot == "tags"]
    check("while the record keeps them as they were given",
          any("Job-Search" in written for written in typed), str(typed))
    check("finding by tag ignores how it was written",
          len(w.world.tagged("Berlin")) == 3, str(w.world.tagged("Berlin")))
    check("a tag used once is named as such", "to-read" in tagging.once_only(w.world),
          str(tagging.once_only(w.world)))

    # --- review is driven by new material, not by the calendar ---
    due = dict((tag, (now, before)) for tag, now, before in tagging.due_for_review(w.world))
    check("a tag nobody has looked at is due once it is a category", "berlin" in due, str(due))
    tagging.reviewed(w.world, "berlin")
    after = dict((tag, (now, before)) for tag, now, before in tagging.due_for_review(w.world))
    check("once looked at, it stays off the list", "berlin" not in after, str(after))
    w.run('for name in ["Finn Gray", "Gus Holt"]:\n'
          '    Person.new(full_name=name, tags=["berlin"])', "host")
    grown = dict((tag, (now, before)) for tag, now, before in tagging.due_for_review(w.world))
    check("until enough new things arrive under it", "berlin" in grown, str(grown))
    check("and the list says how much it moved", grown.get("berlin") == (5, 3), str(grown.get("berlin")))

    # --- two words for one idea: merged because somebody said so ---
    w.run('Person.new(full_name="Hal Ibsen", tags=["jobsearch"])', "host")
    moved = tagging.merge(w.world, "job-search", "jobsearch")
    check("merging carries everything over", moved == 1, str(moved))
    check("and the losing tag is gone", "jobsearch" not in w.world.tags(), str(list(w.world.tags())))
    check("while the one that stayed grew",
          w.world.tags()["job-search"]["count"] == 4, str(w.world.tags()["job-search"]["count"]))

    # --- and tags worth considering, from whatever reads alike ---
    w.run('Person.new(full_name="Rita Chen", tags=["batteries"]).comment("cell chemistry at a battery startup")\n'
          'Person.new(full_name="Lars Ek").comment("works on lithium anodes at a small firm")', "host")
    lars = w.classes["Person"].get(full_name="Lars Ek")
    suggested = [tag for tag, _ in tagging.suggest(w.world, lars)]
    check("a tag is suggested from what reads like it", "batteries" in suggested, str(suggested))
    check("suggesting applies nothing", not lars.tags, str(lars.tags))

    # --- what a tag means is nobody's business here ---
    check("tags that read alike are reported, not merged",
          all(isinstance(pair, tuple) for pair in tagging.look_alike(w.world)))
    before = {tag: entry["count"] for tag, entry in w.world.tags().items()}
    tagging.look_alike(w.world)
    check("nothing was changed by looking",
          {tag: entry["count"] for tag, entry in w.world.tags().items()} == before, str(before))

    print()
    if failures:
        print(f"{len(failures)} failed: {', '.join(failures)}")
        return 1
    print("all tag tests passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
