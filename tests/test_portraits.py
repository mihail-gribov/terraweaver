"""A thing that came in as a bare name, described in words, read into a class.

The whole circuit with the outside models stood in for: the walk down the tree of classes, the
one open call that gives a class and the code to fill the thing in, that code running by the
door a host's code runs through, and the loop that hands a failure back and asks again.

The stand-ins are the point. Every defect this file was written after took a five-minute live
run to find, and not one of them was a logic error a test could catch by walking the same path
twice: each was the world telling the reader something other than what was so — an example
naming a class this world has not got, a short form that only works for words already here, a
promise that a missing relation type would be made. A reader whose answers are fixed in advance
is the second party those needed, at no cost.

Run: .venv/bin/python tests/test_portraits.py
"""
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from terraweaver import authoring, ontology as ont, portraits
from terraweaver.runtime import WorldRuntime

failures: list[str] = []


def check(name: str, condition: bool, detail: str = "") -> None:
    print(f"{'PASS' if condition else 'FAIL'}  {name}" + (f"  — {detail}" if detail and not condition else ""))
    if not condition:
        failures.append(name)


class AJev:
    """Stands in for the Jev: answers each choice with the option named in turn."""

    def __init__(self, answers: list[str]):
        self.answers, self.asked = list(answers), []

    def choose(self, state: str, question: str, options: dict) -> dict:
        self.asked.append((question, list(options)))
        want = self.answers.pop(0) if self.answers else portraits.NEW_ONE
        return {want: 1.0} if want in options else {}


class Engineer:
    """Stands in for the engineer: hands back answers in turn, keeping what it was asked."""

    def __init__(self, answers: list[dict]):
        self.answers, self.asked = list(answers), []

    def json(self, system: str, asked: str):
        self.asked.append(asked)
        return self.answers.pop(0) if self.answers else None


def a_world():
    work = Path(tempfile.mkdtemp(prefix="portraits-"))
    here = Path(__file__).resolve().parent.parent / "ontology" / "core"
    runtime = WorldRuntime(str(work / "w.db"), fixture=None, specs=ont.base_specs(here), selves=True)
    authoring.install(runtime.world, work / "grown")
    return runtime


