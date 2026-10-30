"""Topics kept fresh from the web (memory/refresh.py), with a fake search and fake models."""
import sys
import tempfile
import time
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from memory.refresh import Refresher  # noqa: E402

TOPIC = {"topic": 3, "name": "Mila's birthday evening", "text": "a quiet evening with jazz on 11 November"}


def wait(r):
    for _ in range(100):
        if not r.running:
            return
        time.sleep(0.02)


def make(where, found="- Jazz trio at Bluebird, 11 Nov 21:00 (https://bluebird.example)", matters=0.9, changes=0.8):
    kept, told, searched = [], [], []
    r = Refresher(where, search=lambda q, n: searched.append(q) or [{"url": "https://bluebird.example", "title": "Bluebird", "text": "jazz"}],
                  write=lambda prompt: '{"queries": ["jazz club Belgrade November 2026"]}' if "queries" in prompt else found,
                  volatile=lambda t, m: changes, worth=lambda t, f: matters, keep=lambda *a: kept.append(a))
    r.tell = told.append
    return r, kept, told, searched


def test_found_is_kept_and_told():
    with tempfile.TemporaryDirectory() as d:
        r, kept, told, searched = make(Path(d))
        assert r.touched([TOPIC]) == ["Mila's birthday evening"]
        wait(r)
        assert searched == ["jazz club Belgrade November 2026"]
        assert kept and kept[0][0] == 3 and kept[0][1].startswith("From the web, ")
        assert len(told) == 1 and "Found what matters" in told[0]
        # Searched a moment ago: not again.
        assert r.touched([TOPIC]) == []


def test_nothing_that_matters_is_said_not_kept():
    with tempfile.TemporaryDirectory() as d:
        r, kept, told, _ = make(Path(d), matters=0.1)
        r.touched([TOPIC]); wait(r)
        assert not kept and "nothing new" in told[0]


def test_a_topic_that_holds_is_not_searched():
    with tempfile.TemporaryDirectory() as d:
        r, kept, told, searched = make(Path(d), changes=0.1)
        assert r.touched([TOPIC]) == [] and not searched and not told


def test_stale_is_searched_again():
    with tempfile.TemporaryDirectory() as d:
        r, _, told, searched = make(Path(d))
        r.touched([TOPIC]); wait(r)
        r.now = lambda: datetime.now() + timedelta(days=8)
        assert r.touched([TOPIC]) == ["Mila's birthday evening"]
        wait(r)
        assert len(searched) == 2


if __name__ == "__main__":
    for name, f in list(globals().items()):
        if name.startswith("test_"):
            f()
            print("ok", name)
