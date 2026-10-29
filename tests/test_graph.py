"""Tests for the graph: texts, the entities they mention, links, topics (memory/graph.py).

Run: .venv/bin/python tests/test_graph.py           # no model calls: a reader that answers as told
     .venv/bin/python tests/test_graph.py --live    # the TV story through Nemotron Super
"""
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from memory.graph import USER, Graph  # noqa: E402

failures: list[str] = []


def check(name: str, condition: bool, detail: str = "") -> None:
    print(f"{'PASS' if condition else 'FAIL'}  {name}" + (f"  — {detail}" if detail and not condition else ""))
    if not condition:
        failures.append(name)


# The TV story: one talk on Monday, one a month later.
TV = [
    (1, "2026-10-26 19:00:00", "My wife Mila and I want a new TV for the living room."),
    (2, "2026-10-26 19:05:00", "The Sony TV is too expensive for me."),
    (3, "2026-10-26 19:07:00", "The LG TV has glare in our bright living room."),
    (4, "2026-10-26 19:10:00", "Let's take the Samsung S90D."),
    (5, "2026-11-28 10:00:00", "We went with the LG TV after all, we got blinds."),
]


def journal(entries):
    return lambda: [(n, f"{n} · {when} · the user", text) for n, when, text in entries]


def told(answers):
    """A reader that gives, for each entry in turn, the reading it is told to."""
    queue = list(answers)
    return lambda system, prompt: queue.pop(0) if queue else {}


def first(state, question, options):
    """A decision model that answers as the state says, else the first option."""
    return next((name for name, _ in options if f"[{name}]" in question + state), options[0][0])


def said_of_self() -> None:
    """What the user says of themselves: a link from the user, in the entry's words, with the day it
    happened and a class from the decision model; an answer gets every one in the found topics."""
    entries = [(1, "2023-05-05 10:00:00", "By the way, two weeks ago I planted 12 tomato saplings."),
               (2, "2023-05-06 10:00:00", "I wake up at 8:30 am on Saturdays."),
               (3, "2023-05-20 10:00:00", "Last Saturday I woke up at 7:30 am, a good start.")]
    readings = [
        {"links": [{"from": "I", "relation": "planted", "to": "12 tomato saplings", "quote": "I planted 12 tomato saplings",
                    "when": "2023-04-21"}],
         "topics": [{"topic": "new", "name": "gardening", "text": "Planted tomatoes (2023-04-21)."}]},
        {"links": [{"from": "the user", "relation": "wakes up at", "to": "8:30 am on Saturdays",
                    "quote": "I wake up at 8:30 am on Saturdays", "when": "last week"}],
         "topics": [{"topic": "new", "name": "wake-up time", "text": "Wakes at 8:30 on Saturdays."}]},
        {"links": [{"from": "the user", "relation": "woke up at", "to": "7:30 am", "quote": "I woke up at 7:30 am",
                    "when": "2023-05-13"}],
         "topics": [{"topic": 2, "name": "wake-up time", "text": "Wakes at 8:30 on Saturdays; 7:30 last Saturday."}]},
    ]
    classes = {"planted": "did", "wakes up at": "now", "woke up at": "did", "gardening": "interest", "wake-up": "habit"}
    decide = lambda state, question, options: next(c for k, c in classes.items() if k in state)  # noqa: E731
    with tempfile.TemporaryDirectory() as tmp:
        goes_on = lambda message, t: (0.9 if "plant" in message and t["name"] == "gardening"  # noqa: E731
                                      else 0.5 if "Saturday" in message and t["name"] == "wake-up time" else 0.1)
        g = Graph(Path(tmp), journal(entries), reader=told(readings), decide=decide, goes_on=goes_on)
        g.wait(10)
        own = {(l["relation"], l["to"], l.get("when"), l.get("class")) for l in g.links if l["from"] == USER}
        check("the user's own links, in the entry's words, with the day it happened and a class",
              ("planted", "12 tomato saplings", "2023-04-21", "did") in own, str(own))
        check("a 'when' that is not a day is not kept", ("wakes_up_at", "8:30 am on Saturdays", None, "now") in own, str(own))
        check("a topic gets a kind", {t["topic"]: t.get("kind") for t in g.latest_topics()} == {1: "interest", 2: "habit"},
              str(g.latest_topics()))
        facts = g.facts_for([1], "what did I do in the garden two weeks ago?")
        check("an answer gets what the user said of themselves, by class, with days",
              'planted 12 tomato saplings: "I planted 12 tomato saplings" (fact 1, said 2023-05-05, happened 2023-04-21)'
              in facts and "did —" in facts, facts)
        recalled = g.recall("I want to plant peppers next", [1])
        check("beside a message: the topic it goes on with, and what the user said in it",
              recalled.startswith('We discussed this before: "gardening", last on 2023-05-05') and "planted 12 tomato saplings" in recalled
              and "wake" not in recalled, recalled)
        check("a topic near by meaning that the message does not go on with is not recalled",
              g.recall("what's the weather?", []) == "")
        maybe = g.recall("busy Saturday ahead", [])
        check("not sure: the topic only named, in a line, for the agent to ask",
              maybe.startswith('Possibly related: "wake-up time", last on 2023-05-20') and "Where it stood" not in maybe, maybe)
        check("found by meaning alone, with no entry found: recalled when the message goes on with it",
              g.recall("thinking of planting peppers", []).startswith('We discussed this before: "gardening"'))
        facts = g.facts_for([2], "what time do I wake up on Saturdays?")
        check("every fact of a found topic, not only the found ones, the newest first",
              facts.index("fact 3") < facts.index("fact 2"), facts)


