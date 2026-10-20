"""Tests for the proto memory: entities, events and links named by code, over the baseline's journal.

Run: .venv/bin/python tests/test_proto.py           # no model calls
"""
import asyncio
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from baseline import server as base  # noqa: E402
from proto import server  # noqa: E402
from proto.model import Structure  # noqa: E402

failures: list[str] = []


def check(name: str, condition: bool, detail: str = "") -> None:
    print(f"{'PASS' if condition else 'FAIL'}  {name}" + (f"  — {detail}" if detail and not condition else ""))
    if not condition:
        failures.append(name)


async def _none() -> str:
    return "none"


def main() -> int:
    with tempfile.TemporaryDirectory() as where:
        base.facts = Path(where) / "facts.md"
        server.structure = Structure(Path(where) / "structure.jsonl", base._keep, server.held)
        server.sessions.clear()

        # --- a run writes sentences to the journal and things beside it ---
        said = server.run_code(
            'anna = entity("Anna", "Anna is the user\'s sister.", kind="Person")\n'
            'olga = entity("Olga")\n'
            'anna.say("Anna moved from Lisbon to Porto in September 2026.")\n'
            'link(anna, olga, "Anna and Olga work together at Brightwork.", as_="colleague")\n', "s1")
        check("a run says what it kept", "Kept: #1 (Anna), #2 (Anna), #3 (Anna, Olga)." in said, said)
        journal = base.facts.read_text()
        check("the journal holds the sentences, as told",
              "Anna is the user's sister." in journal and "work together at Brightwork." in journal, journal)
        records = [json.loads(line) for line in (Path(where) / "structure.jsonl").read_text().splitlines()]
        check("kind is a free word, kept lower case",
              any(r.get("name") == "Anna" and r.get("kind") == "person" for r in records), str(records))
        check("a link points at both things and its word",
              any(r.get("entry") == 3 and r["about"] == ["t1", "t2"] and r["as"] == "colleague" for r in records))

        # --- variables last between runs of one session, not across sessions ---
        said = server.run_code('print(anna.about())', "s1")
        check("variables last between runs", "Lisbon to Porto" in said and "Brightwork" in said, said)
        said = server.run_code('print(anna)', "s2")
        check("another session does not see them", "NameError" in said, said)

        # --- the memory asks who is who; it never merges on a guess ---
        said = server.run_code('a = entity("Anna Lee")', "s2")
        check("a shared name is asked about", "Is Anna Lee (t3) the Anna the memory holds as t1" in said
              and "same('t3', 't1')" in said, said)
        check("nothing about Olga is asked", "Olga" not in said, said)
        check("until answered, they are two", server.run_code('print(a.about())', "s2").startswith("[]"))
        server.run_code("a.say('Anna Lee has a dog named Rex.')", "s2")
        said = server.run_code("print(same('t3', 't1')); print(a.about())", "s2")
        check("same() joins what is known of both", "Rex" in said and "Brightwork" in said, said)
        said = server.run_code('b = entity("Anna")', "s3")
        check("things settled as one are asked about once",
              said.count("Is Anna (t4)") == 1 and "'t1'" in said, said)

        # --- what a reader would not understand is asked back, and kept anyway ---
        said = server.run_code('olga.say("She is moving to Berlin.")', "s1")
        check("a sentence that does not name its thing is asked about",
              "does not name Olga" in said and "Kept: #" in said, said)

        # --- an event, its time and the people in it ---
        said = server.run_code(
            'tom = entity("Tom")\n'
            'w = event("Anna\'s wedding", "Anna marries Tom on 2027-06-12 in Porto.", when="2027-06-12", who=[anna, tom])', "s1")
        records = [json.loads(line) for line in (Path(where) / "structure.jsonl").read_text().splitlines()]
        wedding = next(r for r in records if r.get("name") == "Anna's wedding")
        check("an event is a thing of kind event", wedding["kind"] == "event")
        check("its sentence is about the event and the people",
              any(r.get("when") == "2027-06-12" and r["about"][0] == wedding["thing"] and len(r["about"]) == 3
                  for r in records), str(records[-2:]))

        # --- errors are the agent's to read; what was kept before stays kept ---
        said = server.run_code('olga.say("Olga speaks German.")\n1/0', "s1")
        check("an error is shown", "ZeroDivisionError" in said, said)
        check("a write before the error is kept", "Olga speaks German." in base.facts.read_text())
        said = server.run_code('olga.say("   ")', "s1")
        check("a blank fact is refused with what to do", "A fact is a sentence" in said, said)

        # --- now is the agent's: when the facts were said; without it, the clock, and asked ---
        said = server.run_code('olga.say("Olga plays chess.")', "s1", now="2020-01-03")
        check("the agent's now dates the entry", "## #" in base.facts.read_text()
              and "2020-01-03 00:00:00 · conversation\nOlga plays chess." in base.facts.read_text())
        check("given now, nothing is asked about it", "Pass `now`" not in said, said)
        said = server.run_code('olga.say("Olga has a cat.")', "s1")
        check("without now, the clock, and the agent is asked", "Pass `now`" in said, said)
        said = server.run_code('olga.say("Olga has a cat.")', "s1", now="Thursday")
        check("an unreadable now is said so", "could not be read" in said, said)

        # --- what came in is kept as it came, and what was not told from it is asked about ---
        server.structure.heard("s1", "Olga moved to Berlin. Tom bought a boat.", "conversation")
        said = server.run_code('olga.say("Olga moved to Berlin.")', "s1", now="2020-01-04")
        check("a heard name nothing told has is asked about", 'has Tom: "Tom bought a boat."' in said
              and "Olga moved to Berlin" not in said.split("The memory asks:")[-1], said)
        server.structure.heard("s1", "Thanks, yeah. Olga's birthday is March 3rd, and I've been dreading it.")
        said = server.run_code('olga.say("Olga was born on March 3.")', "s1", now="2020-01-04")
        check("a retelling is not asked about, nor what names nothing", "The memory asks" not in said, said)
        check("heard text is kept as it came", "Tom bought a boat." in (Path(where) / "heard.md").read_text())
        said = server.run_code('link(olga, tom, as_="neighbour")', "s1", now="2020-01-04")
        check("a link with only a word is kept and asked about", "a link with no sentence" in said
              and "has no sentence" in said, said)

        # --- forget reaches the index: a forgotten entry is gone from about() ---
        asyncio.run(base.forget("#2"))
        said = server.run_code('print(anna.about())', "s1")
        check("a forgotten entry is gone from about()", "Lisbon" not in said and "sister" in said, said)
        check("the request to forget is about the same thing", "forgotten, and 1 entry was taken out: #2" in said
              and "· forget: " in said, said)
        # --- forget reaches what was heard: the sentence goes to the bin, the rest stays ---
        server.structure.heard("s1", "Anna got a dog called Rex. Anna's hairdresser is Olga.")
        said = server.run_code('anna.say("Anna has a dog called Rex.")', "s1", now="2020-01-05")
        number = int(said.split("Kept: #")[1].split(" ")[0])
        asked_for = []

        async def model(prompt: str) -> str:
            asked_for.append(prompt)
            return next(line.split(".")[0] for line in prompt.splitlines() if "Rex" in line)

        real, base._haiku = base._haiku, model
        try:
            gone = asyncio.run(base.forget(f"#{number}", now="2020-01-06"))
        finally:
            base._haiku = real
        heard = (Path(where) / "heard.md").read_text()
        check("forget: the heard sentence is taken out, the rest of the message stays",
              "Rex" not in heard and "Anna's hairdresser is Olga." in heard, heard)
        check("forget: the model is shown only sentences that may say it", asked_for and
              "Tom bought a boat" not in asked_for[0] and "hairdresser" in asked_for[0], asked_for)
        check("forget: the answer says what left heard.md", "heard #" in gone and "Rex" in gone, gone)
        listed = asyncio.run(base.forgotten())
        check("forgotten lists the entry and the heard sentence", listed.count("Rex") == 2
              and "- heard #" in listed, listed)
        server.structure.heard("s1", "Anna's dog Rex barks.")
        server.structure.forget_heard([(server.structure.pending["s1"][0], "Anna's dog Rex barks.")])
        check("a forgotten sentence is not asked about as untold",
              "Rex" not in server.run_code('print(1)', "s1", now="2020-01-06"))

        # --- the world: entries said into it, and a forgotten one taken out of it, for good ---
        from proto.world import Worker, _text_columns
        server.world = Worker(Path(where) / "world", quiet=3600)
        try:
            server.run_code('mia = entity("Mia", "Mia is the user\'s niece.")\n'
                            'link(mia, anna, "Mia is Anna\'s daughter and plays the cello.")', "s1", now="2020-01-07")
            server.world.send("sync", server.structure, server.held(), wait=True)
            names = {t["name"] for t in server.world.image["things"].values()}
            check("the world holds the proto's things", {"Anna", "Mia"} <= names, str(names))
            number = max(n for n, t in server.held().items() if "cello" in t)
            real, base._haiku = base._haiku, (lambda prompt: _none())
            try:
                asyncio.run(base.forget(f"#{number}"))
            finally:
                base._haiku = real
            import sqlite3
            conn = sqlite3.connect(Path(where) / "world" / "world.db")
            left = [t for t, c in _text_columns(conn)
                    if conn.execute(f'SELECT count(*) FROM "{t}" WHERE instr("{c}", "cello") > 0').fetchone()[0]]
            check("a forgotten entry's words are nowhere in the world", not left, str(left))
        finally:
            server.world = None

        check("the run tool is one more tool beside the contract's",
              {"run", "tell", "ask", "search_memory", "forget"} <= {t.name for t in asyncio.run(base.server.list_tools())})

    print(f"\n{len(failures)} failed" if failures else "\nall passed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
