"""Tests for names written differently: alphabets, spellings, short forms, initials.

Run: .venv/bin/python tests/test_nameforms.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from terraweaver import nameforms

failures: list[str] = []


def check(name: str, condition: bool, detail: str = "") -> None:
    print(f"{'PASS' if condition else 'FAIL'}  {name}" + (f"  — {detail}" if detail and not condition else ""))
    if not condition:
        failures.append(name)


def main() -> int:
    same = nameforms.same_name

    # --- another alphabet is not another name ---
    check("a name written in Cyrillic meets the same name in Latin",
          same("Михаил Грибов", "Mikhail Gribov"))
    check("and so does a short form of it", same("Миша Грибов", "Michael Gribov"))

    # --- one sound, two spellings: whoever wrote it chose ---
    check("kh and h are one name", same("Mikhail Gribov", "Mihail Gribov"))
    check("so are c and k", same("Nikolai", "Nicolai") and same("Viktor", "Victor"))
    check("and a doubled letter", same("Anna", "Ana"))

    # --- the short forms people actually use ---
    check("a table of short forms carries the common ones",
          same("Mike", "Michael") and same("Bob", "Robert") and same("Katya", "Ekaterina"))
    check("and it works through a spelling variation too", same("Mihail", "Миша"))

    # --- an initial stands for the name ---
    check("an initial with a surname is that person", same("M. Gribov", "Mikhail Gribov"))

    # --- and none of this makes two people one ---
    check("a different surname is a different person", not same("Mikhail Orlov", "Mihail Gribov"))
    check("a nickname nobody vouched for is not a form", not same("Sota", "Mihail"))
    check("and neither is an unrelated name", not same("Anna Peterson", "Anna Sullivan"))

    # --- what the world works out about language is kept for everyone ---
    check("an unknown pair doesn't match", not same("Tosha", "Anton Orlov"))
    nameforms.learn("tosha", "anton")
    check("until it is learned, and then it does for everyone",
          same("Tosha Orlov", "Anton Orlov") and same("Tosha", "Anton"))

    print()
    if failures:
        print(f"{len(failures)} failed: {', '.join(failures)}")
        return 1
    print("all name-form tests passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
