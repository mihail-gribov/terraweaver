DESCRIPTION = """Family through marriage and work in one sentence: the owner's sister Olga, her husband
Mark, and Mark's job at FinEdge — where Bob works too. Answering "who do I know at FinEdge" and "who
is Mark to me" takes the chain owner → sister → her husband → his employer."""

SETUP = """
olga = Person.new(full_name="Olga Gribova", email="olga@example.com")
owner.relate(olga, "kin", label="brother", label_reverse="sister")
"""

TURNS = [
    "Using my world (terraweaver): my sister Olga's husband, Mark Stone (mark.stone@example.com), works at "
    "FinEdge — the same company as Bob. Please record that.",
]

EXPECT = """
mark = Person.get(email="mark.stone@example.com")
olga = Person.get(email="olga@example.com")
assert olga in mark.related("partner"), "Mark and Olga aren't recorded as a couple"
assert mark.organization is not None and mark.organization.name == "FinEdge", "Mark's job isn't recorded"
assert len([p for p in Person.all(limit=None) if "olga" in p.full_name.lower()]) == 1, "Olga duplicated"
"""

PROBES = [
    ("Using my world (terraweaver): who do I know at FinEdge?", ["Mark", "Wolfe"], []),
    ("Using my world (terraweaver): how is Mark Stone connected to me?", ["Olga", "sister"], []),
]

LEVEL = "hard"
