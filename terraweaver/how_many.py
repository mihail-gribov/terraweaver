"""How many hold at one moment, at each end of a link type: a closed question per end, to the picker.

A type's two sides decide what a later telling does. Limited, it ends the one standing; unlimited,
the two stand side by side and "which now" has two answers. Who said how many was the wrong party
both ways: the host copies the example in front of it, and the world made every word of its own
`many-to-one` — one per *subject* — whatever the word was. So `capital_of` limited the city and
not the country, `author_of` the author and not the work, `chairperson_of` the person and not the
institution. Measured 2026-10-05 on a fresh 250-fact world: of 42 corrections whose gold was held
under a typed link, **26** had the asked end unlimited. Six were answered wrong; the other twenty
were right only because the host read "latest told first" and believed it.

How many a thing can have at once is a question about what the word means — can a country have two
capitals at once, can a person be a citizen of two countries — which is semantic, the world's own
business, and a choice between two options. So it goes to the picker, never to the host
(feedback: the storyteller is not asked about cardinality), and it is asked only where the data has
given the side a chance to matter: one end already holding two under the word. Asked once per side
and kept on the type with the probability, so the ruling and how sure it was can be read back.

Only ever *limits* a side here. Taking a limit away reopens what the world ended
(`_reopen_what_the_world_ended`), which is the larger change, and is not what was measured.
"""
import logging

from terraweaver import ontology, relations, timeutil

log = logging.getLogger(__name__)

# Sure enough that an end holds one at a time to make the word say so. Below it the side stays
# unlimited and the two values keep standing, with the order of tellings said on a read — which is
# the honest outcome for a word that may well hold several. Probed 2026-10-05 on the 18 doubled
# sides of a 250-fact world: capital_of 0.78, chairperson_of 0.70, head_of_state 0.66 by the
# object; the next was works_at at 0.45, and author_of/founder_of at 0.40 (co-authors exist).
ONE = 0.6

SIDES = {"subject": "functional", "object": "inverse_functional"}

ONE_AT_A_TIME = "only one at a time: a new one replaces the one before"
SEVERAL = "several can hold at the same moment"


def _standing(link) -> bool:
    until = getattr(link, "valid_until", None)
    return until is None or timeutil.as_datetime(until) > timeutil.now()


def doubled(world, name: str) -> dict:
    """For each unlimited side: the ends that hold two or more of this type at once, with their links."""
    rel = relations.spec(world.classes[name])
    links = [link for link in world.all(name, limit=None, history=True) if _standing(link)]
    out = {}
    for side, key in SIDES.items():
        if rel.get(key):
            continue
        by_end: dict = {}
        for link in links:
            end = getattr(link, side, None)
            if end is not None and getattr(end, "id", None):
                by_end.setdefault(end.id, (end, []))[1].append(link)
        groups = [(end, held) for end, held in by_end.values()
                  if len({getattr(getattr(l, "object" if side == "subject" else "subject"), "id", None)
                          for l in held}) > 1]
        if groups:
            out[side] = groups
    return out


def _roles(rel: dict) -> tuple[str, str]:
    roles = (rel.get("roles") or [{}])[0]
    word = rel["kind"].replace("_", " ")
    return (roles.get("name") or f"the thing that is '{word}' something",
            roles.get("inverse") or f"the thing something is '{word}'")


def ask(picker, cls, side: str) -> float:
    """The probability that one thing at `side` holds one of these at a time.

    About the word, with no links of it shown. The links that raise the question are the ones
    holding two at once, so shown as examples they argue for "several" by being there: with them,
    capital_of came out 0.65 and author_of 0.35; without, 0.78 and 0.40.
    """
    rel = relations.spec(cls)
    subject_is, object_is = _roles(rel)
    end_is, other_is = (subject_is, object_is) if side == "subject" else (object_is, subject_is)
    state = (f"A kind of link in a record: '{rel['kind'].replace('_', ' ')}' — "
             f"{cls._spec.get('description', '')}\n"
             f"In each link of this kind the subject is {subject_is} and the object is "
             f"{object_is}.")
    question = (f"At any one moment, how many {other_is} can one {end_is} have under "
                f"'{rel['kind'].replace('_', ' ')}'?")
    return float(picker.yes(state, question, ONE_AT_A_TIME, SEVERAL))


def _said_from(link):
    when = getattr(link, "valid_from", None)
    if when is None or getattr(link, "from_is", None) == timeutil.BEFORE or when == timeutil.NEVER:
        return None
    return timeutil.as_datetime(when)


def _told(link):
    born = getattr(link, "created_at", None)
    return timeutil.as_datetime(born) if born is not None else timeutil.NEVER


def hand_over_in_order(world, name: str, end, held: list) -> int:
    """End each telling where the next began, in the order they were told. How many were ended.

    Like with like, as `_which_is_later` decides it for one pair: where every one of them carries a
    date somebody said, the dates order them, and the order of telling breaks a tie; otherwise the
    order of telling alone.
    """
    dated = all(_said_from(link) is not None for link in held)
    ordered = sorted(held, key=lambda l: ((_said_from(l),) if dated else ()) + (_told(l),))
    ended = 0
    for earlier, later in zip(ordered, ordered[1:]):
        start = _said_from(later) if dated else None
        if relations._not_ours_to_end(earlier, start):
            continue
        said = relations._hand_over(world, earlier, end, start, name, at=_told(later))
        if not isinstance(said, relations._HeldBefore):
            ended += 1
    return ended


def settle(world, picker=None, names: list[str] | None = None) -> list[str]:
    """Ask, for every type with a doubled side nobody has ruled on, how many it holds at once.

    Called where nothing waits: at the close of a task and after the offline reading. Returns one
    line per ruling, for whoever is listening.
    """
    picker = picker or getattr(world, "jev", None)
    if picker is None:
        return []
    lines = []
    for name in sorted(names or world.classes):
        cls = world.classes.get(name)
        rel = (cls._spec.get("relation") if cls is not None else None) or {}
        if not rel or rel.get("free") or relations.rule(rel, "symmetric"):
            continue
        try:
            sides = doubled(world, name)
        except Exception:  # noqa: BLE001 - a type whose links cannot be read is not asked about
            log.debug("how_many: %s could not be read", name, exc_info=True)
            continue
        ruled = rel.setdefault("how_many", {})
        for side, groups in sides.items():
            if side in ruled:
                continue
            try:
                one = ask(picker, cls, side)
            except Exception as wrong:  # noqa: BLE001 - an unanswered question leaves the side as it was
                log.info("how_many: %s/%s not asked: %r", name, side, wrong)
                continue
            ruled[side] = {"one": round(one, 3), "by": getattr(picker, "model", type(picker).__name__)}
            if one < ONE:
                ontology._keep_spec(cls._spec)
                continue
            rel[SIDES[side]] = ontology.AT_A_TIME
            ontology._keep_spec(cls._spec)
            ended = sum(hand_over_in_order(world, name, end, held) for end, held in groups)
            lines.append(f"{rel['kind']}: one {side} holds one at a time (sure {one:.2f}); "
                         f"{ended} earlier telling(s) ended where the next began")
    return lines
