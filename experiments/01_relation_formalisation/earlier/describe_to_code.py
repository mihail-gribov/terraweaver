"""A relation described in words, and the class that comes back.

The sketch next door asks a reader for **data** and writes the code itself, with a reason: the
shape of what is written is ours, and a prompt that emits code ties the question to the shape,
so every change to the code becomes a change to the question. The entity door went the other
way — class description plus the code to fill a thing in — and ran better, so the argument is
not settled by assertion. This is where it gets tried.

What is asked for here is the class body and nothing else: the roles, what may stand at each
end, how many hold at a moment, what follows. `Relation` is above it and provides the rest —
the word for each end, whether it is symmetric, how it reads — because those are *derived*, and
a reader asked for a derived thing gets it wrong in a way nobody notices.

    .venv/bin/python sketch/describe_to_code.py
"""
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import relation as R  # noqa: E402

for env in (ROOT / ".env", Path(os.path.expanduser("~/Projects/ai-safity/.env"))):
    if env.exists():
        for line in env.read_text().splitlines():
            if line.startswith("NEBIUS_API_KEY") and not os.environ.get("NEBIUS_API_KEY"):
                os.environ["NEBIUS_API_KEY"] = line.split("=", 1)[1].strip().strip('"')

SYSTEM = ("You write one Python class describing a kind of link between two things, for a "
          "record that already knows what a link is. You answer with the class and nothing "
          "else — no prose, no fences, no imports.")

ASK = """A fact joins two things, and this record has no word for that kind of link yet. Write
the class for it.

The fact, in the words it came in:
    {said}

The two things it is about:
    {a}  ({a_is})
    {b}  ({b_is})

{held}

The class has these and nothing else. Everything else about a relation is derived from them by
`Relation`, and a derived thing given by hand is wrong in a way nobody notices.

    subject_is     what the SUBJECT is IN THIS LINK — a short noun phrase a thing could be
                   checked against. "capital", "wife", "employee", "born", "part".
    object_is      and the other end: "country", "husband", "employer", "birthplace", "whole".

                   **Not the class, and not the thing.** "Thomas Kyd was born in London" is
                   `born` ↔ `birthplace`, never `person` ↔ `place` — those are the classes,
                   which are said below and would make the word `person_of`, which nobody
                   would write and nobody would look under. "A dog is a kind of mammal" is
                   `kind` ↔ `class`, never `kind` ↔ `mammal` — mammal is the thing at that
                   end this once, not what the end IS.
    subject_class  what may stand at each end, as a tuple of the classes themselves and never
    object_class   of their names — `subject_class = (Place,)`, never `'Place'`. Several where
                   several may: an employer is an organisation or a person. Chosen by
                   what the class IS, not by the sound of its word, and left out when anything
                   may stand there. Left out is the honest answer while one example is all
                   there is: a side named from the first one refuses the second.
    one_object     True when the subject has one object AT A MOMENT. Not one ever — history
    one_subject    always accumulates. Somebody has one employer now and many over a life, so
                   for an employment this is True.
    implies        a tuple of what becomes true in addition, from: "transitive" (A to B and B
                   to C makes A to C), "inherits" (what holds of the object holds of the
                   subject), "identity" (the two are one thing under two names). Often empty.

The classes this record has, and what each is — a name alone does not say whether a country
is a Place here or whether an organisation is a Thing:

{classes}

**Which way it runs is the whole of the direction.** The subject is the one the fact is about:
"Rome is the capital of Italy" makes Rome the subject and `subject_is` "capital".

**Whether the fact is true is not part of this task.** "London is the capital of France" is
described exactly as the true one would be.

Answer with exactly this shape and nothing else — `Relation` above it, the fields as class
attributes, never as arguments to an `__init__`, which would make them settings of one link
instead of what this kind of link is:

    class Anything(Relation):
        \"\"\"one sentence saying what this kind of link is\"\"\"
        subject_is = '...'
        object_is = '...'
        subject_class = (SomeClass,)
        object_class = (SomeClass,)
        one_object = True
        one_subject = False
        implies = ()

**The name is not yours to choose** — call it anything, it is replaced by one built from the
two roles. A name asked for is one more thing to get wrong and one more word that drifts from
what it names.
"""

CASES = [
    ("Rome is the capital of Italy.", "Rome", "Place", "Italy", "Place"),
    ("Masha is Sasha's wife.", "Masha", "Person", "Sasha", "Person"),
    ("Anna has worked at Acme since 2019.", "Anna Weber", "Person", "Acme", "Organization"),
    ("Kreuzberg is part of Berlin.", "Kreuzberg", "Place", "Berlin", "Place"),
    ("Boris and Vera are siblings.", "Boris", "Person", "Vera", "Person"),
    ("Thomas Kyd was born in London.", "Thomas Kyd", "Person", "London", "Place"),
    ("Bombay is Mumbai.", "Bombay", "Place", "Mumbai", "Place"),
    ("A dog is a kind of mammal.", "dog", "Thing", "mammal", "Thing"),
]

