DESCRIPTION = """A value that changes: Anna Peterson's email. The stored value disagrees with the new
one, so the world raises it; the user has already said it changed, so the end state must be the new
email on the same person — no second Anna Peterson, nothing else touched."""

SETUP = ""

TURNS = [
    "Using my world (terraweaver): Anna Peterson's email has changed — it's anna@dataworks.io now.",
    "Yes, the new one is right.",
]

EXPECT = """
annas = [p for p in Person.all(limit=None) if p.full_name == "Anna Peterson"]
assert len(annas) == 1, f"expected one Anna Peterson, got {len(annas)}"
anna = annas[0]
assert anna.email == "anna@dataworks.io", f"email is {anna.email}"
assert anna.organization.name == "DataWorks", "her employer changed"
"""

# Asked afterwards, each in a fresh conversation: (question, must mention, must not mention).
# The same in every mode, so an agent keeping the data its own way is judged alike.
PROBES = [
    ("Using my world (terraweaver): what's Anna Peterson's email address?",
     ['anna@dataworks.io'], []),
]

# Passed in every mode with Opus and Haiku: kept for regression, left out of comparisons.
LEVEL = "basic"
