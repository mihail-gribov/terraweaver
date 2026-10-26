"""Tests for the registry of task programs and for the lifetime of what a task gathers.

Run: .venv/bin/python tests/test_programs.py        # no model calls
"""
import json
import sys
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from proto.parse import _says_what  # noqa: E402
from proto.programs import Programs, description  # noqa: E402
from proto.tools import Item, Shelf, Tools  # noqa: E402

failures: list[str] = []


def check(name: str, condition: bool, detail: str = "") -> None:
    print(f"{'PASS' if condition else 'FAIL'}  {name}" + (f"  — {detail}" if detail and not condition else ""))
    if not condition:
        failures.append(name)


class Judge:
    """Chooses the option whose text holds a word of the task, else "new"."""

    def choice(self, state, question, options):
        task = state.lower()
        hit = next((n for n, t in options[1:] if any(w in task for w in t.lower().split() if len(w) > 5)), "new")
        return {"choice": hit}


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
    check("the judge's choice is the program found", programs.find("which product should I buy", Judge()) in (name, f"{name}_2"))
    check("the judge's none is no program", programs.find("when is the birthday", Judge()) is None)
    runs = (where / "programs" / "runs.jsonl").read_text().splitlines()
    check("every run is logged", len(runs) == 5 and json.loads(runs[1])["answered"] is False)


def lifetime(where: Path) -> None:
    mem = Shelf(where / "mem")
    user = mem.structure.entity("world", "the user", kind="person")
    eufy = mem.structure.entity("world", "Eufy 11S Max", kind="product")
    mem.structure.said("world", "The user bought the Eufy 11S Max last year.", [user, eufy])
    col = Shelf(where / "mem" / "collections" / "robot-vacuums", of="product")
    for name, price in [("Eufy 11S Max", 199), ("Roborock Q7", 249)]:
        col.structure.entity("world", name, kind="product").set("price_eur", price, f"{name} costs {price}", "https://a")
    fresh = col.structure.entity("world", "Xiaomi H40", kind="product")
    fresh.set("price_eur", 203, "Xiaomi H40 costs 203", "https://b")
    old = f"{datetime.now() - timedelta(days=8):%Y-%m-%d %H:%M:%S}"
    for r in col.structure.records:
        if not (r.get("thing") == fresh.id or fresh.id in (r.get("about") or ())):
            r["at"] = old
    col.structure.path.write_text("".join(json.dumps(r) + "\n" for r in col.structure.records))

    tools = Tools(mem, where / "run", log=lambda *_: None)
    tools.started = old
    items = {i.name: i for i in tools.new_collection("robot vacuums", of_class="product").all_items()}
    check("an item past its lifetime is removed", "Roborock Q7" not in items, str(sorted(items)))
    check("its text is removed with it", "Roborock" not in (where / "mem/collections/robot-vacuums/facts.md").read_text())
    check("an item spoken of with the user has no lifetime", "Eufy 11S Max" in items
          and items["Eufy 11S Max"].dates()["lives_until"] is None)
    check("a fresh item lives a week from when it was found", items.get("Xiaomi H40") is not None
          and items["Xiaomi H40"].dates()["lives_until"] > f"{datetime.now() + timedelta(days=6):%Y-%m-%d}")
    dates = Item(eufy, tools).dates()
    check("everything has its dates", dates["created"] and dates["changed"] and dates["lives_until"] is None)
    tools.started = f"{datetime.now() + timedelta(seconds=1):%Y-%m-%d %H:%M:%S}"
    check("a task chooses from what it found itself, not from earlier finds",
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


def main() -> int:
    quotes()
    with tempfile.TemporaryDirectory() as where:
        registry(Path(where))
        lifetime(Path(where))
    print(f"\n{len(failures)} failed" if failures else "\nall passed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