def personal_world() -> None:
    """The user's world, half fixed: the same parts for every person, one value or a list, the newest
    holding, an item ended by an entry kept as was; values in the entry's own words."""
    entries = [(1, "2026-03-01 10:00:00", "My wife Mila's birthday is on 3 May."),
               (2, "2026-03-01 10:05:00", "I am the father of Lev, he is seven."),
               (3, "2026-03-02 10:00:00", "I work at Acme as a designer and I bought a Samsung TV."),
               (4, "2026-06-01 10:00:00", "I moved to Globex, and we sold the Samsung and got an LG C4.")]
    readings = [
        {"entities": [{"name": "Mila", "kind": "person", "as": "wife Mila"}],
         "links": [{"from": "Mila", "relation": "spouse", "to": "I", "quote": "My wife Mila"},
                   {"from": "Mila", "relation": "born_on", "to": "3 May", "quote": "birthday is on 3 May"}]},
        {"entities": [{"name": "Lev", "kind": "person", "as": "Lev"}],
         "links": [{"from": "I", "relation": "parent", "to": "Lev", "quote": "I am the father of Lev"},
                   {"from": "Lev", "relation": "age", "to": "seven", "quote": "he is seven"}]},
        {"entities": [{"name": "Acme", "kind": "organisation", "as": "Acme"}, {"name": "Samsung TV", "kind": "TV", "as": "Samsung TV"}],
         "links": [{"from": "I", "relation": "works_at", "to": "Acme", "quote": "I work at Acme"},
                   {"from": "I", "relation": "job", "to": "designer", "quote": "as a designer"},
                   {"from": "I", "relation": "owns", "to": "Samsung TV", "quote": "I bought a Samsung TV"}]},
        {"entities": [{"name": "Globex", "kind": "organisation", "as": "Globex"}, {"name": "LG C4", "kind": "TV", "as": "LG C4"},
                      {"name": "Samsung TV", "kind": "TV", "as": "the Samsung"}],
         "links": [{"from": "I", "relation": "works_at", "to": "Globex", "quote": "I moved to Globex"},
                   {"from": "I", "relation": "owns", "to": "Samsung TV", "quote": "we sold the Samsung", "ended": True},
                   {"from": "I", "relation": "owns", "to": "LG C4", "quote": "got an LG C4"}]},
    ]
    with tempfile.TemporaryDirectory() as tmp:
        g = Graph(Path(tmp), journal(entries), reader=told(readings), decide=first, goes_on=lambda m, t: 0.0)
        g.wait(10)
        g2 = Graph(Path(tmp) / "bycode", journal(entries[:1]), reader=told([{"entities": [{"name": "Mila", "kind": "person", "as": "Mila"}]}]),
                   decide=first, goes_on=lambda m, t: 0.0)
        g2.wait(10)
        check("'my wife Mila' is the user's spouse by code, whatever the reader gave",
              [(l["from"], l["relation"], l["to"]) for l in g2.links] == [("Mila", "spouse", USER)], str(g2.links))
        world = "\n".join(g.world_lines(USER, gaps=True))
        check("the user's people: a spouse, a child said the other way round", "spouse: Mila (fact 1" in world
              and "child: Lev (fact 2" in world, world)
        check("one value: the newest holds, the older was", "works at: Globex [organisation] (fact 4" in world and "was: Acme" in world, world)
        check("a list: an item ended by an entry is kept as was", "owns: LG C4 [tv] (fact 4" in world
              and "was: Samsung TV [tv] (fact 4, 2026-06-01) — ended" in world, world)
        check("what is not known yet is said", "not known yet: born on, lives in" in world, world)
        mila = "\n".join(g.world_lines("Mila"))
        check("every person has the same parts, values in the entry's words", "born on: 3 May (fact 1" in mila
              and "spouse: the user" in mila, mila)
        said = g.recall("What should I get my wife for her birthday? And is the TV ok for games?", [])
        check("beside a message: the parts of the user's world it speaks of, and the people's worlds",
              "owns: LG C4" in said and "spouse: Mila" in said and "born on: 3 May" in said and "works at" not in said, said)
        check("an answer gets the user's world", "works at: Globex" in g.facts_for([4], "where do I work?"))


