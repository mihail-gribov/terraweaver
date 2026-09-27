"""Tests for the two parties every world holds, and the files that describe them.

Run: .venv/bin/python tests/test_selves.py
"""
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from terraweaver import open_world

failures: list[str] = []


def check(name: str, condition: bool, detail: str = "") -> None:
    print(f"{'PASS' if condition else 'FAIL'}  {name}" + (f"  — {detail}" if detail and not condition else ""))
    if not condition:
        failures.append(name)


def main() -> int:
    # --- opening a world is one line, and an empty one is still a world ---
    w = open_world()
    check("an empty world has the person it belongs to", w.world.owner is not None)
    check("and the assistant keeping it", w.world.me is not None)
    check("they are the same two rows in every world",
          w.world.owner.id == "person:user" and w.world.me.id == "agent:self",
          f"{w.world.owner.id} / {w.world.me.id}")
    check("and neither is the host's to replace", w.world.is_protected(w.world.owner))

    with tempfile.TemporaryDirectory() as folder:
        home = Path(folder)
        (home / "USER.md").write_text(
            "---\nfull_name: Michael Gribov\naliases: Misha\n---\nBuilds TerraWeaver.")
        (home / "soul.md").write_text("---\nname: Tera\n---\nKeeps the world. Never answers for the user.")

        # --- the files describe them, the way personal agents are configured ---
        w = open_world(str(home / "world.db"))
        check("the user is read from their file", w.world.owner.full_name == "Michael Gribov",
              str(w.world.owner.full_name))
        check("the assistant too", w.world.me.name == "Tera", str(w.world.me.name))
        check("and a soul file says who it is, not what to do",
              w.world.me.character.startswith("Keeps the world"), str(w.world.me.character))
        check("what the file says below the front matter is kept",
              w.world.owner.notes == "Builds TerraWeaver.", str(w.world.owner.notes))

        # --- and what it says is facts, with the file as their source ---
        stated = w.world.facts.about("person:user")
        check("the file's lines are statements, not edits", len(stated) == 3, str(stated))
        check("each carries the file it came from", {s.source for s in stated} == {"USER.md"},
              str({s.source for s in stated}))

        # --- changing the file restates it; taking a line out takes the value with it ---
        (home / "USER.md").write_text("---\nfull_name: Michael Gribov\n---\nMoved to Belgrade.")
        again = open_world(str(home / "world.db"))
        check("an edited file is read again", again.world.owner.notes == "Moved to Belgrade.",
              str(again.world.owner.notes))
        check("a line taken out takes its value", again.world.owner.aliases is None,
              str(again.world.owner.aliases))
        live = again.world.facts.about("person:user")
        check("the statement it used to make is retracted", {s.slot for s in live} == {"full_name", "descriptions"},
              str(live))
        check("and is still in the record",
              len(again.world.facts.about("person:user", include_retracted=True)) == 5,
              str(len(again.world.facts.about("person:user", include_retracted=True))))

        # --- an unchanged file isn't read again ---
        before = len(again.world.facts.about("person:user", include_retracted=True))
        third = open_world(str(home / "world.db"))
        check("reopening an unchanged world states nothing new",
              len(third.world.facts.about("person:user", include_retracted=True)) == before,
              str(len(third.world.facts.about("person:user", include_retracted=True))))

    # --- both are in every namespace, under names that can't be taken ---
    w = open_world()
    seen = w.run('print(user.full_name, agent.name, owner is user, me is agent)', "host")
    check("both are in the namespace under permanent names",
          seen["output"].strip() == "you assistant True True", seen["output"] or str(seen["error"]))
    taken = w.run('user = 5', "host")
    check("and neither can be rebound", not taken["ok"] and "pick another name" in str(taken["error"]),
          str(taken["error"]))
    w.reset_session("host")
    after = w.run('print(user.full_name)', "host")
    check("a new task still has them", after["output"].strip() == "you", after["output"])

    print()
    if failures:
        print(f"{len(failures)} failed: {', '.join(failures)}")
        return 1
    print("all selves tests passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
