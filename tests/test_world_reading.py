"""The world reading the journal in the quiet: values and links with their quotes, into the image.

Run: .venv/bin/python tests/test_world_reading.py           # no model calls: reader and judge stood in
"""
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from memory import journal as base  # noqa: E402
from memory import server  # noqa: E402
from memory.model import Structure  # noqa: E402
from memory.world import Mirror, image_of  # noqa: E402

failures: list[str] = []


def check(name: str, condition: bool, detail: str = "") -> None:
    print(f"{'PASS' if condition else 'FAIL'}  {name}" + (f"  — {detail}" if detail and not condition else ""))
    if not condition:
        failures.append(name)


class Reader:
    """Stands in for `memory.parse.read`: says what each session's text holds, from a script."""

    def __init__(self):
        self.texts = []

    def __call__(self, text, want="", source="", fields=None):
        self.texts.append(text)
        got = {"things": [], "links": [], "dropped": []}
        if "Brightwork" in text:
            got["things"] += [
                {"name": "I", "kind": "person", "values": {}},
                {"name": "Brightwork", "kind": "company", "values": {}},
                {"name": "Priya", "kind": "person", "values": {"role": {"value": "designer", "quote": "Priya, a designer"}}},
                {"name": "Rachel", "kind": "person", "values": {}},
            ]
            got["links"] += [
                {"from": "I", "to": "Brightwork", "as": "works at", "says": "The user works at Brightwork",
                 "quote": "I started at Brightwork"},
                {"from": "Rachel", "to": "Brightwork", "as": "worked at", "says": "Rachel worked at Brightwork",
                 "quote": "Rachel left Brightwork"},
            ]
            got["dropped"].append(("Priya", "age", 30, "no such words"))
        if "Anna" in text:
            got["things"].append({"name": "Anna", "kind": "person",
                                  "values": {"city": {"value": "Porto", "quote": "Anna moved to Porto"}}})
        return got


class Judge:
    """Stands in for the decision model: answers who-is-who from a script, and whether a link holds."""

    def __init__(self, who: str):
        self.who, self.asked = who, []

    def choice(self, state, question, options):
        self.asked.append(question)
        names = [n for n, _ in options]
        if "still hold" in question:
            pick = "ended" if "Rachel" in question else "now"
        else:
            pick = self.who if self.who in names else "none of these"
        return {"choice": pick, "p": {n: (0.9 if n == pick else 0.1 / max(1, len(names) - 1)) for n in names}}


class Later:
    """Stands in for a reader that takes the context apart from the text: reads only the new entries."""

    def __init__(self):
        self.calls = []

    def __call__(self, text, want="", source="", fields=None, context=""):
        self.calls.append((text, context))
        got = {"things": [{"name": n, "kind": "person", "values": {}} for n in ("I", "Rachel", "Tom", "Brightwork")
                          if n in text or n == "I"], "links": [], "dropped": []}
        if "My manager is Rachel" in text:
            got["links"].append({"from": "Rachel", "to": "I", "as": "manager of", "says": "Rachel is the user's manager",
                                 "quote": "My manager is Rachel"})
        if "Alex" in text:
            got["things"].append({"name": "Alex", "kind": "person", "values": {}})
            got["links"].append({"from": "Rachel", "to": "Alex", "as": "worked with", "says": "Rachel worked with Alex",
                                 "quote": "Rachel worked with Alex"})
        if "Rachel left" in text:
            got["links"].append({"from": "Rachel", "to": "Brightwork", "as": "left", "says": "Rachel left Brightwork",
                                 "quote": "Rachel left Brightwork"})
        return got


class Later_judge(Judge):
    """Ends Rachel's manager link only when shown the later entry that says she left."""

    def choice(self, state, question, options):
        self.asked.append((state, question))
        names = [n for n, _ in options]
        pick = "now" if "still hold" in question else names[0]
        return {"choice": pick, "p": {n: (0.9 if n == pick else 0.1 / max(1, len(names) - 1)) for n in names}}

    def noul(self, state, question, true, false):
        self.asked.append((state, question))
        if "the user themself" in question:
            return {"p": {"yes": 0.9 if "\u00abAlex\u00bb" in question else 0.1, "no": 0.1}}
        ended = "no longer holds" in question and "Rachel left" in state.partition("Later:")[2]
        return {"p": {"yes": 0.9 if ended else 0.5, "no": 0.1 if ended else 0.5}}


