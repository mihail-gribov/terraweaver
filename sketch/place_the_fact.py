"""Give the reader two things, the sentence, and what the world already holds. Get back a place.

The last construction taken off the host. It no longer names the role, nor orders the arguments,
nor chooses the type — it says the fact and which two things it is about, and the reader does
the rest:

    pick an existing relation, or describe a new one
    say which of the two things holds which role

That last part is what removes direction as a thing that can be got wrong. Nobody orders the
arguments, so nobody orders them backwards — three links went in backwards in a measured run
because an argument order had to be right, and `Great Britain capital of London` was the world
asserting it.

Shown what is already held, the reader joins rather than invents. Unshown, one recorder wrote
`ChairpersonOf` beside `DirectorOf` and `CreatedBy` beside `FoundedBy` — two words for one idea,
and a world holding both answers for neither.
"""
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from terraweaver import outside  # noqa: E402

SYSTEM = ("You place a fact in a record of relations. A relation joins two things and each end "
          "has a role. You answer with JSON and nothing else.")

ASK = """A fact was written down about two things:

    the fact:  {said}
    the two:   {a}   and   {b}

{held}

**Whether the fact is TRUE is not asked and must not affect anything you say.** This record
holds what somebody said, including things that contradict what is generally known: "London is
the capital of France" is a fact somebody stated, and it is placed exactly as "Paris is the
capital of France" would be — same relation, same roles, London in the capital's role. A record
that only took facts it agreed with would be an encyclopaedia, and this is a record of what was
said. What you decide is the **shape**: which relation, and which end holds which role.

Place it. Either it belongs to a relation the record already holds, or it needs a new one.

- If one of the held relations is this same idea, give its name in `use` and nothing else but
  the two assignments. Joining what is there is better than a second word for one idea.
- Otherwise describe the relation: what each end IS, as a short noun phrase a thing can be
  checked against — "a city that serves as a capital", not "Paris". If both ends hold the same
  role, say the same word. Say how many may hold AT ONE MOMENT on each side: somebody has one
  employer now and many over a life, so that is one. Say whether it is transitive: a part of a
  part is part of the whole, a mother of a mother is not a mother.

Then, either way, say **which of the two things holds which role** — that is the whole of the
direction, and it is yours to decide, not the writer's.

Last: if the sentence says **when**, say when. "since 2015", "from March to June", "until she
left" — a date the writer gave, in the form they gave it. If it says nothing about when, leave
both empty and do not guess: a date nobody said is worse than no date, because the record
cannot tell an invented one from one somebody knew.

JSON only:
{{"use": "<a held relation's name, or null>",
  "subject_is": "...", "object_is": "...",
  "one_object": true|false, "one_subject": true|false, "transitive": true|false,
  "relation_is": "<one sentence>",
  "subject": "<whichever of the two holds the first role>",
  "object": "<the other>",
  "starts": "<when it began, as the sentence said it, or null>",
  "until": "<when it ended, or null>"}}"""


def place(reader, said: str, a: str, b: str, held: str = "") -> dict | None:
    return reader.json(SYSTEM, ASK.format(
        said=said, a=a, b=b,
        held=held or "The record holds no relations yet."))


def main() -> int:
    for where in (Path(__file__).resolve().parent.parent / ".env",
                  Path.home() / "Projects" / "ai-safity" / ".env"):
        if where.exists():
            for line in where.read_text().splitlines():
                if line.startswith("NEBIUS_API_KEY") and not os.environ.get("NEBIUS_API_KEY"):
                    os.environ["NEBIUS_API_KEY"] = line.split("=", 1)[1].strip().strip('"')
    reader = outside.Nemotron(ttl=120)

    held = ""
    cases = [("Paris is the capital of France", "Paris", "France"),
             # said the other way round on purpose: the roles must not follow the order
             ("Germany's capital is Berlin", "Germany", "Berlin"),
             ("Masha is Sasha's wife", "Masha", "Sasha"),
             ("Kreuzberg is part of Berlin", "Kreuzberg", "Berlin"),
             ("Anna works at Brightwork", "Anna", "Brightwork")]
    known = []
    for said, a, b in cases:
        got = place(reader, said, a, b, held)
        if not got:
            print(f"  {said[:34]:36} (ничего не вернулось)"); continue
        if got.get("use"):
            print(f"  {said[:34]:36} -> взял {got['use']:14} "
                  f"субъект={got.get('subject')} объект={got.get('object')}")
        else:
            name = "".join(w[:1].upper() + w[1:]
                           for w in str(got['subject_is']).split()[-1:]) + "Of"
            known.append((name, got))
            held = ("Relations the record already holds:\n" + "\n".join(
                f"    {n}: {g['subject_is']} ↔ {g['object_is']} — {g.get('relation_is','')}"
                for n, g in known))
            print(f"  {said[:34]:36} -> завёл {name:13} "
                  f"{got['subject_is']} ↔ {got['object_is']}")
            print(f"  {'':36}    субъект={got.get('subject')} объект={got.get('object')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
