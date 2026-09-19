DESCRIPTION = """Recording a short story: an existing person picked out by context (Annie at
CloudNine), a new event, a new person (new, not ensure), and an uncertain fact kept as a
tentative remark rather than as truth. Nothing may be duplicated."""

SETUP = ""

TURNS = [
    "Record this in my world (terraweaver): yesterday I had a call with Annie from CloudNine; she "
    "invited me to a Kubernetes meetup next Thursday at 7pm at their office. Also, I met someone new: "
    "Priya Shah (priya@example.com), a data engineer at GreenGrid. And Bob told me he might move to "
    "Berlin in the spring — nothing certain yet.",
]

EXPECT = """
days_ahead = (3 - today().weekday()) % 7 or 7
thursday = today() + timedelta(days=days_ahead + (7 if days_ahead < 3 else 0))
meetups = [e for e in Event.all(limit=None) if "meetup" in e.title.lower()]
assert len(meetups) == 1, f"expected one meetup, got {len(meetups)}"
m = meetups[0]
assert m.start_time.hour == 19, f"meetup at {m.start_time}"
assert Person.get(email="anna.sullivan@example.com") in m.participants, "Anna Sullivan should be a participant"
priya = Person.find(email="priya@example.com").main
assert len(priya) == 1, "Priya recorded once"
assert priya[0].organization.name == "GreenGrid"
gg = Organization.get(name="GreenGrid")
assert [p.full_name for p in gg.employees].count("Priya Shah") == 1, "Priya listed once at GreenGrid"
bob = Person.get(email="robert@example.com")
berlin = bob.comments(contains="Berlin")
assert berlin and berlin[0].tentative, "Bob's move is a tentative remark"
assert bob.organization.name == "FinEdge", "Bob's employer untouched"
"""
