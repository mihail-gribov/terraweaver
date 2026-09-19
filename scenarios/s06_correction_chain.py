DESCRIPTION = """A statement corrected in the next breath: "Priya moved to FinEdge" → "no, she only
has an offer from them". The world must end with her still at GreenGrid and the offer kept as
something tentative — not the first statement recorded as fact (MemOps-style update chain)."""

SETUP = """
Person.new(full_name="Priya Shah", email="priya@example.com", job_title="Data Engineer",
           organization=Organization.get(name="GreenGrid"))
"""

TURNS = [
    "Using my world (terraweaver): Priya Shah just moved from GreenGrid to FinEdge.",
    "Wait, I got that wrong — she hasn't moved. She only has an offer from FinEdge; she's still at "
    "GreenGrid for now.",
]

EXPECT = """
priya = Person.get(email="priya@example.com")
assert priya.organization.name == "GreenGrid", f"Priya is recorded at {priya.organization.name}"
fin = Organization.get(name="FinEdge")
assert priya not in (fin.employees or []), "Priya listed among FinEdge employees"
offer = [c for c in priya.comments() if "offer" in c.text.lower()] + [
    f for f in Preference.find(subject=priya) if "offer" in f.value.lower()]
assert offer, "the FinEdge offer isn't recorded anywhere on Priya"
"""

# Asked afterwards, each in a fresh conversation: (question, must mention, must not mention).
# The same in every mode, so an agent keeping the data its own way is judged alike.
PROBES = [
    ('Using my world (terraweaver): where does Priya Shah work, and does she have any job offers?',
     ['GreenGrid', 'FinEdge', 'offer'], []),
]

LEVEL = "hard"
