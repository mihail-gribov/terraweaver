"""Tests for the graph: texts, the entities they mention, links, topics (memory/graph.py).

Run: .venv/bin/python tests/test_graph.py           # no model calls: a reader that answers as told
     .venv/bin/python tests/test_graph.py --live    # the TV story through Nemotron Super
"""
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
        g = Graph(Path(tmp), journal(TV), reader=told(READINGS))
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

        # Derived, never the truth: read again from the journal, the same comes back.
        g.reader = told(READINGS)
        g.rebuild()
        check("rebuilt from the journal", g.wait(10) and len(g.latest_topics()) == 1 and g.read_upto == 5)

        # Kept across a restart.
        again = Graph(Path(tmp), journal(TV), reader=told([]))
        check("what was read is kept on disk", again.read_upto == 5 and len(again.topics) == 5 and again.links)


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


def main() -> int:
    offline()
    if "--live" in sys.argv:
        live()
    print(f"\n{len(failures)} failed" if failures else "\nall passed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
