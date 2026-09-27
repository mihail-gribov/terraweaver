"""The lines run, through the door a host's code runs through, and the record says what landed.

Not a second interpreter, and that is the point of asking for code at all: what the engineer may say
is what a host may say, the sandbox is the same sandbox, and every refusal the world makes of a host
it makes of the engineer. The two things are bound before the code runs, so the engineer never has to
name them — which two things a fact is about is handed over, never read out of an answer, because
identity recovered from words is the one mistake no later pass repairs. The writes are the world's
own, the lowest standing there is.
"""
from terraweaver import ontology, timeutil
from terraweaver.formalise.look import words_for


def run(runtime, code: str, **bound) -> dict:
    """Run the lines with these names bound, as the world's own writes. What `runtime.run` says back."""
    from terraweaver.runtime import THE_WORLDS_OWN

    session = runtime.session(THE_WORLDS_OWN)
    session.namespace.update(bound)
    with ontology.stating("world"):
        return runtime.run(code, THE_WORLDS_OWN)


def typed_between(world, subject, obj) -> list:
    """Links of a real type joining these two now, either way round.

    How the writing is known to have worked, and it is read from the record rather than from what
    the code appeared to do: a line that ran without an error may still have written nothing.
    """
    out = []
    for name, _, _ in words_for(world):
        for link in world.all(name, limit=None):
            if getattr(link, "valid_until", None) is not None:
                continue
            ends = {getattr(getattr(link, "subject", None), "id", None),
                    getattr(getattr(link, "object", None), "id", None)}
            if ends == {subject.id, obj.id}:
                out.append(link)
    return out


def end_the_bare_one(world, link) -> None:
    """The bare link is replaced by a typed one: end it, do not erase it.

    What was said is not unsaid. The bare link held the host's own words and the moment they were
    said; it stops holding where the typed one begins, and anybody asking what this was before it was
    typed still has it.
    """
    with ontology.trusted_writes(), ontology.stating("world"):
        link.valid_until = timeutil.now()
        world.save(link)


def take_back(world, links: list) -> None:
    """Unmake what the check would not have: the world's own links, before anybody has read them.

    `check.py` argued the other way — judge before the lines run, because deleting is the expensive
    direction — and the argument holds for a write somebody else made and is holding an instance of.
    These are not that. They were written a moment ago under `stating("world")`, by the reading, for
    the reading, and `Relation.retract` exists for exactly this: what the world concluded and no
    longer believes. What the host said is not touched — the bare link and its words stand, and the
    next go reads them again.
    """
    why = "the words do not bear it out"
    for link in links:
        try:
            statements = world.facts.about(link.id)
            # `Relation.retract` guards on `is_conclusion`, which is about a basis and not about
            # who wrote it, so it refuses these: the reading's writes go through the ordinary door
            # and carry no basis. What marks them is `source`, set by `stating("world")`. A link
            # with a statement from anybody else is left exactly as it is.
            if not statements or any(one.source != "world" for one in statements):
                continue
            with ontology.stating("world"):
                for one in statements:
                    world.facts.retract(one.id, by=why)
                world.store.forget(link.id)
        except Exception:  # noqa: BLE001 - a reading is not lost because the unmaking failed
            continue
