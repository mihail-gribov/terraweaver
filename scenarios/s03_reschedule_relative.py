DESCRIPTION = """Move an event relative to another one and notify someone named by role: "the
recruiter" is the contact on the vacancy the interview is about (Anna Peterson). The event is
moved, not duplicated. The host may mark it planned until the recruiter confirms — an assignment is
its own call — but then says so, and the old status stays in the history."""

SETUP = """
cn = Organization.get(name="CloudNine")
Event.new(title="Kubernetes meetup at CloudNine", kind="meeting", about=cn, location=cn.location,
          start_time=datetime(2026, 9, 24, 19, 0), participants=[owner], status="planned")
"""

TURNS = [
    "Using my world (terraweaver): move my DataWorks interview to the day after the meetup, same time "
    "of day, and let the recruiter know.",
]

EXPECT = """
interviews = [e for e in Event.all(limit=None) if e.kind == "interview" and "DataWorks" in e.title]
assert len(interviews) == 1, f"expected one DataWorks interview, got {len(interviews)}"
iv = interviews[0]
assert iv.start_time.date() in (date(2026, 9, 25), date(2026, 9, 26)), f"interview now at {iv.start_time}"
assert iv.status in ("confirmed", "planned"), f"status changed to {iv.status}"
if iv.status == "planned":
    assert [p.value for p in iv.history("status")][0] == "confirmed", "the old status isn't in the history"
assert Person.get(email="anna.peterson@example.com").comments(contains="email sent"), "recruiter not told"
"""

# Asked afterwards, each in a fresh conversation: (question, must mention, must not mention).
# The same in every mode, so an agent keeping the data its own way is judged alike.
PROBES = [
    ('Using my world (terraweaver): when is my DataWorks interview now, and who did I tell about the change?',
     ['25', 'Peterson'], []),
]
