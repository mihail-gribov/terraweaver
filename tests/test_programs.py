"""Tests for the registry of task programs and for the lifetime of what a task gathers.

Run: .venv/bin/python tests/test_programs.py        # no model calls
"""
import json
import sys
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from proto.cleaner import clean  # noqa: E402
from proto.parse import _says_what  # noqa: E402
from proto.programs import Programs, description  # noqa: E402
from proto.tools import Item, Shelf, Tools  # noqa: E402

failures: list[str] = []


def check(name: str, condition: bool, detail: str = "") -> None:
    print(f"{'PASS' if condition else 'FAIL'}  {name}" + (f"  — {detail}" if detail and not condition else ""))
    if not condition:
        failures.append(name)


class Judge:
    """Says "same kind" when the new task shares a long word with the program's text."""

    def noul(self, state, question, true, false):
        known, _, task = state.lower().partition("a new task:")
        same = any(w in known for w in task.split() if len(w.strip('"?')) > 5)
        return {"p": {"yes": 0.9 if same else 0.1, "no": 0.1 if same else 0.9}}


def registry(where: Path) -> None:
    programs = Programs(where / "programs")
    pick = '"""Pick one product for the user from the web.\n\nRanks by limits."""\nreply_to_agent(1)\n'
    check("a program's docstring is its description", description(pick).startswith("Pick one product"))
    check("no registry: nothing is found", programs.find("pick a vacuum", Judge()) is None)
    name = programs.keep(pick, "pick me a vacuum", answered=True)
    check("an answered program is kept under a name from its description", name == "pick_one_product_for_the_user")
    check("a program without an answer is not kept", programs.keep(pick, "t", answered=False) is None)
    check("a program without a docstring is not kept", programs.keep("reply_to_agent(1)", "t", answered=True) is None)
    check("the same description gets a second name", programs.keep(pick, "t", True) == f"{name}_2")
    check("a program based on a kept one replaces it", programs.keep(pick + "# v2\n", "t", True, based_on=name) == name
          and "# v2" in programs.text(name))
    check("the judge's choice is the program found", programs.find("which product should I purchase", Judge()) in (name, f"{name}_2"))
    check("the judge's none is no program", programs.find("when is the birthday", Judge()) is None)
    runs = (where / "programs" / "runs.jsonl").read_text().splitlines()
    check("every run is logged", len(runs) == 5 and json.loads(runs[1])["answered"] is False)
    programs.keep(pick, "pick a kettle", answered=False, based_on=name, attempts=3, seconds=40)
    programs.keep(pick, "pick a lamp", answered=True, based_on=name, attempts=1, seconds=20)
    st = programs.stats()[name]
    check("a failed run of a kept program counts as a use", st["uses"] == 4 and st["reuses"] == 3, str(st))
    check("statistics: answered, versions, first attempts", st["answered"] == 3 and st["versions"] == 3
          and st["first_attempt"] == 3, str(st))
    check("statistics: when made and last used, the last tasks", st["created"] <= st["last_used"]
          and st["tasks"][-1] == "pick a lamp")


