"""A topic extended from the web for the user's questions on it (memory/refresh.py), with a fake
search and fake models; and the journal telling the web's entries from the user's."""
import sys
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from memory import journal  # noqa: E402
from memory import refresh  # noqa: E402
from memory.refresh import Refresher  # noqa: E402

TOPIC = {"topic": 3, "name": "Mila's birthday evening", "text": "a quiet evening with jazz on 11 November",
         "entries": [4, 7]}
FOUND = "- Jazz trio at Bluebird, 11 Nov 21:00 (https://bluebird.example)"
NOW = datetime(2026, 10, 30, 12, 0)


def make(questions, found=FOUND, matters=0.9, changes=0.8, said="2026-10-20 20:00", web=None, where=None):
    kept, told, searched, marks = [], [], [], []
    r = Refresher(keep_web=lambda text, topic, when=None: kept.append((text, topic)) or 42,
                  questions_of=lambda t: questions, extended=lambda *a: marks.append(a),
                  last_web=lambda topic: web, last_said=lambda entries: said, where=where,
                  search=lambda q, n: searched.append(q) or [{"url": "https://bluebird.example", "title": "Bluebird", "text": "jazz"}],
                  write=lambda prompt: '{"queries": ["jazz club Belgrade November 2026"]}' if "queries" in prompt else found,
                  volatile=lambda t, q: changes, worth=lambda t, q, f: matters, now=lambda: NOW)
    r.tell = told.append
    return r, kept, told, searched, marks


def test_a_stale_topic_is_looked_up_for_its_questions():
    asked = [{"id": 1, "asked": "any ideas for saturday?"}, {"id": 2, "asked": "need a place for dinner on friday"}]
    r, kept, told, searched, marks = make(asked)
    assert r.sweep([TOPIC]) == ["Mila's birthday evening"]
    assert len(searched) == 1  # the same query for both is searched once
    assert kept and kept[0][1] == 3 and "any ideas for saturday?" in kept[0][0]
    assert sorted(m[0] for m in marks) == [1, 2] and all(m[1] == 3 and m[3] == 42 for m in marks)
    assert "Found what matters" in told[0] and "#42" in told[0]


def test_a_topic_with_no_question_is_looked_up_from_itself():
    r, kept, _, searched, _ = make([])
    assert r.sweep([TOPIC]) == ["Mila's birthday evening"] and searched and kept


def test_nothing_that_matters_keeps_no_entry_but_the_topic_is_fresh_for_a_month():
    with tempfile.TemporaryDirectory() as d:
        r, kept, told, _, _ = make([{"id": 1, "asked": "any ideas for saturday?"}], matters=0.1, where=Path(d))
        r.sweep([TOPIC])
        assert not kept and "nothing new" in told[0]
        r2, *_ = make([], where=Path(d))  # after a restart, from what is kept beside the graph
        r2.now = lambda: NOW + timedelta(days=29)
        assert r2.fresh(TOPIC) and not r2.due(TOPIC)
        r2.now = lambda: NOW + timedelta(days=31)
        assert r2.due(TOPIC)


def test_a_web_entry_within_a_month_keeps_a_topic_fresh():
    r, *_ = make([], web="2026-10-10 09:00:00")
    assert not r.due(TOPIC)
    r.now = lambda: datetime(2026, 11, 10, 12, 0)
    assert r.due(TOPIC)


def test_a_dormant_topic_is_not_looked_up():
    r, _, _, searched, _ = make([], said="2026-07-01 20:00")
    assert r.sweep([TOPIC]) == [] and not searched


def test_the_users_own_matter_is_checked_not_searched():
    r, _, told, searched, _ = make([{"id": 1, "asked": "any ideas for saturday?"}], changes=0.1)
    assert r.sweep([TOPIC]) == [] and not searched and not told
    assert r.fresh(TOPIC)  # not asked again for a month


def test_sweeps_are_an_hour_apart_even_after_a_restart():
    with tempfile.TemporaryDirectory() as d:
        r, *_ = make([], where=Path(d))
        assert r.sweep([TOPIC])
        other = {**TOPIC, "topic": 4, "name": "concerts"}
        r2, _, _, searched, _ = make([], where=Path(d))
        r2.now = lambda: NOW + timedelta(minutes=30)
        assert r2.sweep([other]) == [] and not searched
        r2.now = lambda: NOW + timedelta(minutes=61)
        assert r2.sweep([other]) == ["concerts"]


def test_a_sweep_takes_at_most_its_cap():
    topics = [{**TOPIC, "topic": n, "name": f"t{n}"} for n in range(10)]
    r, *_ = make([])
    assert len(r.sweep(topics)) == refresh.TOPICS


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
        assert journal.last_web(3) and journal.last_web(4) is None
        assert journal.last_said([1, 2]) == journal.last_said([1]) and journal.last_said([2]) is None


if __name__ == "__main__":
    for name, f in list(globals().items()):
        if name.startswith("test_"):
            f()
            print("ok", name)