def main() -> int:
    # --- a bare name is noted, and the agent is asked about it in its own words ---
    rt = a_world()
    rt.start_task("k", "record what the user said about Rome", "recording")
    made = rt.run('rome = Thing.identify(name="Rome")[0]', "k")
    check("a name nobody here has is recorded by the lookup that asked for it",
          made["ok"] and "Rome" in (made.get("new_variables") or {}).get("rome", ""),
          str(made.get("new_variables") or made.get("error")))
    check("and the agent is asked about it, by the variable it wrote",
          any(line.startswith('rome.describe(') for line in made.get("clarify") or []),
          str(made.get("clarify")))
    check("the asking line is the one its class carries",
          any("why it is in this world" in line for line in made.get("clarify") or []),
          str(made.get("clarify")))
    check("nothing is waiting to be read while nothing has been said",
          portraits.unread(rt.world) == [] and len(portraits.still_only_a_name(rt.world)) == 1)

    # --- said in words, the question closes itself: describing is the answer ---
    rt.run('rome.describe("Rome is the capital of Italy; the user lived there until 2019")', "k")
    check("saying something about it leaves one prose-fact to read",
          len(portraits.unread(rt.world)) == 1 and portraits.still_only_a_name(rt.world) == [],
          str(portraits.unread(rt.world)))
    check("and the question that asked for it has closed itself",
          not [q for q in rt.world.questions.open_(limit=9) if q.kind == "what_is_it"])

    # --- the walk, the class, the code, the links ---
    jev = AJev([portraits.NEW_ONE])
    engineer = Engineer([{
        "class": {"name": "City", "brief": "a city, town or village",
                  "description": "A populated place with a permanent community.",
                  "attributes": [{"name": "population",
                                  "description": "how many people live there", "type": "int"}]},
        "code": 'it.population = 2800000\nit.describe("where the user lived until 2019")',
    }])
    tally = portraits.read_them(rt.world, engineer, jev=jev, run=rt._the_world_writes)
    rt._hand_back_what_moved(tally.pop("moved", []))
    check("the prose-fact is read, the class made, the code run",
          tally == {"read": 1, "placed": 1, "defined": 1, "ran": 1, "failed": 0, "gave_up": 0},
          str(tally))
    rome = rt.world.find(rt.world.classes["City"], name="Rome").matches[0]
    check("the thing is read under the class that was made", type(rome).__name__ == "City")
    check("what the words gave is on it", rome.population == 2800000, str(rome.population))
    check("and it joined nothing, because these words joined nothing",
          rome.relations() == [], str([r.display_name() for r in rome.relations()]))

    # --- the new class sits under the one the walk stopped at, and inherits its question ---
    city = rt.world.classes["City"]
    check("the class is a kind of what the walk stopped at", city._spec.get("parent") == "Thing")
    check("it is reachable next time the walk comes down",
          "City" in portraits.children_of(rt.world, "Thing"))
    check("it says nothing of its own about what to say, so it says its parent's",
          "what_to_say" not in city._spec
          and ont.what_to_say(city, rt.world.classes) == ont.what_to_say(
              rt.world.classes["Thing"], rt.world.classes))
    check("and it is described in prose, by somebody",
          [d["source"] for d in city._spec["descriptions"]] == ["world"],
          str(city._spec.get("descriptions")))

    # --- the walk is offered the children plus a way out, by their short line ---
    asked = jev.asked[0][1]
    # Event is a root of its own — a thing is, an event happens — so it is not among the kinds
    # of Thing the walk comes down through.
    check("the walk offers the kinds of Thing and a way out",
          set(asked) == {"AIAgent", "Person", portraits.NEW_ONE}, str(asked))
    # An account of a thing says what it is to other things — "the capital of Italy" — and that
    # is a fact worth having. What went wrong was never that the engineer wrote links; it was
    # how. Two guards, and both are in what it is shown.
    asked_for = engineer.asked[0]
    check("the engineer may join this thing to another, and is shown the word for it",
          "it.set_capital_of(italy)" in asked_for, asked_for[-900:])
    check("the other end is looked up by a call that cannot create one",
          'Thing.get(name="Italy")' in asked_for and ".identify(" not in asked_for,
          asked_for[-900:])
    check("and it is shown what this thing is already joined to, so it does not say it twice",
          "already joined to" in asked_for, asked_for[-900:])

    # There is no case here for a thing the world named itself: this door names nothing. That
    # it once did — reaching for "Italy" out of an account of Rome — is the defect the check
    # above guards against. `runtime._reachable` still words a question about such a thing by
    # a lookup anybody can run, for whenever the world does make one.

    # --- the loop: a line the world refuses comes back, and the next answer is run ---
    rt.run('turin = Thing.identify(name="Turin")[0]\n'
           'turin.describe("Turin is a city in the north of Italy")', "k")
    loop_jev = AJev(["City"])
    loop_engineer = Engineer([
        {"class": None, "code": 'it.population = 900_000\nit.relate(nowhere, "near")'},
        {"class": None, "code": 'it.describe("in the north")'},
    ])
    tally = portraits.read_them(rt.world, loop_engineer, jev=loop_jev, run=rt._the_world_writes)
    rt._hand_back_what_moved(tally.pop("moved", []))
    check("a refused line is handed back and the next answer runs",
          tally["ran"] == 1 and tally["gave_up"] == 0 and len(loop_engineer.asked) == 2, str(tally))
    check("and what came back carried the world's own answer to it",
          "the record answered" in loop_engineer.asked[1], loop_engineer.asked[1][-300:])
    check("the walk put it under the class that was already here",
          type(rt.world.find(rt.world.classes["City"], name="Turin").matches[0]).__name__ == "City")
    after = rt.run('print(type(turin).__name__)', "k")
    check("and what the agent is still holding is the thing as it now is",
          (after["output"] or "").strip() == "City", after["output"] or str(after.get("error")))

    # --- a reading is written against the prose-fact, not against the thing ---
    rows = rt.world.store.conn.execute(
        "SELECT statement_id, entity_id, read_at, became FROM portraits").fetchall()
    check("every reading names the prose-fact it read and when it read it",
          len(rows) == 2 and all(r[0] and r[2] for r in rows), str(rows))
    check("what the world wrote itself is not an account for it to read back",
          portraits.unread(rt.world) == [], str(portraits.unread(rt.world)))
    rt.run('turin.describe("Turin was the first capital of Italy")', "k")
    check("so saying more about it leaves something to read again",
          len(portraits.unread(rt.world)) == 1, str(portraits.unread(rt.world)))

    # --- a reader that says nothing usable costs the reading, never the thing ---
    silent = portraits.read_them(rt.world, Engineer([]), jev=AJev(["City"]),
                                 run=rt._the_world_writes)
    silent.pop("moved", None)
    check("an engineer that answers nothing leaves the words for a later pass",
          silent["failed"] == 1 and silent["read"] == 0, str(silent))
    turin = [e for e in rt.world.all("City", limit=None, history=True)
             if str(e.display_name()) == "Turin"]
    check("and the thing is exactly where it was",
          len(turin) == 1 and type(turin[0]).__name__ == "City",
          str([(str(e.display_name()), type(e).__name__)
               for e in rt.world.all("City", limit=None, history=True)]))

    print()
    if failures:
        print(f"{len(failures)} failed: {', '.join(failures)}")
        return 1
    print("all portrait tests passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
