DESCRIPTION = """Several hops of reading: what the owner wants (recorded as facts about him) →
openings not yet applied to that fit → the companies → people the owner knows there. Pure
reading: the world must not change."""

SETUP = ""

TURNS = [
    "Using my world (terraweaver): which openings I haven't applied to yet actually fit what I want, "
    "and do I know anyone at those companies who could refer me?",
]

EXPECT = """
assert len(Vacancy.find(status="not_applied")) == 21, "vacancy statuses changed"
"""

ANSWER_MUST = ["Research Scientist", "Alan", "Ada"]
ANSWER_MUST_NOT = ["Gameplay Programmer", "Frontend Engineer"]

# Passed in every mode with Opus and Haiku: kept for regression, left out of comparisons.
LEVEL = "basic"