def later_entries() -> None:
    """A link said in one reading and ended in a later one; chunks cut by size, with the context."""
    import memory.world as pw

    with tempfile.TemporaryDirectory() as where:
        base.facts = Path(where) / "facts.md"
        server.structure = Structure(Path(where) / "structure.jsonl", base._keep, server.held)
        server.sessions.clear()
        server.run_code('me = entity("The user")\nrachel = entity("Rachel")\n'
                        'rachel.say("My manager is Rachel.")\n', "claude-code")
        mirror = Mirror(Path(where) / "world")
        mirror.sync(server.structure, server.held())
        reader, judge = Later(), Later_judge(who="")
        mirror.read_journal(reader=reader, judge=judge)
        manager = [l for l in mirror.from_journal["links"] if l["type"] == "manager of"]
        check("a link read holds while nothing later says otherwise", manager and manager[0]["holds"] == "now",
              json.dumps(mirror.from_journal["links"]))

        server.run_code('tom = entity("Tom")\ntom.say("Tom joined the team.")\n'
                        'rachel.say("Rachel left Brightwork.")\n', "claude-code")
        mirror.sync(server.structure, server.held())
        cut, pw.CHUNK_CHARS = pw.CHUNK_CHARS, 60
        try:
            mirror.read_journal(reader=reader, judge=judge)
        finally:
            pw.CHUNK_CHARS = cut
        text, context = reader.calls[-1]
        check("a cut by size: the reader gets the entries before as context, apart from the text",
              "Rachel left" in text and "Tom joined" in context and "Tom joined" not in text, str(reader.calls[-1]))
        check("the context names what the image knows", "Rachel manager of The user" in context, context)
        manager = [l for l in mirror.from_journal["links"] if l["type"] == "manager of"][0]
        check("a later entry ends a link read earlier, asked with its date",
              manager["holds"] == "ended" and manager.get("ended_in") == 3, json.dumps(manager))
        check("the image says which entry ended it",
              any(l.get("ended_in") == 3 for l in mirror.image()["links"] if l["type"] == "manager of"))
        mirror._forget_read({3})
        manager = [l for l in mirror.from_journal["links"] if l["type"] == "manager of"][0]
        check("forgetting the entry that ended it unends it", manager["holds"] == "unsaid"
              and "ended_in" not in manager, json.dumps(manager))
        check("the ontology is off unless asked for", not pw.ontology())

        server.run_code('rachel.say("Rachel worked with Alex.")\n', "claude-code")
        mirror.sync(server.structure, server.held())
        mirror.read_journal(reader=reader, judge=judge)
        user = [g for g, t in mirror.image()["things"].items() if t.get("user")]
        alex = [l for l in mirror.from_journal["links"] if l["type"] == "worked with"]
        check("the user's own name, said by the judge, binds to the one user thing",
              user == ["t1"] and alex and alex[0]["object"] == "t1", json.dumps([user, alex]))
        check("and is kept, so it binds from then on", "alex" in mirror.from_journal.get("user_names", []))


