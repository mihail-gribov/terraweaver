DESCRIPTION = """A disagreement discovered in passing: the user mentions "Ada from DataWorks", the
world has Ada at TechCorp. The host should notice and check; once the user says she moved, the
employer changes (the old one kept in history) and the passing remark is kept too."""

SETUP = ""

TURNS = [
    "Using my world (terraweaver): I had lunch with Ada from DataWorks today — she says their data team "
    "is hiring. Note that down.",
    "Oh right, she moved from TechCorp to DataWorks last month.",
]

EXPECT = """
adas = [p for p in Person.all(limit=None) if "ada" in p.full_name.lower()]
assert len(adas) == 1, f"expected one Ada, got {len(adas)}"
ada = adas[0]
assert ada.organization.name == "DataWorks", f"Ada is at {ada.organization.name}"
assert any("TechCorp" == getattr(p.value, "name", None) for p in ada.history("organization")), "TechCorp not in her history"
"""

PROBES = [
    ("Using my world (terraweaver): where does Ada Lovelace work now, where did she work before, and "
     "is anyone hiring that I should know about?",
     ["DataWorks", "TechCorp", "hiring"], []),
]

LEVEL = "hard"