def lifetime(where: Path) -> None:
    mem = Shelf(where / "mem")
    user = mem.structure.entity("world", "the user", kind="person")
    eufy = mem.structure.entity("world", "Eufy 11S Max", kind="product")
    mem.structure.said("world", "The user bought the Eufy 11S Max last year.", [user, eufy])
    col = Shelf(where / "mem" / "collections" / "robot-vacuums", of="product")
    made = {}
    for name, price in [("Eufy 11S Max", 199), ("Roborock Q7", 249), ("Dreame D10", 179), ("Roborock Q5", 159)]:
        made[name] = col.structure.entity("world", name, kind="product")
        made[name].set("price_eur", price, f"{name} costs {price}", "https://a")
    fresh = col.structure.entity("world", "Xiaomi H40", kind="product")
    fresh.set("price_eur", 203, "Xiaomi H40 costs 203", "https://b")
    old = f"{datetime.now() - timedelta(days=100):%Y-%m-%d %H:%M:%S}"
    for r in col.structure.records:
        if not (r.get("thing") == fresh.id or fresh.id in (r.get("about") or ())):
            r["at"] = old
    col.structure.path.write_text("".join(json.dumps(r) + "\n" for r in col.structure.records))
    (col.path / "used.json").write_text(json.dumps({
        made["Dreame D10"].id: {"used": f"{datetime.now() - timedelta(days=10):%Y-%m-%d %H:%M:%S}"},
        made["Roborock Q5"].id: {"used": old, "lasting": "named in an answer, 2026-07-01"}}))

    removed = clean(mem, Programs(where / "programs"), log=lambda *_: None)
    check("the cleaner removes what was not used for its TTL", removed["items"] == {"robot-vacuums": ["Roborock Q7"]},
          str(removed))
    tools = Tools(mem, where / "run", log=lambda *_: None)
    tools.started = old
    items = {i.name: i for i in tools.new_collection("robot vacuums", of_class="product").all_items()}
    check("its text is removed with it", "Roborock Q7" not in (where / "mem/collections/robot-vacuums/facts.md").read_text())
    check("found long ago but read by a task lately: kept", "Dreame D10" in items)
    check("once named in an answer: no TTL", "Roborock Q5" in items and items["Roborock Q5"].dates()["lives_until"] is None)
    check("named in the user's memory: no TTL", items["Eufy 11S Max"].dates()["lives_until"] is None)
    check("the TTL counts from the last use: three months on", items["Xiaomi H40"].dates()["lives_until"]
          > f"{datetime.now() + timedelta(days=89):%Y-%m-%d}")
    tools.reply_to_agent("Choice: Xiaomi H40, at 203 euros.")
    check("what the answer names has been with the user: no TTL", items["Xiaomi H40"].dates()["lives_until"] is None
          and items["Dreame D10"].dates()["lives_until"] is not None)
    dates = Item(eufy, tools).dates()
    check("everything has its dates", dates["created"] and dates["changed"] and dates["lives_until"] is None)
    tools.started = f"{datetime.now() + timedelta(seconds=1):%Y-%m-%d %H:%M:%S}"
    check("a task chooses from what was found lately, not from earlier finds",
          not tools.new_collection("robot vacuums").all_items())
    refound = tools.new_collection("robot vacuums")._shelf
    refound.structure.since = f"{datetime.now():%Y-%m-%d %H:%M:%S}"
    x = next(t for t in refound.things() if t.name == "Xiaomi H40")
    for r in refound.structure.records:
        r["at"] = min(r["at"], f"{datetime.now() - timedelta(hours=1):%Y-%m-%d %H:%M:%S}")
    x.set("price_eur", 260, "Xiaomi H40 costs 260", "https://c")
    check("an item found again reads only this task's values", x.get("price_eur") == 260, str(x.get("price_eur")))
    again = col.structure.entity("world", "Dreame D10")
    check("a new thing after a removal gets an id of its own", again.id not in {r.get("thing") for r in col.structure.records[:-1]})


def quotes() -> None:
    check("a bare length doesn't say what it measures", not _says_what("10.2 cm", "threshold_cm"))
    check("a length with its words does", _says_what("überwindet Schwellen bis 2 cm", "threshold_cm"))
    check("a bare sum of money is a price", _says_what("249 €", "price_eur"))
    check("but not anything else", not _says_what("249 €", "threshold_cm"))


def programs_age(where: Path) -> None:
    programs = Programs(where / "aging")
    old = programs.keep('"""Plan a trip for the user."""\nreply_to_agent(1)\n', "plan a trip", True)
    new = programs.keep('"""Say who the colleagues of the user are."""\nreply_to_agent(2)\n', "colleagues", True)
    runs = programs.runs()
    runs[0]["at"] = (datetime.now() - timedelta(days=100)).isoformat(timespec="seconds")
    (where / "aging" / "runs.jsonl").write_text("".join(json.dumps(r) + "\n" for r in runs))
    check("a program used within its lifetime is kept until three months after", programs.stats()[new]["lives_until"]
          > (datetime.now() + timedelta(days=89)).isoformat())
    removed = clean(Shelf(where / "empty"), programs, log=lambda *_: None)  # TTL: 90 days
    check("a program not used for three months is removed", removed["programs"] == [old]
          and not (where / "aging" / f"{old}.py").exists() and new in programs.all(), str(removed))
    check("its removal is logged", any(r.get("removed") == old for r in programs.runs()))
    check("statistics ignore the removal records", set(programs.stats()) == {new})


