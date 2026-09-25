"""When the look turns up a candidate, ask whether it is the same idea. A closed question.

The division the whole evening arrived at: a cheap local comparison **offers** a candidate, and
a reader with named options **decides**. Substring matching is a fine generator and a terrible
judge — `Berkeley` inside `University of California, Berkeley` cost a measured world twelve
names — so it is kept for the first job and taken off the second.

One call, only when there is a candidate. Nothing is merged on the answer: what comes back is
said to whoever is defining the relation, because whether two words are one idea depends on
what the person meant, which the host has and the world does not.
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from terraweaver import outside  # noqa: E402

SAME = ("one idea under two words — a record holding both would answer for neither, and the "
        "links written under one belong with the links written under the other")
APART = ("two ideas that happen to share a word — a record needs both, and merging them would "
         "lose the question one of them answers")
ENDS = ("these are the two ENDS of one relation, not two relations — one names what the near "
        "end is and the other what the far end is")


def one_idea(reader, asking: str, asking_of: str, holding: str, holding_of: str,
             what_it_is: str = "") -> dict:
    """Is the role somebody is about to define the same idea as one the world already holds?"""
    state = (f"A record of facts holds relations. Each joins two things, and each end has a "
             f"role — in 'Paris is the capital of France', 'capital' and 'country' are the two "
             f"roles of one relation.\n\n"
             f"    already held:   {holding} ↔ {holding_of}"
             + (f"   ({what_it_is})" if what_it_is else "") + "\n"
             f"    about to define: {asking} ↔ {asking_of or '(the far end unnamed)'}\n\n"
             f"Whether any particular fact is true is not asked.")
    got = reader.ask(state, {"q": {"type": "choice",
          "instructions": f"Is {asking!r} the same idea as {holding!r}, a different one, or the "
                          f"other end of the same relation?",
          "criteria": {"same": SAME, "apart": APART, "two_ends": ENDS}}})["q"]
    return {"choice": got["choice"], "probabilities": got.get("probabilities", {})}


def main() -> int:
    for where in (Path(__file__).resolve().parents[3] / ".env",
                  Path.home() / "Projects" / "ai-safity" / ".env"):
        if where.exists():
            for line in where.read_text().splitlines():
                if line.startswith("TYPESAFE_API_KEY") and not os.environ.get("TYPESAFE_API_KEY"):
                    os.environ["TYPESAFE_API_KEY"] = line.split("=", 1)[1].strip().strip('"')
    reader = outside.Jev()
    cases = [
        ("chairperson", "organization", "chair", "organization", "the person who chairs a body", "same"),
        ("chairman", "organization", "chair", "organization", "the person who chairs a body", "same"),
        ("director", "organization", "chair", "organization", "the person who chairs a body", "apart"),
        ("whole", "", "part", "whole", "one thing is a part of another", "two_ends"),
        ("citizen", "country", "capital", "country", "a city that is a country's seat", "apart"),
        ("founder", "organization", "creator", "work", "who made a thing", "apart"),
        ("spouse", "spouse", "husband", "wife", "a married couple", "same"),
    ]
    right = 0
    for asking, asking_of, holding, holding_of, what, want in cases:
        said = one_idea(reader, asking, asking_of, holding, holding_of, what)
        got = said["choice"]
        right += got == want
        p = said["probabilities"].get(got, 0.0)
        print(f"{'✓' if got == want else '✗'} {asking:12} vs {holding:12} "
              f"ждали {want:9} сказал {got:9} p={p:.2f}")
    print(f"\n{right}/{len(cases)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
