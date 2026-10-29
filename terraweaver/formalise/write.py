"""The lines run, through the door a host's code runs through, and the record says what landed.

Not a second interpreter, and that is the point of asking for code at all: what the engineer may say
is what a host may say, the sandbox is the same sandbox, and every refusal the world makes of a host
it makes of the engineer. The two things are bound before the code runs, so the engineer never has to
name them — which two things a fact is about is handed over, never read out of an answer, because
identity recovered from words is the one mistake no later pass repairs. The writes are the world's
own, the lowest standing there is.
"""
from terraweaver import ontology, timeutil
from terraweaver.formalise import check
from terraweaver.formalise.look import words_for


def run(runtime, code: str, **bound) -> dict:
    """Run the lines with these names bound, as the world's own writes. What `runtime.run` says back."""
    from terraweaver.runtime import THE_WORLDS_OWN

    session = runtime.session(THE_WORLDS_OWN)
    session.namespace.update(bound)
    with ontology.stating("world"):
        return runtime.run(code, THE_WORLDS_OWN)


def typed_between(world, subject, obj, apart_from=()) -> list:
    """Links of a real type joining these two now, either way round, minus the ones already there.

    How the writing is known to have worked, and it is read from the record rather than from what
    the code appeared to do: a line that ran without an error may still have written nothing.

    `apart_from` is what was standing before this reading started, and it is not optional in
    practice. Without it this answers "what joins these two", which is not the question asked:
    2026-09-30, docs/archive/code-review-2026-09-30.md 3.4.2 — 7 of 402 end-pairs in a 455-fact world
    carry two types (`CapitalOf` beside `MayorOf`, `AuthorOf` beside `FamousFor`), and for those
    a link about another fact entirely was counted as this reading's work, judged against words
    it has nothing to do with, and the bare link holding the real words was ended as done.
    """
    apart = set(apart_from or ())
    out = []
    for name, _, _ in words_for(world):
        for link in world.all(name, limit=None):
            if getattr(link, "valid_until", None) is not None:
                continue
            if link.id in apart:
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


def settle_by_verdict(world, links: list, about: dict) -> list[str]:
    """Act on the decision model's answer, once there are no goes left.

    Three goes and the check still refuses: until now that threw the reading away — 12 readings of
    355 ended "not borne out by the words" and 71 "gave up", every one of them a link the engineer
    had written and the record then lost. And in each of them the decision model had already said
    *what* was wrong, with a confidence behind it. Its answer is the last word, so it is acted on
    rather than discarded:

        backwards on the link        the ends go round — it is the one thing the words did settle
        not in it, an attribute      that attribute comes off and the link stays
        not in it, the link          left alone: which two things this is about is the host's to
                                     say, and every false alarm measured came back in this shape

    What is not done is asking again. The engineer has had its three goes; this is the decision
    model's turn to be believed — about the word, the direction and what is written on the link, and
    not about whether the two things belong together, which nobody here asked it.
    """
    from terraweaver import ontology

    held = {link.id: link for link in links}
    did = []
    for one in about.get("claims", []):
        verdict, link = one.get("verdict"), held.get(one.get("of"))
        if link is None or verdict in (None, "says_so") or one.get("sure", 0) < check.SURE_ENOUGH:
            continue
        what = (one.get("claim") or {}).get("what")
        try:
            with ontology.trusted_writes(), ontology.stating("world"):
                if verdict == check.BACKWARDS and what == "link":
                    link.subject, link.object = link.object, link.subject
                    world.save(link)
                    did.append(f"{link.display_name()} — put round, as the words say")
                elif what != "link":
                    name = (one.get("claim") or {}).get("name")
                    if name:
                        setattr(link, name, None)
                        world.save(link)
                        did.append(f"{link.display_name()} — {name} dropped, the words do not give it")
                else:
                    did.append(f"{link.display_name()} — kept: the words do not bear out the word, "
                               f"but which two things this is about was not the picker's to judge")
        except Exception as wrong:  # noqa: BLE001 - a reading is not lost because the settling failed
            did.append(f"could not settle: {type(wrong).__name__}")
    return did