def filled_from_messages() -> None:
    """The world is filled as the user speaks: "my wife" gives the user a wife whose name is not known
    yet; when an entry names her, she is that wife — joined, with the fact that joined them."""
    entries = [(1, "2026-03-01 10:00:00", "My wife loves jazz, I want to get her concert tickets."),
               (2, "2026-03-05 10:00:00", "My wife's birthday is on 3 May."),
               (3, "2026-03-20 10:00:00", "Mila, my wife, prefers small venues.")]
    readings = [{}, {"links": [{"from": "the user's wife", "relation": "born_on", "to": "3 May", "quote": "birthday is on 3 May"}]},
                {"entities": [{"name": "Mila", "kind": "person", "as": "Mila"}]}]
    with tempfile.TemporaryDirectory() as tmp:
        g = Graph(Path(tmp), journal(entries[:2]), reader=told(readings), decide=first, goes_on=lambda m, t: 0.0)
        g.wait(10)
        world = "\n".join(g.world_lines(USER, gaps=True))
        check("'my wife' with no name: the user has a wife, her name not known yet",
              "spouse: the user's wife (name not known yet)" in world and "the name of the user's wife" in world, world)
        check("what is said of her is hers before she is named", "born on: 3 May" in "\n".join(g.world_lines("the user's wife")))
        g.entries = journal(entries)
        g.wake()
        g.wait(10)
        world = "\n".join(g.world_lines(USER, gaps=True))
        check("named later: the same wife, now Mila", "spouse: Mila (fact" in world and "the user's wife" not in world, world)
        check("what was said of her before she was named is Mila's", "born on: 3 May" in "\n".join(g.world_lines("Mila")))
        check("the join is kept with the fact that made it", g.aliases.get("the user's wife", {}).get("fact") == 3, str(g.aliases))
        kept = json.loads((Path(tmp) / "world.json").read_text())
        check("the world is kept as a structure: every part, filled or empty",
              kept[USER]["parts"]["spouse"]["now"][0]["value"] == "Mila" and kept[USER]["parts"]["born_on"]["now"] == []
              and kept["Mila"]["known_as"] == ["the user's wife"], json.dumps(kept[USER]["parts"]["spouse"]))
        again = Graph(Path(tmp), journal(entries), reader=told([]), decide=first)
        check("the join holds across a restart", "spouse: Mila" in "\n".join(again.world_lines(USER)))


READINGS = [
    {"entities": [{"name": "the user", "kind": "person", "as": "I"},
                  {"name": "Mila", "kind": "person", "as": "My wife Mila"},
                  {"name": "living room", "kind": "place", "as": "living room"}],
     "links": [{"from": "Mila", "relation": "spouse", "to": "the user", "quote": "My wife Mila"}],
     "topics": [{"topic": "new", "name": "choosing a TV", "text": "Wants a new TV for the living room."}]},
    {"entities": [{"name": "Sony TV", "kind": "TV", "as": "The Sony TV"},
                  {"name": "Mila", "kind": "person", "as": "Mila said"}],  # not in the entry: dropped
     "topics": [{"topic": 1, "name": "choosing a TV", "text": "Sony ruled out: too expensive."}]},
    {"entities": [{"name": "LG TV", "kind": "TV", "as": "The LG TV"}],
     "links": [{"from": "LG TV", "relation": "has glare in", "to": "living room", "quote": "glare"},
               {"from": "LG TV", "relation": "spouse", "to": "Nobody", "quote": "LG"}],  # no such entity
     "topics": [{"topic": 1, "name": "choosing a TV", "text": "Sony out, too dear; LG out, glare."}]},
    {"entities": [{"name": "Samsung S90D", "kind": "TV", "as": "the Samsung S90D"}],
     "topics": [{"topic": 1, "name": "choosing a TV", "text": "Sony out; LG out, glare; chose the Samsung S90D."}]},
    {"entities": [{"name": "LG TV", "kind": "TV", "as": "the LG TV"}],
     "topics": [{"topic": 1, "name": "choosing a TV",
                 "text": "Sony out; LG out, glare; chose the Samsung S90D (2026-10-26); then the LG after all, blinds (2026-11-28)."}]},
]


