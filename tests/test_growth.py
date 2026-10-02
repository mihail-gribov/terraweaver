"""Tests for the two upper levels of change: what the world adds to its classes, and the
methods it writes for itself.

Run: .venv/bin/python tests/test_growth.py
"""
import json
import tempfile
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from terraweaver import open_world  # noqa: E402

from terraweaver import growth
from terraweaver.ontology import base_specs as ont_base, load_specs
from terraweaver.runtime import WorldRuntime

ONTOLOGY_DIR = Path(__file__).resolve().parent.parent / "ontology" / "core"
ROOT = Path(__file__).resolve().parent.parent
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
                 attributes=[{"name": "name", "type": "str", "description": "another name"}])
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
    rt = open_world()
    rt.run('Person.new(name="Ada Lovelace")\nPerson.new(name="Ada King")', "host")
    rt.world.procedures.define(
        "namesakes", "namesakes(self)",
        "first = self.name.split()[0]\n"
        "return [p for p in Person.find(name=first).matches if p != self]",
        because="asked three times this week: who else here goes by the same first name",
        attaches_to="Person")
    rt.world.procedures.bind(rt.classes)
    called = rt.run('ada = Person.get(name="Ada Lovelace")\nprint(ada.namesakes())', "host")
    check("host code calls it like any method", called["ok"], str(called["error"]))
    check("and the call is counted", rt.world.procedures.get("namesakes").uses == 1,
          str(rt.world.procedures.get("namesakes")))
    check("it says why it exists",
          "three times this week" in rt.run('print(Person.namesakes.__doc__)', "host")["output"])

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
    check("and Thing no longer holds it as a Thing itself",
          rt.classes["Thing"].all(limit=None, kinds=False) == [])
    said = [(s.slot, s.value) for s in rt.world.facts.about(was.subject_id)]
    check("becoming is a statement like any other", ("is_a", "Sport") in said, str(said))
    check("and nothing had to move to make it true",
          any(slot == "descriptions" for slot, _ in said), str(said))

    # --- the whole of it: a world with only the base, and a host that ends with a vocabulary ---
    from pathlib import Path as _Path
    from terraweaver import ontology as _ont

    import tempfile as _tempfile

    room = _Path(_tempfile.mkdtemp(prefix="tw-base-"))
    base = WorldRuntime(str(room / "base.db"), selves=False,
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
    # What the labels are ranked against is a model, and this check used to need a real one: it
    # passed while Ollama could load bge-m3 and failed the moment somebody else's run filled the
    # card — a unit test quietly depending on a GPU. The ranking is what is under test, so the
    # similarity is stood in for here and the answer is the world's own logic.
    class _Close:
        """"author of" is the same idea as the type; anything else is not."""

        def embed(self, texts):
            return [[1.0] if "author" in text or "authorship" in text else [0.0]
                    for text in texts]

    base.world.meanings.model = _Close()
    closed = base.run('made = world.define_relation("authorship", "who wrote what",\n'
                      '                             nature="related_to",\n'
                      '                             subject=Thing, object=Thing,\n'
                      '                             cardinality="one-to-many")\n'
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

    rt = open_world()
    made = authoring.install(rt.world, None)
    rt.start_task("k", "record where a city is the seat of government", "recording")
    rt.run('berlin = Thing.ensure(name="Berlin", nature="place")\n'
           'germany = Thing.ensure(name="Germany", nature="place")\n'
           'link = berlin.relate(germany, "related", label="capital of")\n'
           'link.describe("Berlin is the capital of Germany")\n'
           'print("free link made")', "k")
    made.define_relation("capital_of", "the city that is a country's seat of government",
                         nature="part_of", cardinality="one-to-one")
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
    rt = open_world()
    made = authoring.install(rt.world, None)
    made.define_relation("capital_of", "the city that is a country's seat of government",
                         nature="part_of", cardinality="one-to-one")
    rt._bind_classes(rt.session("k2"))
    rt.start_task("k2", "record which cities are seats of government", "recording")
    rt.run('for city, land in (("Berlin", "Germany"), ("Tokyo", "Japan")):\n'
           '    a = Thing.ensure(name=city, nature="place")\n'
           '    b = Thing.ensure(name=land, nature="place")\n'
           '    a.set_capital_of(b)\n'
           'print("two links")', "k2")
    # Break one of them the way retype used to: take its ends out of the image, not the record.
    links = rt.world.all(rt.world.classes["CapitalOf"], limit=None)
    tokyo_link = next(l for l in links if l.subject.name == "Tokyo")
    rt.store.conn.execute("DELETE FROM 'CapitalOf' WHERE instance_id = ? AND attr IN "
                          "('subject', 'object')", (tokyo_link.id,))
    rt.store.conn.commit()
    rt.store._identity.clear()
    got = rt.run('print([t.name for t in Thing.get(name="Germany").related("capital")])', "k2")
    check("one unreadable link does not take the rest of its type with it",
          got["ok"] and "Berlin" in (got["output"] or ""),
          str(got.get("error") or got.get("output"))[:160])

    # --- what the refusal tells you to do has to work in the same breath ---
    # The world refuses an attribute the class has not got, and now says to declare it. Growing
    # a class used to build a new class object, leaving the instance in hand and the name in the
    # run's namespace on the old spec — so a host that did exactly what it was told got the same
    # refusal again, with no way past it from inside the run. That is where prose comes from.
    rt = open_world()
    authoring.install(rt.world, None)
    rt.start_task("k3", "record what the user said about somebody's pay", "recording")
    taken = rt.run('p = Person.new(name="Ada Byron")\np.salary = 120000\n'
                   'print(Person.get(name="Ada Byron").salary)', "k3")
    check("an attribute the class has not got is taken, with its type guessed",
          taken["ok"] and "120000" in (taken["output"] or ""),
          str(taken.get("error"))[:110])
    done = rt.run('world.attribute(Person, "salary", "what they are paid a year", type="int")\n'
                  'p = Person.get(name="Ada Byron")\np.salary = 120000\nprint(p.salary)', "k3")
    check("and saying what it means works in the same run",
          done["ok"] and "120000" in (done["output"] or ""),
          str(done.get("error") or done.get("output"))[:140])
    # Writable and not findable is the other half of the same trap. `find`/`get` prefers
    # `world.specs` — the dictionary the world opened with — to the class, and so does the
    # assembler when it asks whether a slot holds one value or many. A grown spec has to land
    # in both, or the attribute works until somebody looks for it.
    found = rt.run('print([p.name for p in Person.find(salary=120000)])', "k3")
    check("and the grown attribute can be searched by, not only written",
          found["ok"] and "Ada Byron" in (found["output"] or ""),
          str(found.get("error") or found.get("output"))[:140])
    # Adding is the whole of what growth does: nothing here redeclares, removes or renames,
    # because everything recorded under a word was recorded meaning it. The refusal has to say
    # what the word already means, or a host that wanted another type is left with nowhere to go.
    again = rt.run('world.attribute(Person, "salary", "now as words", type="str")', "k3")
    check("an attribute cannot be redeclared into another type",
          not again["ok"] and "already declared" in str(again.get("error")),
          str(again.get("error"))[:90])
    check("and the refusal says what the word already means",
          "int" in str(again.get("error")) and "paid a year" in str(again.get("error")),
          str(again.get("error"))[-160:])

    # --- a word the host writes before anybody says what it means ---
    # Refusing this is right about the ontology and wrong about the cost: a raise stops the
    # block, everything after it goes unrecorded, and a host that keeps hitting a wall writes
    # prose. So the word is taken, and the two things no value can tell you — what it means
    # and whether it supersedes — are asked for at the close.
    work = Path(tempfile.mkdtemp(prefix="tw-taken-"))
    rt = WorldRuntime(str(work / "w.db"), 
                      specs=ont_base(ROOT / "ontology" / "core"), selves=True)
    authoring.install(rt.world, work / "grown")
    rt.start_task("k4", "record what the user said about Ada and her pay", "recording")
    wrote = rt.run('ada = Person.new(name="Ada Byron")\n'
                   'ada.describe("the person the user is telling me about")\n'
                   'ada.salary = 120000\nada.phone = "+7 (900) 000-00-01"\n'
                   'print(Person.get(name="Ada Byron").salary)', "k4")
    check("a word nobody declared is taken, not refused",
          wrote["ok"] and "120000" in (wrote["output"] or ""),
          str(wrote.get("error"))[:120])
    held = rt.finish_task("k4")
    check("and the task will not close until somebody says what it means",
          held is not None and "taken on your word" in held, str(held)[:110])
    check("and the close hands back the call to write",
          "world.attribute(Person, 'salary'" in (held or ""), str(held)[:200])
    said = rt.run('world.attribute(Person, "salary", "what they are paid a year, before tax", '
                  'type="int", changes=True)\n'
                  'world.attribute(Person, "phone", "the number she is called on", type="phone")\n'
                  'print("said")', "k4")
    check("saying what it means is not redeclaring it", said["ok"], str(said.get("error"))[:120])
    kept = rt.run('print(Person.get(name="Ada Byron").salary)\n'
                  'print([p.name for p in Person.find(phone="+79000000001")])', "k4")
    check("what was written under the word is still there, and the type now holds",
          "120000" in (kept["output"] or "") and "Ada Byron" in (kept["output"] or ""),
          str(kept.get("error") or kept.get("output"))[:140])
    check("and then it closes", "taken on your word" not in (rt.finish_task("k4") or ""))

    # --- a class the world started with and one it made are the same kind of thing ---
    # The preset is what a world opens with and nothing more. What distinguishes a class is
    # recorded as its source; how it is built, extended and changed does not depend on it.
    import tempfile as _tf
    from pathlib import Path as _P
    from terraweaver import ontology as _ontology
    room = _P(_tf.mkdtemp(prefix="tw-preset-"))
    one = open_world(str(room / "world.db"))
    one.start_task("k", "make a class and change one the world started with", "recording")
    one.world.extras["define"]("Sport", "A game people play and follow.", identified_by="name")
    check("a class the world started with says so", one.world.classes["Person"]._spec.get("source") == "preset",
          str(one.world.classes["Person"]._spec.get("source")))
    check("and one it made says who made it", one.world.classes["Sport"]._spec.get("source") == "agent",
          str(one.world.classes["Sport"]._spec.get("source")))
    # An addition to a class the world made, filed so it sorts before the class it extends: in one
    # pass it was refused as "not a core class", which made the preset the only thing to build on.
    (room / "grown" / "AAA_sport_rules.json").write_text(json.dumps(
        {"name": "AAA_sport_rules", "extends": "Sport", "because": "rules came up three times",
         "attributes": [{"name": "rules", "type": "str", "description": "How the game is played."}]}))
    # A change to a class the world started with — kept by the world, the way any change is. It
    # was not: the preset won over the world's own version on reopening, and an attribute grown on
    # Person was there for the session and gone the next time the world was opened.
    one.world.extras["attribute"](one.world.classes["Person"], "email",
                                  "The address this person reads their mail at.", type="email")
    check("changing a class the world started with is kept beside the world",
          (room / "grown" / "Person.json").exists(),
          str(sorted(p.name for p in (room / "grown").glob("*.json"))))
    two = open_world(str(room / "world.db"))
    check("an addition lands on a class the world made, whatever the order of the files",
          "rules" in [a["name"] for a in two.world.classes["Sport"]._spec["attributes"]],
          str([a["name"] for a in two.world.classes["Sport"]._spec["attributes"]]))
    check("and the world opens with its own version of a class it started with",
          "email" in [a["name"] for a in two.world.classes["Person"]._spec["attributes"]],
          str([a["name"] for a in two.world.classes["Person"]._spec["attributes"]]))
    check("while the preset itself is untouched",
          '"email"' not in (_P(__file__).resolve().parent.parent / "ontology" / "core"
                            / "Person.json").read_text())
    _ontology.set_world(two.world)

    # A class the host defines is identified by the attribute it named — and still is after the
    # world is reopened. `list("name")` is `['n', 'a', 'm', 'e']`, so it used to come back keyed on
    # an attribute called `n`, which nothing has. Measured 2026-09-28: twenty classes the reading
    # had made were keyed that way in a 455-fact world, and since the reading moves entities into
    # the classes it makes, a thing findable by name stopped being findable the moment it was
    # placed. The host then answered "not recorded" about facts the world held.
    from terraweaver import matching

    where = Path(tempfile.mkdtemp(prefix="tw-keys-"))
    rt = open_world(str(where / "world.db"), home=where)
    rt.start_task("k", "define a class and put something in it", "recording")
    rt.run('world.define("City", "a place people live in", "name")\n'
           'City.new(name="London")', "k")
    again = open_world(str(where / "world.db"), home=where)
    check("a class the host defined keeps its name key when the world is reopened",
          matching.NAME_KEYS.get("City") == "name", str(matching.NAME_KEYS.get("City")))
    found = again.run('print(City.identify(name="London"))', "k")
    check("so what was put in it is found by name again",
          "London" in (found.get("output") or ""),
          str(found.get("error") or found.get("output"))[:120])

    print()
    if failures:
        print(f"{len(failures)} failed: {', '.join(failures)}")
        return 1
    print("all growth tests passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())

