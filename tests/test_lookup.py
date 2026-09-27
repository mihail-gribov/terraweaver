"""What may be asked of the outside, and what may never leave this world.

Run: .venv/bin/python tests/test_lookup.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from terraweaver import lookup, open_world

failures: list[str] = []


def check(name: str, condition: bool, detail: str = "") -> None:
    print(f"{'PASS' if condition else 'FAIL'}  {name}" + (f"  — {detail}" if detail and not condition else ""))
    if not condition:
        failures.append(name)


def refused(action) -> str | None:
    try:
        action()
    except lookup.NotAllowed as exc:
        return str(exc)
    return None


def main() -> int:
    w = open_world()
    world = w.world
    w.run('Person.new(full_name="Ada Lovelace")', "host")   # somebody this world knows

    # --- the checks we named in advance ---
    check("a kind of thing may be looked up",
          lookup.check(world, "what_is", "what is a doula") == "what is a doula")
    check("and how a kind of link behaves",
          lookup.check(world, "link_properties", "can a person have two godfathers"))
    check("a purpose nobody named is refused",
          "isn't something the world looks up" in (refused(lambda: lookup.check(world, "whatever", "x")) or ""),
          str(refused(lambda: lookup.check(world, "whatever", "x"))))

    # --- nothing about the person leaves, whatever the purpose ---
    leak = refused(lambda: lookup.check(world, "public_name", "where does Ada Lovelace work"))
    check("a name from this world stops the query", leak is not None and "stranger" in leak, str(leak))
    contact = refused(lambda: lookup.check(world, "what_is", "who owns ada@example.com"))
    check("so does an address", contact is not None and "leave this world" in contact, str(contact))
    number = refused(lambda: lookup.check(world, "place", "who is +1 555 010 2030"))
    check("and a phone number", number is not None, str(number))
    check("a public company by name is fine",
          lookup.check(world, "public_name", "TechCorp registered company name"))

    # --- what the person asked for is their call ---
    asked = lookup.check(world, "asked_for", "BMW X5 2026 reliability and running costs")
    check("something the person asked about goes as they put it",
          asked == "BMW X5 2026 reliability and running costs")
    check("even when it names someone, because they asked",
          lookup.check(world, "asked_for", "what is Ada Lovelace known for"))

    print()
    if failures:
        print(f"{len(failures)} failed: {', '.join(failures)}")
        return 1
    print("all lookup tests passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