def offline() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        g = Graph(Path(tmp), journal(TV), reader=told(READINGS), decide=first)
        check("every entry is read", g.wait(10) and g.read_upto == 5, f"read_upto={g.read_upto}")

        check("a pause longer than an hour ends a dialogue", g.dialogue_of(2) == [1, 2, 3, 4] and g.dialogue_of(5) == [5],
              f"{g.dialogue_of(2)} {g.dialogue_of(5)}")
        check("'I' is the user, shared by every dialogue",
              any(m["entity"] == USER and m["dialogue"] == 0 for m in g.mentions))
        check("a mention must stand on the entry's words",
              not any(m["entity"] == "Mila" and m["text"] == 2 for m in g.mentions))

        relations = {(l["from"], l["relation"], l["to"], l["common"]) for l in g.links}
        check("a common relation is kept, named the common way", ("Mila", "spouse", USER, True) in relations, str(relations))
        check("any other relation is kept too: a skeleton, not a fence",
              ("LG TV", "has_glare_in", "living room", False) in relations, str(relations))
        check("a link to an entity the entry does not name is not kept",
              not any(l["to"] == "Nobody" for l in g.links))

        topics = g.latest_topics()
        check("one topic across two dialogues", len(topics) == 1 and topics[0]["entries"] == [1, 2, 3, 4, 5],
              str(topics))
        check("every version is kept", [t["version"] for t in g.topics] == [1, 2, 3, 4, 5])
        check("the latest version is layered", "after all" in topics[0]["text"] and "Sony" in topics[0]["text"])

        image = g.image("LG TV")
        check("an image is its texts, the newest first", [n for n, _, _ in image["entries"]] == [5, 3],
              str(image["entries"]))

        facts = g.facts_for([5], "which TV did we choose?")
        check("an answer gets the topic and the images the found entries name",
              'Topic "choosing a TV"' in facts and "LG TV" in facts and "facts 5 [2026-11-28], 3 [2026-10-26]" in facts, facts)

        g.goes_on = lambda message, t: 0.0
        known = g.recall("My wife wants a soundbar too", [])
        check("beside a message: a person it names as the user calls them, known from before",
              "Known from before:" in known and "- Mila (person): Mila is the spouse of the user" in known
              and "last on 2026-10-26" in known, known)
        check("by name too", "- LG TV (tv)" in g.recall("is the LG TV any good for games?", []))

        # Derived, never the truth: read again from the journal, the same comes back.
        g.reader = told(READINGS)
        g.rebuild()
        check("rebuilt from the journal", g.wait(10) and len(g.latest_topics()) == 1 and g.read_upto == 5)

        # Kept across a restart.
        again = Graph(Path(tmp), journal(TV), reader=told([]), decide=first)
        check("what was read is kept on disk", again.read_upto == 5 and len(again.topics) == 5 and again.links)


def at_scale() -> None:
    """However large the memory, the reader of one entry is shown a bounded few: the topic it goes on
    with among them, and the user's own people among the entities."""
    from memory import graph as module
    entries = [(1, "2026-01-01 10:00:00", "My sister Ana lives in Lisbon.")]
    entries += [(n, f"2026-01-{1 + n % 27:02d} 1{n % 10}:00:00", f"Note number {n} about hobby{n}.") for n in range(2, 302)]
    entries += [(302, "2026-06-01 10:00:00", "More on the bakery: the oven costs 4000 euros.")]
    readings = [{"entities": [{"name": "the user", "as": "My"}, {"name": "Ana", "kind": "person", "as": "sister Ana"}],
                 "links": [{"from": "Ana", "relation": "sibling", "to": "the user", "quote": "My sister Ana"}]}]
    readings += [{"topics": [{"topic": "new", "name": f"hobby{n}", "text": f"Talks about hobby{n}."}]} for n in range(2, 302)]
    shown = {}

    def reader(system, prompt):
        if "More on the bakery" in prompt:
            shown["prompt"] = prompt
            return {}
        return readings.pop(0) if readings else {}

    with tempfile.TemporaryDirectory() as tmp:
        g = Graph(Path(tmp), journal(entries[:-1]), reader=reader, decide=first)
        g.wait(30)
        g.topics.append({"topic": 999, "name": "starting the bakery", "text": "Plans a bakery in Lisbon.",
                         "day": "2026-05-01", "entries": [1], "version": 1})
        g._index([], [], g.topics[-1:])
        g.entries = journal(entries)
        g.wake()
        g.wait(30)
        prompt = shown.get("prompt", "")
        topics_part = prompt.split("The topics so far")[1].split("What the user said earlier")[0] if prompt else ""
        check("at scale: the reader is shown a bounded few topics",
              0 < topics_part.count(": Talks about") + topics_part.count(": Plans") <= module.SHOWN_TOPICS, topics_part[:200])
        check("at scale: the topic the entry goes on with is among them", "starting the bakery" in topics_part)
        check("at scale: the user's own people are shown to the reader", "- Ana — person" in prompt)


