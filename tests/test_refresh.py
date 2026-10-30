"""A topic extended from the web for the user's questions on it (memory/refresh.py), with a fake
search and fake models; and the journal telling the web's entries from the user's."""
import sys
import tempfile
import time
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from memory import journal  # noqa: E402
from memory.refresh import Refresher  # noqa: E402

TOPIC = {"topic": 3, "name": "Mila's birthday evening", "text": "a quiet evening with jazz on 11 November",
         "entries": [4, 7]}
FOUND = "- Jazz trio at Bluebird, 11 Nov 21:00 (https://bluebird.example)"


def wait(r):
    for _ in range(100):
        if not r.running:
            return
        time.sleep(0.02)


def make(questions, found=FOUND, matters=0.9, changes=0.8):
    kept, told, searched, marks = [], [], [], []
    r = Refresher(keep_web=lambda text, topic: kept.append((text, topic)) or 42,
                  questions_of=lambda t: questions, extended=lambda *a: marks.append(a),
                  search=lambda q, n: searched.append(q) or [{"url": "https://bluebird.example", "title": "Bluebird", "text": "jazz"}],
                  write=lambda prompt: '{"queries": ["jazz club Belgrade November 2026"]}' if "queries" in prompt else found,
                  volatile=lambda t, m: changes, worth=lambda t, q, f: matters)
    r.tell = told.append
    return r, kept, told, searched, marks


def test_each_question_is_extended_and_marked():
    asked = [{"id": 1, "asked": "any ideas for saturday?", "extended": None},
             {"id": 2, "asked": "need a place for dinner on friday", "extended": None}]
    r, kept, told, searched, marks = make(asked)
    assert r.touched([TOPIC], "plan her birthday evening") == ["Mila's birthday evening"]
    wait(r)
    assert len(searched) == 1  # the same query for both is searched once
    assert kept and kept[0][1] == 3 and "any ideas for saturday?" in kept[0][0]
    assert sorted(m[0] for m in marks) == [1, 2] and all(m[1] == 3 and m[3] == 42 for m in marks)
    assert "Found what matters" in told[0] and "#42" in told[0]


def test_nothing_that_matters_is_marked_and_said_not_kept():
    r, kept, told, _, marks = make([{"id": 1, "asked": "any ideas for saturday?", "extended": None}], matters=0.1)
    r.touched([TOPIC]); wait(r)
    assert not kept and "nothing new" in told[0] and marks[0][3] is None


def test_no_question_no_search():
    r, kept, told, searched, _ = make([])
    assert r.touched([TOPIC]) == [] and not searched and not told


def test_the_users_own_matter_is_not_searched():
    r, _, told, searched, _ = make([{"id": 1, "asked": "any ideas for saturday?", "extended": None}], changes=0.1)
    assert r.touched([TOPIC]) == [] and not searched and not told


def test_a_question_extended_lately_is_not_due_until_stale():
    lately = (datetime.now() - timedelta(days=2)).isoformat(timespec="seconds")
    r, *_ = make([{"id": 1, "asked": "any ideas for saturday?", "extended": lately}])
    assert r.due(TOPIC) == []
    r.now = lambda: datetime.now() + timedelta(days=6)
    assert [q["id"] for q in r.due(TOPIC)] == [1]


def test_the_journal_tells_the_web_from_the_user():
    with tempfile.TemporaryDirectory() as d:
        journal.facts = Path(d) / "facts.md"
        journal._keep("Mila hates crowds", journal.USER)
        journal.keep_web("- Jazz trio at Bluebird (https://bluebird.example)", 3)
        (u, hu, _), (w, hw, _) = journal._entries(journal._memory())
        assert journal.source_of(hu) == journal.USER and journal.topic_of(hu) is None
        assert journal.source_of(hw) == journal.WEB and journal.topic_of(hw) == 3
        shown = journal._for_the_model(journal._memory()).splitlines()
        assert shown[0] == "1. Mila hates crowds" and shown[1].startswith("2. (from the web) ")


if __name__ == "__main__":
    for name, f in list(globals().items()):
        if name.startswith("test_"):
            f()
            print("ok", name)
