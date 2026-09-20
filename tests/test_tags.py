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

    # --- one shape to compare in, whatever was typed ---
    vocabulary = w.world.tags()
    check("three ways of writing one tag are one tag", vocabulary["job-search"]["count"] == 3,
          str({t: e["count"] for t, e in vocabulary.items()}))
    check("and the world keeps every spelling, because that is the thing to review",
          vocabulary["job-search"]["spellings"] == {"job-search", "job search", "Job-Search"},
          str(vocabulary["job-search"]["spellings"]))
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

    # --- what a tag means is nobody's business here ---
    check("tags that read alike are reported, not merged",
          all(isinstance(pair, tuple) for pair in tagging.look_alike(w.world)))
    check("nothing was changed by looking", len(w.world.tags()["job-search"]["spellings"]) == 3)

    print()
    if failures:
        print(f"{len(failures)} failed: {', '.join(failures)}")
        return 1
    print("all tag tests passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
