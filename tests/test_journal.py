"""Tests for the baseline memory: the contract's calls over a plain text file.

Run: .venv/bin/python tests/test_baseline.py           # no model calls
     .venv/bin/python tests/test_baseline.py --live    # plus ask/context through Haiku
"""
import asyncio
import sys
import tempfile
from datetime import timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from memory import journal as server  # noqa: E402

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
        check("empty memory: search is nothing", call(server.search_memory, "Anna") == "nothing")
        check("empty memory: nothing to forget", call(server.forget, "#1") == "Nothing was forgotten.")

        # --- tell keeps what was said, as said, dated, with its source ---
        check("blank tell is not kept", call(server.tell, "   ").startswith("Nothing was said"))
        check("nothing written for a blank tell", not server.facts.exists())
        check("tell keeps", call(server.tell, "My sister Anna lives in Lisbon.") == "Kept.")
        call(server.tell, "Anna moved to Porto last month.", source="anna's postcard")
        text = server.facts.read_text()
        check("both kept, in order", text.index("Lisbon") < text.index("Porto"), text)
        check("default source is the conversation", "· conversation\nMy sister Anna" in text, text)
        check("a named source is kept", "· anna's postcard\nAnna moved" in text, text)
        check("each entry is numbered and dated", "## #1 · 20" in text and "## #2 · 20" in text, text)
        call(server.tell, "Mia likes drawing.", source="  a note\non the fridge ")
        check("a source is one line", "· a note on the fridge\nMia likes" in server.facts.read_text())
        call(server.tell, "Mia is six.", source="")
        check("a blank source is the conversation", "· conversation\nMia is six." in server.facts.read_text())

        # --- forget by number takes exactly those entries, and a number is never given again ---
        check("forget: a number that is not held", call(server.forget, "#99") == "Nothing was forgotten.")
        gone = call(server.forget, "#3")
        check("forget: returns what it took", gone.startswith("- #3 · ") and gone.endswith(": Mia likes drawing."), gone)
        text = server.facts.read_text()
        check("forget: the entry is gone", "drawing" not in text and "Lisbon" in text and "Mia is six." in text, text)
        check("forget: the request is kept, as its own entry", "## #5 · " in text and "· forget\nThe user asked "
              "for this to be forgotten, and 1 entry was taken out: #3" in text, text)
        listed = call(server.forgotten)
        check("bin: forgotten lists the entry, with when and until when", listed.startswith("- #3 · ")
              and "Mia likes drawing." in listed and "forgotten " in listed and "deleted for good after " in listed, listed)
        check("bin: no reader sees it", "drawing" not in server._memory())
        server.keep_forgotten = timedelta(0)
        server._memory()
        check("bin: past its time it is deleted for good", "drawing" not in server._bin().read_text()
              and call(server.forgotten).startswith("Nothing was forgotten"))
        server.keep_forgotten = timedelta(days=30)
        call(server.tell, "Mia goes to school.")
        check("tell after forget: the next number, not a reused one", "## #6 · " in server.facts.read_text())
        check("entries: one item per entry, as told",
              server._as_entry("2 · 2026-10-15 12:00:00 · anna's postcard", "Anna moved\nto Porto.")
              == "- #2 · 2026-10-15 12:00:00 · anna's postcard: Anna moved to Porto.")
        check("numbers: only those held, in order, no repeats",
              server._numbers("4, 2, 9, 4", {1, 2, 4}, 10) == [4, 2])
        check("add_memory is tell", call(server.tell, "Anna has a dog.") == "Kept."
              and "add_memory" in {t.name for t in asyncio.run(server.server.list_tools())})

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
            found = call(server.search_memory, "where Anna lives")
            check("search: the entries themselves, both of them", "Lisbon" in found and "Porto" in found
                  and all(line.startswith("- #") for line in found.splitlines()), found)
            gone = call(server.forget, "that Anna has a dog")
            again = call(server.forget, "that Anna has a dog")
            check("forget in words never takes an earlier request to forget",
                  "taken out: that Anna has a dog" in server.facts.read_text(), again)
            check("forget in words: that entry and no other, and the request kept", "dog" in gone
                  and len(gone.splitlines()) == 1 and server.facts.read_text().count("dog") == 1
                  and "taken out: that Anna has a dog" in server.facts.read_text(), gone)
            answer = call(server.context, "Fix the failing import in setup.py")
            check("context: nothing for an unrelated message", answer.strip().lower().rstrip(".") == "nothing", answer)

    print(f"\n{len(failures)} failed" if failures else "\nall passed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
