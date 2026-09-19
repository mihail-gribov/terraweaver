"""Tests for relations: instances linking two entities, and what the world checks about them.

Run: .venv/bin/python tests/test_relations.py
"""
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from terraweaver.impls import IMPLS
from terraweaver.ontology import build_classes, load_specs
from terraweaver.store import Store
from terraweaver.world import World
from worlds.job_search import build

ONTOLOGY_DIR = Path(__file__).resolve().parent.parent / "ontology" / "core"
failures: list[str] = []


def check(name: str, condition: bool, detail: str = "") -> None:
    print(f"{'PASS' if condition else 'FAIL'}  {name}" + (f"  — {detail}" if detail and not condition else ""))
    if not condition:
        failures.append(name)


def refused(action) -> str | None:
    try:
        action()
    except (ValueError, TypeError) as exc:
        return str(exc)
    return None


def main() -> int:
    classes = build_classes(load_specs(ONTOLOGY_DIR), IMPLS)
    store = Store(":memory:")
    build(classes, store)
    world = World(store, classes)
    Person, Organization = classes["Person"], classes["Organization"]
    owner = world.owner

    # --- the fixture's links are relations now ---
    ada = Person.get(email="ada@example.com")
    techcorp = Organization.get(name="TechCorp")
    check("organization reads the primary membership", ada.organization is techcorp)
    check("job_title reads its role", ada.job_title == "Staff Engineer")
    check("employees read the memberships", ada in techcorp.employees)
    bob = Person.get(email="robert@example.com")
    check("a relationship to the owner reads from relations", bob.relationship == "former manager", str(bob.relationship))
    check("a recruiter is a Service to the owner",
          Person.get(email="anna.peterson@example.com").relationship == "recruiter")

    # --- symmetric: seen from both ends ---
    darren = Person.new(full_name="Darren Liu", email="darren@example.com")
    kevin = Person.new(full_name="Kevin Liu", email="kevin.liu@example.com")
    kevin.relate(darren, "kin", label="older brother")
    check("a symmetric relation is seen from both ends",
          darren.related("kin") == [kevin] and kevin.related("kin") == [darren])
    again = kevin.relate(darren, "kin", label="older brother")
    check("relating again updates, doesn't duplicate", len(darren.relations("kin")) == 1 and again is darren.relations("kin")[0])
    darren.relate(kevin, "kin", label="younger brother")
    tie = darren.relations("kin")[0]
    check("each side of a symmetric relation keeps its own label",
          tie.label == "older brother" and tie.label_reverse == "younger brother", f"{tie.label} / {tie.label_reverse}")
    check("a relation can't link something to itself", refused(lambda: kevin.relate(kevin, "social")) is not None)

    # --- one at a time: overlapping periods, not "now" ---
    naomi = Person.new(full_name="Naomi Park", email="naomi@example.com")
    lena = Person.new(full_name="Lena Ross", email="lena@example.com")
    first = darren.relate(naomi, "partner", label="girlfriend", starts=date(2024, 9, 1))
    check("a second current partner is refused", refused(lambda: darren.relate(lena, "partner")) is not None)
    first.keep(until=date(2026, 1, 1))
    check("after the first one ended, a new one goes through",
          refused(lambda: darren.relate(lena, "partner", starts=date(2026, 3, 1))) is None)
    check("and the ended one is history", darren.related("partner") == [lena]
          and naomi in darren.related("partner", history=True))

    # --- direction, reverse names, chains ---
    company = Organization.new(name="Meridian Corp")
    b04 = Organization.new(name="Supply Chain Operations", aliases=["B04"])
    b04.relate(company, "part_of", label="department")
    chen = Person.new(full_name="Kevin Chen", email="kchen@meridian.example")
    job = chen.relate(b04, "membership", role="vendor logistics lead", starts=date(2026, 1, 15))
    linda = Person.new(full_name="Linda Zhao", email="lzhao@meridian.example")
    linda.relate(b04, "authority", label="manager")
    check("read from the object's end by the reverse name", b04.related("members") == [chen])
    check("a membership extends along part_of", chen.related("membership") == [b04, company],
          str(chen.related("membership")))
    check("who manages the department", b04.related("managed_by") == [linda])
    check("a cycle of parts is refused", refused(lambda: company.relate(b04, "part_of")) is not None)
    check("a second current manager of the same department is refused",
          refused(lambda: chen.relate(b04, "authority")) is not None)
    check("an endpoint of the wrong class is refused", refused(lambda: b04.relate(chen, "kin")) is not None)

    # --- a relation is an instance: attributes, history, comments ---
    job.role = "team lead"
    check("a relation's attribute keeps its history", [p.value for p in job.history("role")] == ["vendor logistics lead", "team lead"])
    job.comment("moved from Procurement")
    check("a relation takes comments", bool(job.comments(contains="Procurement")))

    # --- organization assignment moves the primary membership ---
    ada.organization = Organization.get(name="DataWorks")
    check("a new job closes the old one", techcorp not in ada.related("membership")
          and techcorp in ada.related("membership", history=True))
    check("and the job history comes from memberships",
          [p.value.name for p in ada.history("organization")] == ["TechCorp", "DataWorks"])

    # --- construction with relation-backed fields ---
    priya = Person.new(full_name="Priya Shah", email="priya@example.com",
                       organization=Organization.get(name="GreenGrid"), job_title="Data Engineer",
                       relationship="friend")
    check("organization, job title and relationship given at creation become relations",
          priya.organization.name == "GreenGrid" and priya.job_title == "Data Engineer" and priya.relationship == "friend")

    # --- the free type ---
    godfather = Person.new(full_name="Victor Hale", email="victor@example.com")
    check("Related needs a label and a description", refused(lambda: godfather.relate(priya, "related")) is not None)
    check("with them it goes through", refused(lambda: godfather.relate(
        priya, "related", label="godfather", description="Priya's godfather")) is None)

    # --- find compares entities by identity, not name ---
    twin = Organization.new(name="Meridian Corp (Boston)")
    check("find by a referenced entity matches that record only",
          [p.full_name for p in Person.find(organization=b04).main] == ["Kevin Chen"])

    print()
    if failures:
        print(f"{len(failures)} failed: {', '.join(failures)}")
        return 1
    print("all relation tests passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
