"""Tests for the baseline memory: the four calls of the contract over a plain text file.

Run: .venv/bin/python tests/test_baseline.py           # no model calls
     .venv/bin/python tests/test_baseline.py --live    # plus ask/context through Haiku
"""
import asyncio
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from baseline import server  # noqa: E402

failures: list[str] = []


def check(name: str, condition: bool, detail: str = "") -> None:
    print(f"{'PASS' if condition else 'FAIL'}  {name}" + (f"  — {detail}" if detail and not condition else ""))
    if not condition:
        failures.append(name)


def call(tool, *args, **kwargs) -> str:
    return asyncio.run(tool(*args, **kwargs))


def main() -> int:
    live = "--live" in sys.argv
    with tempfile.TemporaryDirectory() as where:
        server.facts = Path(where) / "memory" / "facts.md"

        # --- an empty memory answers without a model ---
        check("empty memory: ask says so", call(server.ask, "Where does Anna live?") == "The memory is empty.")
        check("empty memory: context is nothing", call(server.context, "Hi") == "nothing")
        check("questions: a text file never asks", call(server.questions) == "Nothing to ask.")

        # --- tell keeps what was said, as said, dated, with its source ---
        check("blank tell is not kept", call(server.tell, "   ").startswith("Nothing was said"))
        check("nothing written for a blank tell", not server.facts.exists())
        check("tell keeps", call(server.tell, "My sister Anna lives in Lisbon.") == "Kept.")
        call(server.tell, "Anna moved to Porto last month.", source="anna's postcard")
        text = server.facts.read_text()
        check("both kept, in order", text.index("Lisbon") < text.index("Porto"), text)
        check("default source is the conversation", "· conversation\nMy sister Anna" in text, text)
        check("a named source is kept", "· anna's postcard\nAnna moved" in text, text)
        check("each entry is dated", text.count("## 20") == 2, text)
        call(server.tell, "Mia likes drawing.", source="  a note\non the fridge ")
        check("a source is one line", "· a note on the fridge\nMia likes" in server.facts.read_text())
        call(server.tell, "Mia is six.", source="")
        check("a blank source is the conversation", "· conversation\nMia is six." in server.facts.read_text())

        # --- the contract's list, from whatever the model wrote ---
        check("list: bullets, numbers and blanks become `- ` items",
              server.as_list("1. Anna lives in Porto.\n\n* The user is allergic to cats.", 10)
              == ["- Anna lives in Porto.", "- The user is allergic to cats."])
        check("list: capped at the limit", len(server.as_list("a\nb\nc\nd", 2)) == 2)
        check("list: an item stays under 300 characters", len(server.as_list("x" * 500, 1)[0]) < 300)
        check("context with limit 0 is nothing", call(server.context, "Anna?", limit=0) == "nothing")

        # --- the model reads the whole file, the later entry holds ---
        if live:
            answer = call(server.ask, "Which city does Anna live in now?")
            check("ask: the later entry holds", "Porto" in answer, answer)
            answer = call(server.ask, "What is Anna's phone number?")
            check("ask: says when the memory does not say", "not" in answer.lower() and not any(
                ch.isdigit() for ch in answer), answer)
            answer = call(server.context, "Thinking of visiting my sister in summer")
            check("context: brings up the sister", "Porto" in answer, answer)
            check("context: every line is a `- ` item", all(line.startswith("- ") for line in answer.splitlines()), answer)
            answer = call(server.context, "Tell me everything about my family", limit=1)
            check("context: never more than the limit", len(answer.splitlines()) == 1, answer)
            answer = call(server.context, "Fix the failing import in setup.py")
            check("context: nothing for an unrelated message", answer.strip().lower().rstrip(".") == "nothing", answer)

    print(f"\n{len(failures)} failed" if failures else "\nall passed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
