DESCRIPTION = """Forgetting exactly one thing: the rumour about Bob moving goes; what else is known
about Bob — his hobby, his employer — stays."""

SETUP = """
bob = Person.get(email="robert@example.com")
bob.comment("might move to Berlin in the spring", when=date(2026, 9, 18), tentative=True)
bob.comment("loves sailing, has a boat at Lake Union", permanent=True)
"""

TURNS = ["Using my world (terraweaver): forget what I told you about Bob moving — it was just a rumour."]

EXPECT = """
bob = Person.get(email="robert@example.com")
assert not bob.comments(contains="Berlin"), "the rumour is still current"
assert bob.comments(contains="sailing"), "Bob's hobby was lost"
assert bob.organization.name == "FinEdge", "Bob's employer changed"
"""

PROBES = [
    ("Using my world (terraweaver): tell me everything you know about Bob.",
     ["sailing", "FinEdge"], ["Berlin"]),
]

LEVEL = "hard"
