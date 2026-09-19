DESCRIPTION = """Services that change hands on a date: from next month the dentist is Dr. Patel instead
of Dr. Rao, at the same clinic; plus a landlord with a monthly rent. Today and next month have
different answers."""

SETUP = """
clinic = Organization.new(name="SmileCare")
rao = Person.new(full_name="Arun Rao", email="rao@smilecare.example")
rao.relate(clinic, "membership", role="dentist", primary=True)
rao.relate(owner, "service", label="dentist")
"""

TURNS = [
    "Using my world (terraweaver): from October 1 my dentist will be Dr. Nina Patel at the same SmileCare "
    "clinic, instead of Dr. Rao. Also — our landlord is Greg Hunt, and the rent is $2,100 a month.",
]

EXPECT = """
rao = Person.get(email="rao@smilecare.example")
ending = [r for r in rao.relations("service", history=True) if r.object == owner]
assert ending and ending[0].valid_until is not None and ending[0].valid_until.date() == date(2026, 10, 1), "Dr. Rao isn't recorded as ending on October 1"
patel = [p for p in Person.all(limit=None) if "patel" in p.full_name.lower()]
assert len(patel) == 1, "Dr. Patel not recorded once"
starting = [r for r in patel[0].relations("service", history=True) if r.object == owner]
assert starting and starting[0].valid_from is not None and starting[0].valid_from.date() == date(2026, 10, 1), "Dr. Patel isn't recorded as starting on October 1"
greg = [p for p in Person.all(limit=None) if "greg" in p.full_name.lower()]
assert greg and any(r.object == owner for r in greg[0].relations("service")), "the landlord isn't recorded as serving the owner"
"""

PROBES = [
    ("Using my world (terraweaver): who is my dentist right now, who will it be next month, and who is my "
     "landlord and what's the rent?",
     ["Rao", "Patel", "Greg", "2,100|2100"], []),
]

LEVEL = "hard"
