DESCRIPTION = """Something that runs through a life for months and touches everything: a move. A flat,
a landlord, a mover, a school, dates. None of it is one kind of thing, and the task never says how
to keep it together — that is the question. Either answer counts: a project everything hangs off,
or a tag on each piece. What is checked is that the pieces can be pulled up as one thing months
later, and that the second turn finds what a date change touches."""

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
# Either way of keeping it together counts; what matters is that one thing gathers the pieces.
marked = [t for t, entry in world.tags().items() if "mov" in t or "lisbon" in t or "relocat" in t]
gathered = {type(e).__name__ for tag in marked for e in world.tagged(tag)}
for project in Project.all(limit=None):
    if "mov" in (project.name or "").lower() or "lisbon" in (project.name or "").lower():
        gathered |= {type(e).__name__ for e in project.related("participation")}
        gathered |= {type(r.other(project)).__name__ for r in project.relations()}
assert len(gathered) >= 2, (
    f"the move isn't gathered anywhere: tags {list(world.tags())}, reached {gathered}")
"""

PROBES = [
    ("Using my world (terraweaver): pull up everything to do with the move — what's settled, what "
     "isn't, and what's the next date I need to act on.",
     ["Rui|Campos|flat", "Azulejo|movers", "February|notice"], []),
    ("Using my world (terraweaver): the movers now say the 12th doesn't work, it has to be the "
     "13th. Note that, and tell me what else that date touches.",
     ["13"], []),
]

# Draft: not in any pool yet. What it set out to observe, it already showed — given a months-long
# thing and no instruction, the host reaches for a tag on each piece in one run and invents a
# Project with relations in another, both without being told. What it still needs before it can
# score anything: a world of its own rather than the job_search fixture underneath (the checks
# keep catching that world's entities), and probes that accept either shape of answer.
LEVEL = "draft"
