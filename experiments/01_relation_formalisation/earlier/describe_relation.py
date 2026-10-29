"""One sentence in, a relation out. The whole of the open question, asked in one place.

The world records what was said and concludes nothing about the relation from it — two tellings
about one couple look like a conjugate pair and may be two relations. So the describing is not
the world's: it is asked of a reader, once per relation, and what comes back is a reading held
in the image, never a fact in the record.

    "Sasha is Masha's husband"  ->  husband <-> wife, one each way, not transitive

Six fields, the ones the argument settled on (`docs/archive/relation-properties.md`). No `kind`: the
word is read off the roles. No `symmetric`: it is `subject_is == object_is`. No `over_time`: a
period belongs to the statement, not to the relation.
"""
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from terraweaver import outside  # noqa: E402

SYSTEM = ("You describe relations in a record of facts. A relation joins two things and each end "
          "has a role. You answer with JSON and nothing else.")

ASK = """A fact was written down:

    {sentence}

Describe the relation it is an instance of.

- **the two roles**: what each end IS, as a short noun phrase a thing can be checked against —
  "a city that serves as a capital", not "Paris". The first role is the one the sentence starts
  from. If both ends hold the same role, say the same word: two siblings are both siblings.
- **how many at a moment**: may the first end have several of the second AT ONE TIME, and the
  second several of the first? A person has one mother and a mother has several children. This
  is about one moment, not a lifetime: somebody has one employer now and many over a life, so
  that is one, not many.
- **transitive**: if A is B's and B is C's, is A C's? A part of a part is part of the whole; a
  mother of a mother is not a mother.

JSON only:
{{"subject_is": "...", "object_is": "...",
  "one_object": true|false, "one_subject": true|false,
  "transitive": true|false, "relation_is": "<one sentence, what this relation is>"}}"""


def describe(reader, sentence: str) -> dict | None:
    return reader.json(SYSTEM, ASK.format(sentence=sentence))


def main() -> int:
    for where in (Path(__file__).resolve().parents[3] / ".env",
                  Path.home() / "Projects" / "ai-safity" / ".env"):
        if where.exists():
            for line in where.read_text().splitlines():
                if line.startswith("NEBIUS_API_KEY") and not os.environ.get("NEBIUS_API_KEY"):
                    os.environ["NEBIUS_API_KEY"] = line.split("=", 1)[1].strip().strip('"')
    reader = outside.Nemotron(ttl=90)
    for sentence in ("Sasha is Masha's husband",
                     "Paris is the capital of France",
                     "Anna is Boris's mother",
                     "Kreuzberg is part of Berlin",
                     "Boris is Vera's sibling",
                     "Anna is an employee of Brightwork",
                     "Ursula K. Le Guin is the author of A Wizard of Earthsea"):
        said = describe(reader, sentence)
        if not said:
            print(f"  {sentence[:46]:48} (ничего не вернулось)")
            continue
        many = ("много" if not said.get("one_object") else "один",
                "много" if not said.get("one_subject") else "один")
        print(f"  {sentence[:46]:48} {str(said.get('subject_is'))[:26]:28} ↔ "
              f"{str(said.get('object_is'))[:26]:28} {many[0]}/{many[1]}"
              f"{'  транзитивно' if said.get('transitive') else ''}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
