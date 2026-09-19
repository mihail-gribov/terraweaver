DESCRIPTION = """Two hops through the social graph: nobody the owner knows works at HealthSync, but his
friend Priya knows Omar, who does. The answer has to walk owner → friend → her acquaintance → his
employer. Read-only."""

SETUP = """
priya = Person.new(full_name="Priya Shah", email="priya@example.com")
owner.relate(priya, "social", label="friend")
omar = Person.new(full_name="Omar Haddad", email="omar@healthsync.example")
omar.relate(Organization.get(name="HealthSync"), "membership", role="engineering manager", primary=True)
priya.relate(omar, "social", label="old classmate")
"""

TURNS = ["Using my world (terraweaver): do I know anyone who knows someone at HealthSync? I'd like an intro."]

EXPECT = "pass"

ANSWER_MUST = ["Priya", "Omar"]

LEVEL = "hard"