def live() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        g = Graph(Path(tmp), journal(TV))
        g.wait(600)
        topics = g.latest_topics()
        print("\n".join(f"  topic {t['topic']} v{t['version']} {t['name']}: {t['text']}" for t in topics))
        print("  links:", [(l["from"], l["relation"], l["to"]) for l in g.links])
        check("live: all read", g.read_upto == 5)
        check("live: Mila is the user's spouse",
              any(l["relation"] == "spouse" and {l["from"], l["to"]} == {"Mila", USER} for l in g.links))
        tv = [t for t in topics if 5 in t["entries"]]
        check("live: the TV topic holds the change and what was ruled out",
              bool(tv) and "LG" in tv[0]["text"] and "Sony" in tv[0]["text"], str(tv))


def live_world() -> None:
    entries = [(1, "2026-03-01 10:00:00", "My wife Mila's birthday is on 3 May."),
               (2, "2026-03-01 10:05:00", "Our son Lev is seven, and we have a beagle called Rex."),
               (3, "2026-03-02 10:00:00", "I work at Acme as a designer. I speak Serbian and some German."),
               (4, "2026-03-02 10:05:00", "We bought a Samsung TV last week."),
               (5, "2026-06-01 10:00:00", "In May I left Acme for a job at Globex, and we sold the Samsung and got an LG C4 instead.")]
    with tempfile.TemporaryDirectory() as tmp:
        g = Graph(Path(tmp), journal(entries))
        g.wait(600)
        world = "\n".join(g.world_lines(USER, gaps=True))
        print(world)
        print("\n".join(g.world_lines("Mila")))
        check("live world: wife, son, pet", all(w in world for w in ("spouse: Mila", "child: Lev", "pet: Rex")), world)
        check("live world: works at Globex now, Acme was", "works at: Globex" in world and "Acme" in world.split("works at:")[1].split("\n")[0], world)
        check("live world: owns the LG C4, the Samsung ended", "LG C4" in world.split("owns:")[1].split("was:")[0]
              and "Samsung" in world.split("owns:")[1].split("\n")[0].split("was:")[-1], world)
        check("live world: Mila's birthday", "born on: 3 May" in "\n".join(g.world_lines("Mila")))
    entries = [(1, "2026-03-01 10:00:00", "My wife loves jazz, I want to get her concert tickets."),
               (2, "2026-03-05 10:00:00", "My wife's birthday is on 3 May, and my sister is visiting then."),
               (3, "2026-03-20 10:00:00", "Mila, my wife, prefers small venues."),
               (4, "2026-03-21 10:00:00", "My sister Ana lives in Lisbon.")]
    with tempfile.TemporaryDirectory() as tmp:
        g = Graph(Path(tmp), journal(entries))
        g.wait(600)
        world = "\n".join(g.world_lines(USER, gaps=True))
        print(world)
        print("\n".join(g.world_lines("Mila") + g.world_lines("Ana")))
        check("live filling: the wife named later is one with 'my wife'", "spouse: Mila" in world and "user's wife" not in world, world)
        check("live filling: the sister named later is one with 'my sister'", "sibling: Ana" in world and "user's sister" not in world, world)
        check("live filling: what was said before the name is hers", "born on: 3 May" in "\n".join(g.world_lines("Mila")))


def main() -> int:
    offline()
    at_scale()
    said_of_self()
    personal_world()
    filled_from_messages()
    if "--live" in sys.argv:
        live()
        live_world()
    print(f"\n{len(failures)} failed" if failures else "\nall passed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
