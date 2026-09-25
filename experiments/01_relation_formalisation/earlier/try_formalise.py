"""The whole procedure on eight facts, in order, with the world growing as it goes.

Each fact is looked for before it is described, so the seventh is read against what the first
six left behind. That is the thing being tried: not whether one description comes back well,
but whether a vocabulary converges.

    .venv/bin/python sketch/try_formalise.py
"""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import formalise as F  # noqa: E402
import relation as R   # noqa: E402

for env in (ROOT / ".env", Path(os.path.expanduser("~/Projects/ai-safity/.env"))):
    if env.exists():
        for line in env.read_text().splitlines():
            if line.startswith("NEBIUS_API_KEY") and not os.environ.get("NEBIUS_API_KEY"):
                os.environ["NEBIUS_API_KEY"] = line.split("=", 1)[1].strip().strip('"')

CLASSES = {name: type(name, (), {"__doc__": what, "__repr__": lambda s: s.said,
                                "__str__": lambda s: s.said})
           for name, what in {
               "Person": "a human being known to the user",
               "Place": "a city, a district, a country, an address",
               "Organization": "a company, an institution, a team",
               "Thing": "anything that is rather than happens — a book, a sport, a dish",
           }.items()}
F.CLASSES = CLASSES


def a(kind: str, said: str):
    one = CLASSES[kind]()
    one.said = said
    return one


FACTS = [
    ("Rome is the capital of Italy.", a("Place", "Rome"), a("Place", "Italy")),
    ("Paris is the capital of France.", a("Place", "Paris"), a("Place", "France")),
    ("Masha is Sasha's wife.", a("Person", "Masha"), a("Person", "Sasha")),
    ("Anna has worked at Acme since 2019.", a("Person", "Anna"), a("Organization", "Acme")),
    ("Kreuzberg is part of Berlin.", a("Place", "Kreuzberg"), a("Place", "Berlin")),
    ("Boris and Vera are siblings.", a("Person", "Boris"), a("Person", "Vera")),
    ("Thomas Kyd was born in London.", a("Person", "Thomas Kyd"), a("Place", "London")),
    ("A dog is a kind of mammal.", a("Thing", "dog"), a("Thing", "mammal")),
]


def main() -> int:
    from terraweaver import outside
    from describe_to_code import ASK, SYSTEM, CLASSES as SHOWN

    words = outside.Nemotron(ttl=90)
    jev = outside.AsChoices(words)

    def engineer(link):
        held = world.words.offer(type(link.a), type(link.b))
        asked = ASK.format(said=link.words, a=link.a, a_is=type(link.a).__name__,
                           b=link.b, b_is=type(link.b).__name__, held=held,
                           classes="\n".join(f"    {n:14}{w}" for n, w in SHOWN.items()))
        code = (words.say(SYSTEM, asked) or "").strip()
        return code.removeprefix("```python").removeprefix("```").removesuffix("```").strip()

    world = F.World()
    for said, one, other in FACTS:
        F.comes_in(world, one, other, said)
        before = len(world.words.known)
        tally = F.formalise(world, jev, engineer)
        made = world.words.known[-1] if world.words.known else None
        how = ("looked up" if len(world.words.known) == before else "described")
        typed = [l for l in world.links if l.is_a and not l.over][-1:] 
        print(f"\n=== {said}")
        if typed:
            link = typed[0]
            print(f"    {how:10} {link.is_a.__name__}: {link}")
            print(f"               {link.is_a.word()} ↔ {link.is_a.word_back()}"
                  f"   {_ends(link.is_a)}"
                  f"   {'symmetric' if link.is_a.symmetric() else ''} {link.is_a.implies or ''}")
        else:
            print(f"    left untyped: {tally}")

    print("\n--- the words this world ended up with")
    print(world.words.offer())
    left = world.untyped()
    print(f"\nuntyped links left: {len(left)}")
    return 0


def _ends(word) -> str:
    def named(classes):
        return "/".join(c.__name__ for c in (classes or ())) or "any"
    return f"{named(word.subject_class)} → {named(word.object_class)}"


if __name__ == "__main__":
    sys.exit(main())
