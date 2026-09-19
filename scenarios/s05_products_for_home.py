DESCRIPTION = """A shopping conversation the object model has no Product class for: a TV for the
living room and a hair dryer for the owner's wife, each with criteria and several candidate models
that are only ideas so far, not decisions. The
host has to lay it out in the world (a person for the wife, the two purchases, criteria, the
candidates) so that a later, separate conversation can pick it up from the world alone."""

SETUP = ""

CONVERSATIONS = [
    [
        "Using my world (terraweaver): I'm choosing two things. First, a TV for the living room — "
        "65 inches, budget up to $1,500, it must be good for watching football in a bright room. Ideas "
        "so far: the Samsung QN90D, the LG C4 and the Sony Bravia 8; the LG looks nicer but I worry about glare. Second, a "
        "hair dryer for my wife, Elena — she wants something light and quiet, under $400. Candidates are "
        "the Dyson Supersonic and the Philips 7000. Keep track of all this for me.",
        "Her email is elena@example.com. And we've pretty much ruled out the LG because of the glare.",
    ],
    [
        "Using my world (terraweaver): remind me where we are with the TV and with Elena's hair dryer — "
        "what are we choosing between and what matters?",
    ],
]

EXPECT = """
elena = Person.get(email="elena@example.com")
assert "elena" in elena.full_name.lower(), f"wife recorded as {elena.full_name}"
everything = " ".join(
    [repr(e) for cls in (Project, Idea, Preference, Event) for e in cls.all(limit=None)]
    + [c.text for c in world.comments(limit=500, include_expired=True)]
).lower()
for model in ("qn90d", "c4", "bravia", "supersonic", "philips"):
    assert model in everything, f"{model} not recorded anywhere"
assert "1,500" in everything or "1500" in everything, "TV budget not recorded"
assert "400" in everything, "dryer budget not recorded"
assert "glare" in everything, "why the LG was ruled out isn't recorded"
"""

ANSWER_MUST = ["QN90D", "Bravia", "Supersonic", "glare"]

# Asked afterwards, each in a fresh conversation: (question, must mention, must not mention).
# The same in every mode, so an agent keeping the data its own way is judged alike.
PROBES = [
    ('Using my world (terraweaver): which TVs are still in the running, and why was one dropped?',
     ['QN90D', 'Bravia', 'glare'], []),
]
