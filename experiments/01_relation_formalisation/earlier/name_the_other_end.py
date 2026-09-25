"""Given one role and a pair of things, name the other end. The one genuinely open question.

A host says what it knows — "Paris is the capital of France" — and the far end has no name.
Nobody can read it off the record: the world sees two things and one word. Inventing a word by
pattern is what produced `capital_of_of` and "whichever end you start from", which a reader took
for content and answered confidently wrong. So it is asked, once per pair, of the reader whose
kind of question this is.

Open, therefore Nemotron; once per pair, therefore cheap. The closed side — which end is which,
does this thing fit that role — stays with Jev and costs one call per link.
"""
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from terraweaver import outside  # noqa: E402

SYSTEM = ("You name the far end of a relation in a record of facts. A relation joins two things "
          "and each end has a role: in 'Paris is the capital of France', Paris holds the role "
          "'capital' and France holds the role the question is about. You answer with JSON and "
          "nothing else.")

ASK = """Somebody wrote down a fact. One end's role is named, the other is not.

    {a} is {b}'s {role}.

Name what {b} is in this — the role at the far end. A short noun phrase for what a thing must
be to stand there, not a name for this one thing: "the country whose capital it is", not
"France". If the two ends are the same role, say the same word — two siblings are both siblings.

Then say what the relation is, in one sentence, as a reader who has never seen it would need it.

JSON only:
{{"other_role": "...", "relation_is": "...", "same_role_both_ends": true|false}}"""


def name_the_other(reader, a: str, role: str, b: str) -> dict | None:
    return reader.json(SYSTEM, ASK.format(a=a, b=b, role=role))


def main() -> int:
    for where in (Path(__file__).resolve().parents[3] / ".env",
                  Path.home() / "Projects" / "ai-safity" / ".env"):
        if where.exists():
            for line in where.read_text().splitlines():
                if line.startswith("NEBIUS_API_KEY") and not os.environ.get("NEBIUS_API_KEY"):
                    os.environ["NEBIUS_API_KEY"] = line.split("=", 1)[1].strip().strip('"')
    reader = outside.Nemotron()
    cases = [("Paris", "capital", "France"),
             ("Masha", "wife", "Sasha"),
             ("Anna", "mother", "Boris"),
             ("Kreuzberg", "part", "Berlin"),
             ("Boris", "sibling", "Vera"),
             ("Ursula K. Le Guin", "author", "A Wizard of Earthsea"),
             ("Anna", "employee", "Brightwork")]
    for a, role, b in cases:
        said = name_the_other(reader, a, role, b)
        if not said:
            print(f"  {role:10} -> (ничего не вернулось)")
            continue
        print(f"  {role:10} ↔ {str(said.get('other_role')):34} "
              f"{'одна роль' if said.get('same_role_both_ends') else ''}")
        print(f"             {str(said.get('relation_is'))[:86]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