def main() -> int:
    with tempfile.TemporaryDirectory() as where:
        base.facts = Path(where) / "facts.md"
        server.structure = Structure(Path(where) / "structure.jsonl", base._keep, server.held)
        server.sessions.clear()
        server.run_code('me = entity("The user")\n'
                        'me.say("I started at Brightwork in March; Priya, a designer, sits next to me.")\n'
                        'rachel = entity("Rachel")\n'
                        'rachel.say("Rachel left Brightwork last month.")\n', "s1")
        server.run_code('anna = entity("Anna", "Anna is my sister.")\n'
                        'anna2 = entity("Anna Lee", "Anna Lee is a client.")\n'
                        'anna.say("Anna moved to Porto in September.")\n'
                        'marco = entity("Marco", kind="person")\n', "s2")
        mirror = Mirror(Path(where) / "world")
        mirror.sync(server.structure, server.held())

        reader, judge = Reader(), Judge(who="t3")
        got = mirror.read_journal(reader=reader, judge=judge)
        check("entries that follow each other are read together, once, sessions or not",
              len(reader.texts) == 1 and "Rachel left" in reader.texts[0] and "Anna moved" in reader.texts[0],
              str(reader.texts))
        check("with their numbers and dates", "#2 · " in reader.texts[0], reader.texts[0][:300])
        check("and with what is known of the things they name", "Already known" in reader.texts[0]
              and "- Rachel" in reader.texts[0], reader.texts[0][:300])
        image = mirror.image()
        groups = {t["name"]: g for g, t in image["things"].items()}

        check("'I' is the user, and the user is marked", image["things"][groups["The user"]].get("user") is True
              and any(l["subject"] == groups["The user"] for l in image["links"]), json.dumps(image["links"]))
        anna = "t3"       # entity("Anna"); entity("Anna Lee") is t4
        check("a value is on its thing, with the entry its quote stands in",
              any(v["value"] == "Porto" and v["quote"] == "Anna moved to Porto"
                  for v in image["values"].get(anna, {}).get("city", [])), json.dumps(image["values"]))
        porto = image["values"][anna]["city"][0]["entry"]
        check("and that entry is the one that says it", "Porto" in server.held()[porto], server.held()[porto])
        check("two who could be Anna: the judge was asked, and its answer bound it",
              any("Anna" in q for q in judge.asked) and "t4" not in image["values"], str(judge.asked))
        check("a name nobody holds is a thing the world read",
              image["things"].get(groups.get("Priya"), {}).get("source") == "read", json.dumps(image["things"]))
        rachel_link = [l for l in image["links"] if l["subject"] == groups["Rachel"]]
        check("'left' ends a link rather than adding one", rachel_link and rachel_link[0]["holds"] == "ended",
              json.dumps(rachel_link))
        check("read links carry their entry, sentence and quote",
              all(l.get("entry") and l.get("says") and l.get("quote") for l in image["links"] if l["source"] == "read"))
        marco = [t for t in image["things"].values() if t["name"] == "Marco"]
        check("a thing the host named and nobody said anything of is in the image, as the host's kind",
              marco and marco[0]["source"] == "host" and marco[0]["class"] == "Person", json.dumps(image["things"]))
        check("the reading counts what the checks dropped", got.get("dropped") == 1, str(got))

        again = mirror.read_journal(reader=reader, judge=judge)
        check("what was read is not read again", len(reader.texts) == 1 and again.get("entries") == 0, str(again))

        world_dir = Path(where) / "world"
        check("the image is on disk for a reader outside the server",
              image_of(world_dir)["values"] == json.loads(json.dumps(image["values"])))

        # A forgotten entry takes what was read from it.
        mirror._forget_read({porto})
        image = mirror.image()
        check("a forgotten entry's values leave the image", anna not in image["values"],
              json.dumps(image["values"]))
        rachel_entry = rachel_link[0]["entry"]
        mirror._forget_read({rachel_entry})
        image = mirror.image()
        check("and its links", not any(l["entry"] == rachel_entry for l in image["links"] if l["source"] == "read"))
        check("and a read thing nothing stands on any more",
              all(t["name"] != "Brightwork" or any(l["object"] == g for l in image["links"])
                  for g, t in image["things"].items()), json.dumps(image["things"]))
        check("and image_of shows it gone", "Porto" not in json.dumps(image_of(world_dir)))

        # A name two things could be, and a judge that says neither: kept apart, never merged.
        unsure = Mirror(Path(where) / "world2")
        unsure.sync(server.structure, server.held())
        unsure.read_journal(reader=Reader(), judge=Judge(who="nobody"))
        img = unsure.image()
        annas = [g for g, t in img["things"].items() if t["name"] == "Anna"]
        check("a judge that says neither leaves the name a thing of its own",
              any(g.startswith("r:") for g in annas) and "t3" not in img["values"], json.dumps(img["things"]))

    later_entries()
    print(f"\n{'all passed' if not failures else f'{len(failures)} failed'}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