def limits_and_closest(where: Path) -> None:
    from proto.solve import LIMIT_WORDS
    check("a stated limit has a limit's words", all(LIMIT_WORDS.search(q) for q in (
        "has to stay under 400 euros", "between 200 and 500", "does not want another device that works only through a cloud")))
    check("a preference or a habit is no limit", not any(LIMIT_WORDS.search(q) for q in (
        "prefers evenings out on Friday or Saturday", "Sunday evenings go to preparing for work", "don't like loud clubs")))
    tools = Tools(Shelf(where / "closest-mem"), where / "run", log=lambda *_: None)
    c = tools.new_collection("concerts", of_class="event")
    for name, date in [("Candlelight: Vivaldi", "2026-12-10"), ("Candlelight: Queen", "2026-11-22")]:
        c._shelf.structure.entity("world", name, kind="event").set("date", date, f"{name} is on {date}", "https://a")
    ranking = c.all_items().rank_by({"on_saturday": lambda i: i.value_of("date") == "2026-10-31",
                                     "candlelight": lambda i: "Candlelight" in i.name}, must_hold=["on_saturday"])
    check("the same thing is the same item, however reached",
          c.all_items()[0] == c.all_items()[0] and len({*c.all_items(), *c.all_items()}) == 2)
    check("nothing passed: the closest come with the ranking", not ranking and len(ranking.closest) == 2)
    tools.reply_to_agent("No concert fits.")
    check("and go into the reply, whatever the program wrote", "Candlelight: Vivaldi" in tools.answered
          and "closest" in tools.answered, tools.answered)
    from datetime import date
    vivaldi = next(i for i in c.all_items() if "Vivaldi" in i.name)
    check("a date is read by code, weekday and all", vivaldi.date_of("date") == date(2026, 12, 10)
          and vivaldi.date_of("place") is None)
    weekend = c.all_items().rank_by({"weekend": lambda i: i.date_of("date").weekday() >= 5,
                                     "evening": lambda i: i.date_of("starts_at").hour >= 18})
    check("a date not known is not known, not no", all(r.conditions["evening"] is None for r in weekend)
          and {r.item.name: r.conditions["weekend"] for r in weekend} == {"Candlelight: Queen": True,
                                                                         "Candlelight: Vivaldi": False})
    check("a report gives a date's weekday", "(Sunday)" in next(r for r in weekend if "Queen" in r.item.name).report())


def search_reaches_read_things(where: Path) -> None:
    from proto.search import Search
    mem = Shelf(where / "search-mem")
    anna = mem.structure.entity("world", "Anna", "Anna is the user's sister.", kind="person")
    image = {"things": {anna.id: {"name": "Anna", "class": "Person"}, "r:the-user": {"name": "the user", "class": "Person",
                                                                                    "user": True}},
             "links": [{"type": "ManagerOf", "subject": "r:the-user", "object": anna.id, "entry": 1}], "values": {}}
    search = Search(mem.structure, lambda: mem.journal.entries, where / "vectors.jsonl", image=lambda: image)
    try:
        about, by = search.about_named("Who manages Anna?"), search.by_structure("Is my manager Anna?")
        check("a thing only the world read doesn't break the search", 1 in about and 1 in by, f"{about} {by}")
    except ValueError as wrong:
        check("a thing only the world read doesn't break the search", False, repr(wrong))


def main() -> int:
    quotes()
    with tempfile.TemporaryDirectory() as where:
        registry(Path(where))
        lifetime(Path(where))
        programs_age(Path(where))
        limits_and_closest(Path(where))
        search_reaches_read_things(Path(where))
    print(f"\n{len(failures)} failed" if failures else "\nall passed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
