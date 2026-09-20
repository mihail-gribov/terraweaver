DESCRIPTION = """Something that runs through a life for months and touches everything: a move. A flat,
a landlord, a mover, a school, dates, people who helped. None of it is one kind of thing and no
relation joins them, so the only way to pull it up later is to have marked it. Whether the host
reaches for that is the question — nothing in the task says the word."""

SETUP = """
lisbon = Place.new(name="Lisbon", city="Lisbon", category="other")
firm = Organization.new(name="Azulejo Movers", industry="Logistics")
landlord = Person.new(full_name="Rui Campos", email="rui.campos@example.com")
landlord.relate(owner, "service", label="landlord", fee=1450)
school = Organization.new(name="Escola Beatriz", industry="Education")
# A year of ordinary life around it, so "everything about the move" is not just "everything".
for i, (title, kind) in enumerate([("standup", "meeting"), ("dentist", "appointment"),
                                   ("book club", "meeting"), ("1:1 with Nils", "meeting"),
                                   ("payroll call", "call"), ("gym induction", "appointment")]):
    Event.new(title=title, kind=kind, status="confirmed",
              start_time=now() - timedelta(days=5 + i * 9))
"""

TURNS = [
    "Using my world (terraweaver): we're moving to Lisbon on 14 March. Things so far: the flat is "
    "through Rui Campos, 1450 a month; Azulejo Movers quoted 2,300 and can do the 12th; the kids "
    "start at Escola Beatriz after Easter; and I need to give notice here by 1 February. Keep all "
    "of that together — I'll be adding to it for months.",
]

EXPECT = """
moving = [t for t, entry in world.tags().items() if "mov" in t or "lisbon" in t or "relocat" in t]
assert moving, f"nothing was marked as belonging together: {list(world.tags())}"
covered = {type(e).__name__ for tag in moving for e in world.tagged(tag)}
assert len(covered) >= 2, f"the mark covers only {covered} — a move is not one kind of thing"
"""

PROBES = [
    ("Using my world (terraweaver): pull up everything to do with the move — what's settled, what "
     "isn't, and what's the next date I need to act on.",
     ["Rui|Campos|flat", "Azulejo|movers", "February|notice"], []),
    ("Using my world (terraweaver): the movers now say the 12th doesn't work, it has to be the "
     "13th. Note that, and tell me what else that date touches.",
     ["13"], []),
]

LEVEL = "hard"
