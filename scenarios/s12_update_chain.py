DESCRIPTION = """A value that changes in steps, across conversations, with a tentative step in the
middle: promoted → "only official next month" → (later) official, and a team change. The final
state is the new title, with the old one still known."""

SETUP = """
Person.new(full_name="Priya Shah", email="priya@example.com", job_title="Data Engineer",
           organization=Organization.get(name="GreenGrid"))
"""

CONVERSATIONS = [
    [
        "Using my world (terraweaver): Priya Shah just got promoted to Senior Data Engineer.",
        "Actually, hold on — HR says it only becomes official next month. Nothing is final yet.",
    ],
    [
        "Using my world (terraweaver): Priya's promotion to Senior Data Engineer is official now. She "
        "also moved to the Grid Analytics team.",
    ],
]

EXPECT = """
priya = Person.get(email="priya@example.com")
assert priya.job_title == "Senior Data Engineer", f"title is {priya.job_title}"
assert priya.organization.name == "GreenGrid", "employer changed"
"""

PROBES = [
    ("Using my world (terraweaver): what's Priya Shah's title now, what was it before, and which team is she on?",
     ["Senior Data Engineer", "Data Engineer", "Grid Analytics"], []),
]

LEVEL = "hard"
