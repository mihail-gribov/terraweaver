"""Tests for the two upper levels of change: what the world adds to its classes, and the
methods it writes for itself.

Run: .venv/bin/python tests/test_growth.py
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from terraweaver import growth
from terraweaver.ontology import load_specs
from terraweaver.runtime import WorldRuntime

ONTOLOGY_DIR = Path(__file__).resolve().parent.parent / "ontology" / "core"
failures: list[str] = []


def check(name: str, condition: bool, detail: str = "") -> None:
    print(f"{'PASS' if condition else 'FAIL'}  {name}" + (f"  — {detail}" if detail and not condition else ""))
    if not condition:
        failures.append(name)


def refused(action) -> str | None:
    try:
        action()
    except Exception as exc:  # noqa: BLE001 - any refusal counts; the point is that it didn't go through
        return str(exc)
    return None


def main() -> int:
    core = load_specs(ONTOLOGY_DIR, grown_dir=Path("/nonexistent"))

    # --- the world adds to a class, and the core file stays what it was ---
    addition = {"name": "PersonWithDiet", "extends": "Person", "added_at": "2026-09-20",
                "because": "seven people had a dietary note in a remark",
                "attributes": [{"name": "dietary_notes", "type": "str", "description": "What they don't eat."}]}
    grown = growth.apply_growth(core, [addition])
    names = [a["name"] for a in grown["Person"]["attributes"]]
    check("a grown attribute joins the class", "dietary_notes" in names, str(names[-3:]))
    check("and the core spec is untouched",
          "dietary_notes" not in [a["name"] for a in core["Person"]["attributes"]])
    check("the world can say what it added to itself",
          "dietary_notes" in growth.describe_growth(grown) and "seven people" in growth.describe_growth(grown),
          growth.describe_growth(grown))

    # --- growth adds; it never rewrites ---
    clash = dict(addition, name="PersonEmail",
                 attributes=[{"name": "email", "type": "str", "description": "another email"}])
    check("redefining a core attribute is refused",
          "can't be redefined" in (refused(lambda: growth.apply_growth(core, [clash])) or ""),
          str(refused(lambda: growth.apply_growth(core, [clash]))))
    check("extending something that isn't a core class is refused",
          refused(lambda: growth.apply_growth(core, [dict(addition, extends="Wizard")])) is not None)
    check("a change nobody can explain is refused",
          "review" in (refused(lambda: growth.apply_growth(core, [dict(addition, because="  ")])) or ""))
    check("a grown file can't smuggle in anything else",
          refused(lambda: growth.apply_growth(core, [dict(addition, impls="rm -rf")])) is not None)

    # --- a procedure the world wrote for itself ---
    rt = WorldRuntime(":memory:", fixture="job_search")
    rt.world.procedures.define(
        "colleagues", "colleagues(self)",
        "org = self.organization\n"
        "return [p for p in Person.find(organization=org).matches if p != self] if org else []",
        because="asked three times this week: who else works where this person works",
        attaches_to="Person")
    rt.world.procedures.bind(rt.classes)
    called = rt.run('ada = Person.get(full_name="Ada Lovelace")\nprint(ada.colleagues())', "host")
    check("host code calls it like any method", called["ok"], str(called["error"]))
    check("and the call is counted", rt.world.procedures.get("colleagues").uses == 1,
          str(rt.world.procedures.get("colleagues")))
    check("it says why it exists",
          "three times this week" in rt.run('print(Person.colleagues.__doc__)', "host")["output"])

    # --- a procedure that can't run is never stored ---
    check("code the sandbox refuses is refused here",
          refused(lambda: rt.world.procedures.define("bad", "bad(self)", "import os\nreturn os",
                                                     because="x", attaches_to="Person")) is not None)
    check("and it wasn't kept", rt.world.procedures.get("bad") is None)
    check("a procedure with no reason to exist is refused",
          refused(lambda: rt.world.procedures.define("nope", "nope(self)", "return 1",
                                                     because="", attaches_to="Person")) is not None)

    # --- unused procedures are named so they can be dropped ---
    rt.world.procedures.define("unused", "unused(self)", "return 1",
                               because="tried once, never needed again", attaches_to="Person")
    check("a procedure just added isn't forgotten yet", rt.world.procedures.forgotten() == [])
    check("an old unused one is named",
          [p.name for p in rt.world.procedures.forgotten(older_than_days=-1)] == ["unused"],
          str(rt.world.procedures.forgotten(older_than_days=-1)))
    rt.world.procedures.drop("unused")
    check("and dropping it leaves nothing behind", rt.world.procedures.get("unused") is None)

    # --- a world starts without the word for everything in it, and catches up losing nothing ---
    from terraweaver import authoring

    rt.run('ball = Thing.ensure(name="pesäpallo")\n'
           'ball.describe("created in Finland")\nball.tag("sport")', "host")
    was = rt.classes["Thing"].get(name="pesäpallo")
    authoring.Authoring(rt.world).define("Sport", "A game people play and follow.",
                                         identified_by="name")
    rt.classes["Sport"] = rt.world.classes["Sport"]
    became = rt.run('now = Thing.get(name="pesäpallo").become("Sport")\n'
                    'print(type(now).__name__, now.name, now.descriptions, now.tags)', "host")
    check("a Thing becomes the class the world learned", became["ok"], str(became["error"]))
    check("and reads as one, with everything said about it",
          became["output"].strip() == "Sport pesäpallo ['created in Finland'] ['sport']",
          became["output"])
    check("the same entity, not a copy", rt.classes["Sport"].get(name="pesäpallo").id == was.id)
    check("and Thing no longer holds it", rt.classes["Thing"].all(limit=None) == [])
    said = [(s.slot, s.value) for s in rt.world.facts.about(was.subject_id)]
    check("becoming is a statement like any other", ("is_a", "Sport") in said, str(said))
    check("and nothing had to move to make it true",
          any(slot == "descriptions" for slot, _ in said), str(said))

    # --- the whole of it: a world with only the base, and a host that ends with a vocabulary ---
    from pathlib import Path as _Path
    from terraweaver import ontology as _ont

    import tempfile as _tempfile

    room = _Path(_tempfile.mkdtemp(prefix="tw-base-"))
    base = WorldRuntime(str(room / "base.db"), fixture=None, selves=False,
                        specs=_ont.base_specs(ONTOLOGY_DIR))
    authoring.install(base.world, room / "grown")
    wrote = base.run('for who, what in [("Ferdowsi", "Shahnameh"), ("Le Guin", "Earthsea"),\n'
                     '                  ("Watsuki", "Kenshin")]:\n'
                     '    Thing.ensure(name=who).relate(Thing.ensure(name=what), "related",\n'
                     '                                  label="author of")', "host")
    check("a base world takes a link it has no type for", wrote["ok"], str(wrote["error"]))
    check("and says so once the word is a habit",
          any("has been written 3 times" in h for h in wrote.get("hints", [])),
          str(wrote.get("hints")))
    asked = base.world.wanted()
    check("naming the shape it keeps needing",
          [(s["asked"], s["from"], s["to"], s["seen"]) for s in asked]
          == [("author of", "Thing", "Thing", 3)], str(asked))
    closed = base.run('made = world.define_relation("authorship", "who wrote what",\n'
                      '                             nature="related_to",\n'
                      '                             subject=Thing, object=Thing,\n'
                      '                             cardinality="one-to-many", over_time=False)\n'
                      'print(len(world.take_in(made)), len(Related.all(limit=None)))', "host")
    check("and the links already written join the type it defines",
          closed["output"].strip() == "3 0", closed["output"] + str(closed["error"]))
    check("after which the world asks for nothing", base.world.wanted() == [],
          str(base.world.wanted()))

    # --- a free link taken into a type keeps its ends ---
    # `retype` carries the attributes both specs declare, and a link's ends are declared by
    # neither — the relation machinery puts them there. So a link taken in arrived with a
    # label, a description and nothing joined. The record held both ends throughout, so the
    # fact was never lost; it was unreadable, and reading one raised and took every other link
    # of that type down with it.
    from terraweaver import authoring

    rt = WorldRuntime(":memory:", fixture="job_search")
    made = authoring.install(rt.world, None)
    rt.start_task("k", "record where a city is the seat of government", "recording")
    rt.run('berlin = Thing.ensure(name="Berlin", nature="place")\n'
           'germany = Thing.ensure(name="Germany", nature="place")\n'
           'link = berlin.relate(germany, "related", label="capital of")\n'
           'link.describe("Berlin is the capital of Germany")\n'
           'print("free link made")', "k")
    made.define_relation("capital_of", "the city that is a country's seat of government",
                         nature="part_of", cardinality="one-to-one", over_time=False)
    rt._bind_classes(rt.session("k"))
    got = rt.run('world.take_in("capital_of", "capital of")\n'
                 'for link in world.all("CapitalOf", limit=None):\n'
                 '    print(link.subject.name, "->", link.object.name)', "k")
    check("a link taken into a type keeps both its ends",
          got["ok"] and "Berlin -> Germany" in (got["output"] or ""),
          str(got.get("error") or got.get("output"))[:140])

    # --- one unreadable link does not take the rest of its type with it ---
    # Two endless rows from an older `retype` bug raised eighteen times in one recording
    # session: the host could read nothing about capitals, stopped writing them, and
    # twenty-two facts were lost to two bad rows. A reading that cannot be made leaves that
    # one thing out.
    rt = WorldRuntime(":memory:", fixture="job_search")
    made = authoring.install(rt.world, None)
    made.define_relation("capital_of", "the city that is a country's seat of government",
                         nature="part_of", cardinality="one-to-one", over_time=False)
    rt._bind_classes(rt.session("k2"))
    rt.start_task("k2", "record which cities are seats of government", "recording")
    rt.run('for city, land in (("Berlin", "Germany"), ("Tokyo", "Japan")):\n'
           '    a = Thing.ensure(name=city, nature="place")\n'
           '    b = Thing.ensure(name=land, nature="place")\n'
           '    a.relate(b, "capital_of")\n'
           'print("two links")', "k2")
    # Break one of them the way retype used to: take its ends out of the image, not the record.
    links = rt.world.all(rt.world.classes["CapitalOf"], limit=None)
    tokyo_link = next(l for l in links if l.subject.name == "Tokyo")
    rt.store.conn.execute("DELETE FROM 'CapitalOf' WHERE instance_id = ? AND attr IN "
                          "('subject', 'object')", (tokyo_link.id,))
    rt.store.conn.commit()
    rt.store._identity.clear()
    got = rt.run('print([t.name for t in Thing.get(name="Germany").related("capital_of_of")])', "k2")
    check("one unreadable link does not take the rest of its type with it",
          got["ok"] and "Berlin" in (got["output"] or ""),
          str(got.get("error") or got.get("output"))[:160])

    # --- what the refusal tells you to do has to work in the same breath ---
    # The world refuses an attribute the class has not got, and now says to declare it. Growing
    # a class used to build a new class object, leaving the instance in hand and the name in the
    # run's namespace on the old spec — so a host that did exactly what it was told got the same
    # refusal again, with no way past it from inside the run. That is where prose comes from.
    rt = WorldRuntime(":memory:", fixture="job_search")
    authoring.install(rt.world, None)
    rt.start_task("k3", "record what the user said about somebody's pay", "recording")
    turned_away = rt.run('p = Person.new(full_name="Ada Byron")\np.salary = 120000', "k3")
    check("an attribute the class has not got is refused",
          not turned_away["ok"] and "has no attribute 'salary'" in str(turned_away.get("error")),
          str(turned_away.get("error"))[:90])
    check("and the refusal says to declare it, not to write prose",
          "world.attribute(" in str(turned_away.get("error")),
          str(turned_away.get("error"))[:140])
    done = rt.run('world.attribute(Person, "salary", "what they are paid a year", type="int")\n'
                  'p = Person.get(full_name="Ada Byron")\np.salary = 120000\nprint(p.salary)', "k3")
    check("and doing what it says works in the same run",
          done["ok"] and "120000" in (done["output"] or ""),
          str(done.get("error") or done.get("output"))[:140])

    print()
    if failures:
        print(f"{len(failures)} failed: {', '.join(failures)}")
        return 1
    print("all growth tests passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())