# Shown with what each one is, because that is what the choice is made on. Given names only,
# a reader picks by the sound of the word: "Place" says nothing about whether a country is one.
# The classes a world holds, as data. The prompt is written from this and the answer is checked
# against it: a class this record has not got is simply not taken, the way the working world
# does it (`sentences._class_named`). A reader shown a name it cannot check will write a
# reasonable word that is nobody's class, and the record then holds a condition it can test
# against nothing.
CLASSES = {
    "Person": "a human being known to the user",
    "Place": "a city, a district, a country, an address",
    "Organization": "a company, an institution, a team",
    "Thing": "anything that is rather than happens — a book, a sport, a dish",
    "Event": "something that happens at a time — a meeting, a trip leg",
}


# Stand-ins, so the class written by the reader can name them and Python can check it.
AS_CLASSES = {name: type(name, (), {"__doc__": what}) for name, what in CLASSES.items()}


def main() -> int:
    from terraweaver import outside

    words = outside.Nemotron(ttl=90)
    engineer = outside.AsChoices(words)        # a jev stands in; the shape is what is tried
    engineer.say, engineer.json = words.say, words.json
    held = R.Relations()
    for said, a, a_is, b, b_is in CASES:
        # The look comes first, always — and before the roles are read it can only be a closed
        # question over the words already here. Asked the other way round, a reader describes a
        # new relation every time and the vocabulary never converges: one measured run held
        # `ChairpersonOf` beside `DirectorOf` and `CreatedBy` beside `FoundedBy`.
        already = _one_of_these(engineer, said, a, b, held, AS_CLASSES.get(a_is),
                                AS_CLASSES.get(b_is))
        if already is not None:
            print(f"\n=== {said}")
            print(f"    found:  {already.__name__} — {already.reads()}, nothing defined")
            continue
        asked = ASK.format(said=said, a=a, a_is=a_is, b=b, b_is=b_is,
                           held=held.offer(AS_CLASSES.get(a_is), AS_CLASSES.get(b_is)),
                           classes="\n".join(f"    {name:14}{what}"
                                             for name, what in CLASSES.items()))
        code = (engineer.say(SYSTEM, asked) or "").strip()
        code = code.removeprefix("```python").removeprefix("```").removesuffix("```").strip()
        made = _run(code)
        print(f"\n=== {said}")
        for line in code.splitlines():
            print("   ", line)
        if made is None:
            print("    !! did not run")
            continue
        held.add(made)
        print(f"    reads:  {made.reads()}")
        print(f"    words:  {made.word()} ↔ {made.word_back()}"
              f"   symmetric={made.symmetric()}  implies={made.implies}")
    print("\n--- what the world holds now")
    print(held.offer())
    return 0


NONE_OF_THESE = "none of these"


def _one_of_these(engineer, said, a, b, held, subject_class, object_class):
    """Is this one of the words already here? A closed question, and the only cheap one.

    The options are the words this world holds between these two sorts of thing, plus a way
    out. A reader with no way out picks the least bad one, which is how "Amy Winehouse died in
    Camden Town" came back as `born_in`.
    """
    # Narrowed by the classes at the ends, the way the working world narrows it: a fact about a
    # person and a place is worth reading against the words that have run between a person and a
    # place, and `chairperson_of`, which has run between a person and an organisation, is a line
    # this fact can only be distracted by. Narrowed, not hidden — the rest follow, because what
    # a type has run between is what it has seen and not a rule about what it may see.
    def fits(r) -> bool:
        return ((not r.subject_class or subject_class in r.subject_class)
                and (not r.object_class or object_class in r.object_class))

    fitting = [r for r in held.known if fits(r)] + [r for r in held.known if not fits(r)]
    if not fitting:
        return None
    options = {r.word(): f"{r.reads()} — {(r.__doc__ or '').strip()[:70]}" for r in fitting}
    options[NONE_OF_THESE] = ("no word here is this link; it is a kind this record has not "
                              "got yet")
    state = f"{said}\n\nIt is about {a} and {b}."
    scored = engineer.choose(state, f"Which of these is the link between {a} and {b}?", options)
    if not scored:
        return None
    best = max(scored, key=scored.get)
    return next((r for r in fitting if r.word() == best), None)


def _run(code: str):
    """The class the reader wrote, brought to life beside `Relation`."""
    # The classes are in the room, so a name the record has not got is a NameError here rather
    # than a string nobody checks. That is the whole reason to write them as classes.
    room = {"Relation": R.Relation, **AS_CLASSES}
    try:
        exec(code, room)                                   # noqa: S102 - a sketch, on purpose
    except Exception as wrong:                             # noqa: BLE001
        print("    !!", str(wrong)[:120])
        return None
    for value in room.values():
        if isinstance(value, type) and issubclass(value, R.Relation) and value is not R.Relation:
            return value
    return None


if __name__ == "__main__":
    sys.exit(main())
