DESCRIPTION = """A reorganisation announced ahead of time: from March 1 the department B04 moves under
the Logistics division, Linda heads Logistics, and Kevin reports to Tom. Relations that start in the
future: today nothing changes, after March 1 the chain is different."""

SETUP = """
meridian = Organization.new(name="Meridian Corp")
b04 = Organization.new(name="Supply Chain Operations", aliases=["B04"])
b04.relate(meridian, "part_of", label="department")
logistics = Organization.new(name="Logistics")
logistics.relate(meridian, "part_of", label="division")
kevin = Person.new(full_name="Kevin Chen", email="kchen@meridian.example")
kevin.relate(b04, "membership", title="vendor logistics lead", primary=True, starts=date(2026, 1, 15))
linda = Person.new(full_name="Linda Zhao", email="lzhao@meridian.example")
linda.relate(b04, "membership", title="department manager", primary=True)
linda.relate(b04, "authority", label="manager")
tom = Person.new(full_name="Tom Reyes", email="treyes@meridian.example")
tom.relate(logistics, "membership", title="operations lead", primary=True)
"""

TURNS = [
    "Using my world (terraweaver): big reorg at Meridian. From March 1 next year, B04 (Supply Chain "
    "Operations) becomes part of the Logistics division instead of sitting directly under Meridian. "
    "Linda Zhao will be director of Logistics from then, and Kevin Chen will report to Tom Reyes instead "
    "of Linda. Until March nothing changes.",
]

EXPECT = """
b04 = Organization.get(name="Supply Chain Operations")
assert [o.name for o in b04.related("part_of")][:1] == ["Meridian Corp"], "B04 moved already — the reorg starts in March"
future = [r for r in b04.relations("part_of", history=True) if r.object.name == "Logistics"]
assert future and future[0].valid_from is not None and future[0].valid_from.date() == date(2027, 3, 1), "B04 → Logistics from March 1 not recorded"
tom = Person.get(email="treyes@meridian.example")
kevin = Person.get(email="kchen@meridian.example")
later = [r for r in tom.relations("authority", history=True) if r.object == kevin]
assert later and later[0].valid_from is not None and later[0].valid_from.date() == date(2027, 3, 1), "Tom over Kevin from March 1 not recorded"
"""

PROBES = [
    ("Using my world (terraweaver): who is Kevin Chen's manager today, who will it be after March 1, "
     "and which division will his department be in then?",
     ["Linda", "Tom", "Logistics"], []),
]

LEVEL = "hard"
