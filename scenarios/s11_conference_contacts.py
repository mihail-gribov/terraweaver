DESCRIPTION = """Adding people met at a conference to a world that already has many contacts, some of
them the same people written differently: a nickname (Kate for Katherine, Barb for Barbara), an
email in another case, a phone number in another format. Nobody may be duplicated; only the
genuinely new person is created."""

SETUP = """
people = [("Priya Shah", "priya@example.com"), ("Tom Becker", "tom.becker@example.com"),
          ("Sara Kim", "sara.kim@example.com"), ("Luis Ortega", "luis@example.com"),
          ("Mei Tanaka", "mei.t@example.com"), ("Omar Haddad", "omar@example.com"),
          ("Katie Johns", "katie.johns@example.com"), ("Kevin Johnson", "kevin.j@example.com"),
          ("Wilma Chen", "wilma.chen@example.com"), ("William Chang", "wchang@example.com")]
for name, email in people:
    Person.new(full_name=name, email=email)
Person.new(full_name="Katherine Johnson", email="kjohnson@nasa.gov", phone="+1 (555) 010-2030", aliases=["Katherine"])
Person.new(full_name="William Chen", email="william.chen@stripe.com", aliases=["William"])
"""

TURNS = [
    "Using my world (terraweaver): add the people I met at the conference — Kate Johnson from NASA "
    "(KJohnson@NASA.gov, +15550102030), Bill Chen from Stripe (William.Chen@stripe.com), Dana Scully "
    "(dana@fbi.gov, FBI), and Barb Liskov, who's advising a startup called Lumen AI now.",
]

EXPECT = """
assert len(Person.find(email="kjohnson@nasa.gov").matches) == 1, "Katherine duplicated"
assert len(Person.find(email="william.chen@stripe.com").matches) == 1, "William Chen duplicated"
assert len([p for p in Person.all(limit=None) if "liskov" in p.full_name.lower()]) == 1, "Barbara duplicated"
assert len(Person.find(email="dana@fbi.gov").matches) == 1, "Dana not recorded"
"""

PROBES = [
    ("Using my world (terraweaver): how many separate contact records do I have for Katherine Johnson, "
     "and how many for William Chen? Answer with the two numbers.",
     ["1"], ["2 records", "two records", "duplicate"]),
    ("Using my world (terraweaver): what's Dana Scully's email, and what is Barbara Liskov up to these days?",
     ["dana@fbi.gov", "Lumen"], []),
]

LEVEL = "hard"
