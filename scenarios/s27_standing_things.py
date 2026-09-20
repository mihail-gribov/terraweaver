DESCRIPTION = """The standing parts of a week, given once the way a person gives them: a standup every
morning, a 1:1 every other Tuesday, an on-call rota every third week, rent on the first. Nothing here
says how to keep them. What is checked is whether the world can still answer about them months out —
a question a list of occurrences written once cannot answer, because the list runs out."""

SETUP = """
nils = Person.new(full_name="Nils Ek", email="nils@meridian.example")
nils.relate(owner, "social", label="colleague")
# An ordinary diary around them, so "what's standing" is not the same as "everything".
for i, (title, kind) in enumerate([("dentist", "appointment"), ("Ana's leaving do", "meeting"),
                                   ("quarterly review", "meeting")]):
    Event.new(title=title, kind=kind, status="confirmed", start_time=now() + timedelta(days=3 + i * 6))
"""

TURNS = [
    "Using my world (terraweaver): let me get the standing parts of my week in. Standup every "
    "morning at 9:15, quarter of an hour. My 1:1 with Nils is every other Tuesday at 3pm — the "
    "next one is 22 September. I'm on the on-call rota every third week for a week at a time, and "
    "my current stretch started on 7 September. Rent is 2,100 on the 1st of every month.",
]

EXPECT = """
# Either shape counts — a rule, or occurrences written out — as long as the world still reaches
# next year. What must not happen is a handful of rows that stop in a fortnight.
rules = world.repeats()
ahead = [e for e in Event.all(limit=None, any_time=True)
         if getattr(e, "start_time", None) and e.start_time > now() + timedelta(days=120)]
assert rules or ahead, (
    "nothing in the world reaches past four months: the standing things were written down once "
    f"and stop. repeats={rules}, events past 120 days={len(ahead)}")
"""

PROBES = [
    ("Using my world (terraweaver): when is my next 1:1 with Nils after New Year?",
     ["12 January|January 12|2027-01-12|Jan 12"], []),
    ("Using my world (terraweaver): which days am I on call in October?",
     ["19"], []),
    ("Using my world (terraweaver): what's standing in my week — the things that repeat, not "
     "one-offs?",
     ["standup", "Nils|1:1", "on.?call"], ["dentist", "leaving do"]),
]

# A design scenario: it exists to catch the mechanism rotting, not to measure the model. If
# cyclic periods (periods.py, recurrence.py) stop working, or stop being reachable from the
# host's side, every probe here goes wrong at once.
LEVEL = "design"
