DESCRIPTION = """A purchase decided over three conversations: options, then one ruled out and a budget
one added, then the choice made at a price. The world has to carry all of it so a later question
about what happened, and why, can be answered."""

SETUP = ""

CONVERSATIONS = [
    ["Using my world (terraweaver): I'm choosing a 65-inch TV for the living room, budget up to $1,500, "
     "for football in a bright room. Options so far: Samsung QN90D, LG C4 and Sony Bravia 8."],
    ["Using my world (terraweaver): about the TV — the LG C4 is out, too much glare in our room. Add the "
     "TCL QM8 as a budget option, about $999."],
    ["Using my world (terraweaver): we bought the TV — the Sony Bravia 8, for $1,400, delivery on Saturday."],
]

EXPECT = "pass"

PROBES = [
    ("Using my world (terraweaver): which TV did we end up buying and for how much, and which options "
     "did we drop along the way and why?",
     ["Bravia", "1,400", "C4", "glare"], []),
]

LEVEL = "hard"
