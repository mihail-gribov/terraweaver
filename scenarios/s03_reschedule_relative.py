DESCRIPTION = """Move an event relative to another one and notify someone named by role: "the
recruiter" is the contact on the vacancy the interview is about (Anna Peterson). The event is
moved, not duplicated; its status isn't changed on the host's own initiative."""

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
assert iv.status == "confirmed", f"status changed to {iv.status}"
assert Person.get(email="anna.peterson@example.com").comments(contains="email sent"), "recruiter not told"
"""
