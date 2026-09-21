DESCRIPTION = """Once the user has said which Annie they mean, a later conversation must not ask
again: the world remembers the choice and the host goes with it (saying whom it assumed)."""

SETUP = ""

CONVERSATIONS = [
    [
        "Using my world (terraweaver): what's Annie's job title?",
        "Anna Sullivan, from CloudNine.",
    ],
    [
        "Using my world (terraweaver): which company does Annie work for?",
    ],
]

EXPECT = """
meant = Person.get(email="anna.sullivan@example.com")
try:
    taken_as = Person.get(full_name="Annie")
except NotInWorld:
    taken_as = None
assert taken_as == meant, (
    f"'Annie' is taken as {taken_as.display_name() if taken_as else 'nobody'}, not {meant.display_name()} — "
    f"the choice wasn't remembered")
"""

ANSWER_MUST = ["CloudNine"]
# Naming the other Annie as the alternative is right — that's how the host says what it assumed.
ANSWER_MUST_NOT = ["which annie", "which one do you mean"]

# Asked afterwards, each in a fresh conversation: (question, must mention, must not mention).
# The same in every mode, so an agent keeping the data its own way is judged alike.
PROBES = [
    ("Using my world (terraweaver): what's Annie's email address?",
     ['anna.sullivan@example.com'], []),
]

LEVEL = "hard"
