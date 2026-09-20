DESCRIPTION = """One partner relation ends and another begins: Darren and Naomi broke up, he's now with
Emma. The old relation is closed — not deleted, not left current — so "one at a time" holds, and
both the present and the past can be told."""

SETUP = """
darren = Person.new(full_name="Darren Liu", email="darren@example.com")
owner.relate(darren, "social", label="best friend")
naomi = Person.new(full_name="Naomi Park", email="naomi@example.com")
darren.relate(naomi, "partner", label="girlfriend", starts=date(2024, 9, 1))
"""

TURNS = [
    "Using my world (terraweaver): Darren and Naomi broke up last week. He's now seeing Emma Lind "
    "(emma@example.com).",
]

EXPECT = """
darren = Person.get(email="darren@example.com")
now_ = [p.full_name for p in darren.related("partner")]
assert now_ == ["Emma Lind"], f"current partner(s): {now_}"
naomi = Person.get(email="naomi@example.com")
assert naomi in darren.related("partner", any_time=True), "the relationship with Naomi was deleted instead of ended"
"""

PROBES = [
    ("Using my world (terraweaver): who is Darren dating now, and who was he with before?", ["Emma", "Naomi"], []),
]

LEVEL = "hard"
