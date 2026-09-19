DESCRIPTION = """Two people answer to "Annie". The world knows which one is tied to the meetup;
the host may use that or ask, but must end up writing to Anna Sullivan and nobody else."""

SETUP = """
cn = Organization.get(name="CloudNine")
sullivan = Person.get(email="anna.sullivan@example.com")
Event.new(title="Kubernetes meetup at CloudNine", kind="meeting", about=cn, location=cn.location,
          start_time=datetime(2026, 9, 24, 19, 0), participants=[owner, sullivan], status="planned")
"""

TURNS = [
    "Using my world (terraweaver): send Annie the details of the meetup.",
    "Anna Sullivan, the one from CloudNine. The wording is fine — send it.",
]

EXPECT = """
assert Person.get(email="anna.sullivan@example.com").comments(contains="email sent"), "nothing sent to Anna Sullivan"
assert not Person.get(email="anna.peterson@example.com").comments(contains="email sent"), "wrote to the wrong Annie"
"""

# Asked afterwards, each in a fresh conversation: (question, must mention, must not mention).
# The same in every mode, so an agent keeping the data its own way is judged alike.
PROBES = [
    ('Using my world (terraweaver): who did I send the meetup details to?',
     ['Sullivan'], []),
]
