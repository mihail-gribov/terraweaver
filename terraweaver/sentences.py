"""Facts said in words, and typed later.

A host that must choose a relation type before it can say a fact chooses badly: measured over
455 facts, one recorder collected two ideas under `Speaks`, wrote three links backwards because
an argument order had to be right, and answered `over_time` by guess. None of those is a failure
of care — each is a decision it was made to take before it had anything to decide it with.

So there is a second door. The host says the fact in words and names the two things it is about:

    paris.relate(france, "Paris is the capital of France")

That is recorded at once and costs nothing. What relation it is, which end holds which role,
how many may hold at a moment and when it began are read afterwards, at the close of the task,
by the engineer, whose whole attention is that one question — `terraweaver.formalise`. This
module is the door and what the reading needs to know about it; the reading itself is there. A host's run is stopped after ten
seconds and the engineer takes four to twenty, so this cannot happen where the fact is said — and
it does not need to: the words are in the record and reading them is free of any hurry.

What is never read and never guessed: **which two things**. They are handed over as things, not
as names in a sentence, because identity cannot be recovered from words and no later reading
repairs a confusion of two Annas.
"""


def comes_in(world, subject, obj, words: str, task_id: str | None = None):
    """Write the fact down as an untyped link between these two, in the words it came in.

    Nothing waits. The link is there from that moment — joined, findable, countable — and what
    kind of link it is comes later, from a reading with nothing else to attend to. An untyped
    link is a poor link, and a poor link is more than a fact nobody recorded because no type
    could be found for it.

    **Nothing is written down about it besides the link.** There was a side table here, holding
    the words, when they were said, which task said them, and whether anybody had read them yet
    — and every one of those was already in the record: the words are the link's description,
    the time and the run are on the statement, and *unread* is not a mark at all but a state.
    An untyped link that still holds IS a link nobody has read.
    """
    if not (words or "").strip():
        raise ValueError(
            "relate(other, words) needs the fact in words — that is the whole of what it takes. "
            "Not a type, not a role, not which end is which: those are read from the words "
            "afterwards. \"Anna has worked at Brightwork since 2019\" is a fact; \"employment\" "
            "is a type, and choosing one is the thing this call exists to spare you.")
    _about_two(subject, obj, words)
    from terraweaver import ontology

    with ontology.said_in_words():
        return world.relate(subject, obj, "related", description=words.strip())


def _about_two(subject, obj, words: str) -> None:
    """A link is about two things. Said as one, it is probably about the thing, not the joining.

    Not refused — said. The commonest wrong move measured today was a fact about two things
    written as a description of one, and the commonest wrong move in the other direction was an
    account of one thing written onto the link between two. Both passed every check there was.
    The host knows which it meant; the world can only notice that the sentence names one thing
    and not the other, and say so while there is still somebody to say it to.
    """
    from terraweaver import matching, ontology

    said = matching.normalize(words)
    named = [t for t in (subject, obj)
             if matching.normalize(str(t.display_name())) in said
             or any(matching.normalize(w) in said
                    for w in str(t.display_name()).split() if len(w) > 3)]
    if len(named) >= 2:
        return
    if not named:
        ontology.note_hint(
            f"That names neither {subject.display_name()} nor {obj.display_name()}. A link is a "
            f"fact about the two together — say which is what to the other, in the words the "
            f"user used. Recorded as a link either way, and it will be read as one.")
        return
    missing = obj if named[0] is subject else subject
    ontology.note_hint(
        f"That reads as being about {named[0].display_name()} alone — "
        f"{missing.display_name()} is not in it. A link is a fact about the two together: what "
        f"one of them is to the other. If this is an account of {named[0].display_name()} "
        f"rather than of what joins them, it belongs on the thing: "
        f"{named[0].display_name()}.describe(...). Recorded as a link either way.")


def unread(world, limit: int = 100) -> list:
    """Links nobody has read: the untyped ones that still hold.

    Not a list somebody keeps — a question asked of the record. A link with no type is one the
    world has not made sense of yet, and it stops being one the moment it does, because the
    reading ends it and puts a typed link in its place. Kept as a mark instead, the mark and the
    record could disagree, and the one that lies is always the one nobody rebuilds.
    """
    out = []
    for name, cls in world.classes.items():
        if not (cls._spec.get("relation") or {}).get("free"):
            continue
        for link in world.all(name, limit=None):
            if getattr(link, "valid_until", None) is not None:
                continue
            if getattr(link, "subject", None) is None or getattr(link, "object", None) is None:
                continue
            out.append(link)
            if len(out) >= limit:
                return out
    return out


def count(world) -> tuple[int, int]:
    """How many facts were said in words, and how many are still unread."""
    ever = 0
    for name, cls in world.classes.items():
        if (cls._spec.get("relation") or {}).get("free"):
            ever += len(world.all(name, limit=None, history=True))
    return ever, len(unread(world, limit=10_000))


def classes_here(world) -> str:
    """The classes a role may name, so the engineer picks one rather than inventing a word.

    Shown rather than remembered: an engineer told to name a class and not shown which exist will
    write a reasonable word that is nobody's class, and the world then holds a condition it
    cannot check against anything.
    """
    names = sorted(n for n, c in world.classes.items() if not c._spec.get("relation"))
    return "    " + ", ".join(names) + ", or \"any\""


def held(world, subject=None, obj=None) -> str:
    """What the world already holds, so a reading joins rather than invents.

    Shown ends-first when there are two things to hand: a word whose ends have run Person →
    Place is the one worth reading a fact about a person and a place against, and
    `chairperson_of`, which has run Person → Organization, is thirty lines of list that this
    fact can only be distracted by. The narrowing orders, it does not hide — the declared ends
    are evidence and not a promise, and a word whose ends were written down from one example
    would otherwise be unreachable for its second.
    """
    def fits(rel: dict) -> bool:
        if subject is None or obj is None:
            return False
        ends = (rel.get("from") or ["any"], rel.get("to") or ["any"])
        return all(type(end).__name__ in side or "any" in side
                   for end, side in ((subject, ends[0]), (obj, ends[1])))

    near, far = [], []
    for name, cls in sorted(world.classes.items()):
        rel = cls._spec.get("relation")
        if not rel or rel.get("free"):
            continue
        roles = (rel.get("roles") or [{}])[0]
        if not roles.get("name"):
            continue
        line = (f"    {rel['kind']}: {roles['name']} ↔ {roles.get('inverse') or '?'}"
                f" — {cls._spec.get('description', '')[:70]}")
        (near if fits(rel) else far).append(line)
    if not near and not far:
        return "The record holds no relations with named ends yet."
    out = []
    if near:
        out.append("Relations that have run between these two sorts of thing:")
        out += near[:20]
    if far:
        out.append("Relations the record holds between other sorts of thing — one of these may "
                   "still be the word, and its ends are behind the times:")
        out += far[:20]
    return "\n".join(out)
