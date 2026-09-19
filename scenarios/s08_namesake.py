DESCRIPTION = """A namesake: a second Robert Wolfe, at PixelForge. `new` has to notice the existing
one and ask; once the user says it's a different person, a second Robert Wolfe is created and the
first stays exactly as he was."""

SETUP = ""

TURNS = [
    "Using my world (terraweaver): I met a new contact today — Robert Wolfe, a game designer at "
    "PixelForge (rwolfe@pixelforge.io).",
    "No, that's a different person — a different Robert Wolfe, not my former manager.",
]

EXPECT = """
wolfes = [p for p in Person.all(limit=None) if p.full_name == "Robert Wolfe"]
assert len(wolfes) == 2, f"expected two Robert Wolfes, got {len(wolfes)}"
old = Person.get(email="robert@example.com")
assert old.organization.name == "FinEdge" and old.job_title == "Head of Engineering", "the first Robert changed"
new = Person.get(email="rwolfe@pixelforge.io")
assert new is not old and new.organization.name == "PixelForge", "the new Robert isn't at PixelForge"
"""

# Asked afterwards, each in a fresh conversation: (question, must mention, must not mention).
# The same in every mode, so an agent keeping the data its own way is judged alike.
PROBES = [
    ('Using my world (terraweaver): how many people named Robert Wolfe do I know, and where does each work?',
     ['FinEdge', 'PixelForge'], []),
]

LEVEL = "hard"
