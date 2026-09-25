"""A fact comes in, and later it is put into the record's own terms. The whole procedure.

Two steps and one rule between them.

    comes_in(a, b, words)
        The fact is a link between these two, carrying the words it was said in, and it is an
        instance of the ROOT class — a Relation about which nothing is known yet. Nothing waits
        on anything: the two are joined from that moment, findable and countable. An untyped
        link is a poor link, and a poor link is more than a fact nobody recorded because no
        type could be found for it.

    formalise(world, jev, engineer)
        Every untyped link that still holds — which is to say, every one nobody has read, since
        that is a state and not a mark somebody keeps.

          1. LOOK.  A closed question over the words this world already holds, narrowed by the
                    classes at the two ends, with "none of these" always among the options.
                    Found → the link becomes that type. Nothing is defined, nothing is named
                    twice. This step is what makes a vocabulary converge; without it one
                    measured run held `ChairpersonOf` beside `DirectorOf`.

          2. DESCRIBE. Only on "none of these", and only then: an open question for the class
                    body. It is registered, and from then on step one finds it.

          3. The link becomes that type, and the untyped one ends where the typed one begins.
                    Nothing is erased: what was said was said.

        Could not → it stays untyped, which is true of it, and the next pass in a bigger world
        may do better. Nothing is ever marked hopeless.

**Which two things is never read.** They are handed over, because identity cannot be recovered
from words and no later reading repairs a confusion of two Annas.

**Whether it is true is nobody's business here.** A record that holds "London is the capital of
France" describes it exactly as it would the truth.
"""
import sys
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import relation as R  # noqa: E402

NONE_OF_THESE = "none of these"


@dataclass
class Link:
    """Two things joined, and what is known about the joining — which may be only the words."""
    a: object
    b: object
    words: str
    is_a: type | None = None          # None while nothing has been read
    over: bool = False                # ended, because a typed one took its place

    def __str__(self) -> str:
        word = self.is_a.word() if self.is_a else f"“{self.words}”"
        return f"{self.a} {word} {self.b}"


@dataclass
class World:
    """As much of a world as this procedure touches: the links, and the words it has for them."""
    links: list = field(default_factory=list)
    words: R.Relations = field(default_factory=R.Relations)

    def untyped(self) -> list:
        """Every link nobody has read. Not a list kept — a question asked of what is there."""
        return [one for one in self.links if one.is_a is None and not one.over]


def comes_in(world: World, a, b, words: str) -> Link:
    """The fact, joined and recorded, in the words it came in. Nothing waits."""
    if not (words or "").strip():
        raise ValueError(
            "a link needs the fact in words — that is the whole of what it takes. Not a type, "
            "not a role, not which end is which: those are read afterwards.")
    link = Link(a, b, words.strip())
    world.links.append(link)
    return link


def formalise(world: World, jev, engineer, say=print) -> dict:
    """Give a type to the links nobody has read. Look first, describe only if nothing fits."""
    tally = {"read": 0, "joined": 0, "defined": 0, "left": 0}
    for link in world.untyped():
        found = _look(world, link, jev)
        if found is None:
            found = _describe(world, link, engineer, say)
            if found is not None:
                tally["defined"] += 1
        else:
            tally["joined"] += 1
        if found is None:
            tally["left"] += 1
            continue
        tally["read"] += 1
        typed = Link(link.a, link.b, link.words, is_a=found)
        world.links.append(typed)
        link.over = True                  # ended where the typed one begins; not erased
    return tally


def _look(world: World, link: Link, jev):
    """Is this one of the words already here? The options are narrowed, never hidden."""
    a_is, b_is = _class_of(link.a), _class_of(link.b)

    def fits(word) -> bool:
        return ((not word.subject_class or a_is in word.subject_class)
                and (not word.object_class or b_is in word.object_class))

    known = ([w for w in world.words.known if fits(w)]
             + [w for w in world.words.known if not fits(w)])
    if not known:
        return None
    options = {w.word(): f"{w.reads()} — {(w.__doc__ or '').strip()[:70]}" for w in known}
    options[NONE_OF_THESE] = "no word here is this link; it is a kind this record has not got"
    scored = jev.choose(f"{link.words}\n\nIt is about {link.a} and {link.b}.",
                        f"Which of these is the link between {link.a} and {link.b}?", options)
    if not scored:
        return None
    best = max(scored, key=scored.get)
    return next((w for w in known if w.word() == best), None)


def _describe(world: World, link: Link, engineer, say):
    """Nothing fitted: ask for the class, run it, and keep it. From here the look finds it."""
    code = engineer(link)
    if not code:
        return None
    room = {"Relation": R.Relation, **_classes_here()}
    try:
        exec(code, room)                                   # noqa: S102 - a sketch, on purpose
    except Exception as wrong:                             # noqa: BLE001
        say(f"    !! {str(wrong)[:110]}")
        return None
    made = next((v for v in room.values()
                 if isinstance(v, type) and issubclass(v, R.Relation) and v is not R.Relation),
                None)
    if made is None:
        return None
    made.__name__ = R._class_name(made.subject_is, made.object_is)
    return world.words.add(made)


def _class_of(thing) -> type:
    return type(thing)


def _classes_here() -> dict:
    """Whatever the caller put in `CLASSES` — the sketch's stand-in for a world's classes."""
    return dict(getattr(sys.modules[__name__], "CLASSES", {}))
