"""One door for asking, with the simple asks as its special cases.

Every way of narrowing this world exists on its own: attributes through `find`, links through
the relations, tags through the periods, meaning through the index. Two things were missing, and
they are the same thing twice.

**A real question uses several of them at once.** "People at Acme tagged berlin whose notes read
like battery work, as of June" is one question; asking it three ways and intersecting by hand
costs the host runs and reads worse than the question does.

**A real question is often about things of different kinds.** Everything to do with the move is a
flat, a landlord, a moving firm, a school and four dates — a Place, two Organizations, a Person
and some Events. Nothing here could ask that, because every way of asking started by naming a
class. So the class is optional, and leaving it out means "whatever kind of thing it is":

    world.where(tagged="move")                      — the move, all of it, whatever kind
    world.where(mentions="lisbon flat")             — those words, exactly, in anything said
    world.where(related=("participation", project))  — everything hanging off one thing
    world.where(Person, organization=acme,           — attributes, as in find()
                related=("membership", acme),        — a link, in either direction
                tagged="berlin", like="cell chemistry",
                at=date(2026, 6, 1), limit=20)

So this is not a query language. It is the same calls, gathered into one, with the same words
they already use — and the plain ones are this one with a single condition: searching by tag is
`where(tagged=...)`, searching by meaning is `where(like=...)`.

Two ways of searching words, on purpose. `mentions=` is literal: every word must appear, case
ignored, nothing stemmed, and the same question always gives the same answer. `like=` is by
meaning, and is a judgement — it finds what a different wording says. Use the first when you
know the word the user used, the second when you don't.

Everything given narrows; nothing widens. `like` also decides the order, because closeness is the
only thing here that has a degree; without it the order is the world's usual one, most recently
worked with first, one kind of thing after another.

One difference from asking about a single entity: `related=` is read strictly here. Asked about
one thing, the world answers from whichever end has the link and says it corrected you; asked to
pick out many, it does not — "everyone with a membership" that quietly included the employers
would leave the direction meaning nothing.
"""
from datetime import datetime

DEFAULT_LIMIT = 50


def where(world, cls=None, *, related=None, tagged=None, tagged_all=None, mentions=None,
          like=None, how: str = "all", closeness: float = 0.3, at=None, any_time: bool = False,
          limit: int | None = DEFAULT_LIMIT, **attributes) -> list:
    """Everything that answers all of it. Without a class: of any kind. See the module docstring."""
    from terraweaver import relations

    wanted_tags = ([tagged] if tagged else []) + list(tagged_all or [])
    found = []
    for class_name in _classes(world, cls, attributes, wanted_tags):
        found += _by_attributes(world, class_name, attributes, any_time)

    if wanted_tags:
        found = [e for e in found if _carries(world, e, wanted_tags, at, any_time)]

    if mentions:
        from terraweaver import texts

        hits = texts.mentioning(world, mentions, at=at, any_time=any_time)
        words = [w.lower() for w in str(mentions).split()]
        found = [e for e in found
                 if (getattr(e, "subject_id", None) or e.id) in hits
                 or all(w in e.display_name().lower() for w in words)]

    if related is not None:
        kind, other = related if isinstance(related, (tuple, list)) else (related, None)
        keep = []
        for entity in found:
            links = relations.relations_of(world, entity, kind, any_time, strict=True)
            if links and (other is None or any(relations.same(link.other(entity), other)
                                               for link in links)):
                keep.append(entity)
        found = keep

    if like:
        # Scored on all of this one's texts: the closest decides and the rest back it up.
        # Measured on six questions against six people — by the closest text alone the gap
        # between the right answer and the rest is +0.21 but nine strangers come in over 0.5;
        # by the average of everything said it is +0.14 and fourteen do; this way it is +0.17
        # and five do, with the right answer first in all six either way. how="best" and
        # how="mean" are still there. Short texts are why this matters: a one-word text scores
        # 0.36 against things it has nothing to do with, where a ten-word one scores 0.28, so
        # letting a single tag carry an entity into an answer is exactly the wrong bet.
        order, matched = {}, {}
        for entity, score, said in world.meanings.entities(world, like, limit=200, how=how,
                                                           any_time=any_time):
            order[entity.id] = score
            matched[entity.id] = said
        found = [e for e in found if order.get(e.id, 0.0) >= closeness]
        found.sort(key=lambda e: order.get(e.id, 0.0), reverse=True)
        for entity in found:  # so an answer can say which sentence it matched on
            entity.__dict__["_matched"] = (matched.get(entity.id), order.get(entity.id))

    return found[:limit] if limit else found


def _classes(world, cls, attributes: dict, wanted_tags: list) -> list[str]:
    """Which classes can possibly answer — all of them, unless one was named.

    A class without the attributes asked for can hold nothing that matches, and one without tags
    can hold nothing tagged, so sweeping them is only slower, never different.
    """
    if cls is not None:
        return [cls if isinstance(cls, str) else cls.__name__]
    needed = set(attributes) | ({"tags"} if wanted_tags else set())
    out = []
    for class_name, klass in world.classes.items():
        has = {attribute["name"] for attribute in klass._spec["attributes"]}
        if needed <= has:
            out.append(class_name)
    return out


def _by_attributes(world, class_name: str, attributes: dict, any_time: bool) -> list:
    """The starting set: everything of the class, or what the attributes pick out."""
    if not attributes:
        return world.all(class_name, limit=None, any_time=any_time)
    result = world.find(class_name, history=any_time, **attributes)
    if hasattr(result, "main") and result.main is not None:
        return [result.main] if not isinstance(result.main, list) else list(result.main)
    return list(getattr(result, "candidates", []) or [])


def _carries(world, entity, wanted: list, at, any_time: bool) -> bool:
    """Read the same way the tags themselves are read, so one door and two give one answer."""
    from terraweaver import tags as tagging

    held = tagging.ever(world, entity) if any_time else (
        tagging.holding(world, entity, at) or tagging.tags_of(entity))
    holding = {tagging.canonical(tag) for tag in held}
    return all(tagging.canonical(tag) in holding for tag in wanted)
