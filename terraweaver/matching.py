"""Deterministic candidate matching — the detection half of identity resolution.

This module only decides *whether* an incoming entity plausibly refers to something
already in the world. It never decides *which* one: that's the resolution skill's
job, in dialogue with the user.
"""
from difflib import SequenceMatcher

from terraweaver import values
from terraweaver.conditions import Condition
from terraweaver.ontology import Entity

# Exact match on one of these means it's the same entity — no need to ask anyone.
STRONG_KEYS = {
    "Person": ["email", "phone"],
    "Organization": ["website"],
    "Vacancy": ["url"],
}

# Any class holding an `aliases` list has those treated as names too — a nickname the user
# already recorded is exactly how they'll refer to someone.
ALIAS_KEY = "aliases"

# Compared fuzzily to spot "probably the same thing, written differently".
NAME_KEYS = {
    "Person": "full_name",
    "Organization": "name",
    "Project": "name",
    "Place": "name",
    "Vacancy": "title",
    "Event": "title",
    "Idea": "title",
}

# Names compared word by word as well as whole: people and places are called by one part of
# their name ("Annie", "CloudNine"). Titles are not — "Call with Annie (CloudNine)" and
# "CloudNine interview" share a word and are still different events.
PART_MATCH_CLASSES = {"Person", "Organization", "Place"}

# Attributes that tell two entities apart outright when both have them and they differ: two
# events on different days are different events, however alike their titles.
DISTINGUISHING_KEYS = {
    "Event": ["start_time"],
}

CERTAIN = 0.95  # at/above this, treat as the same entity without asking
PART_CEILING = 0.9  # a match on part of a name is never certainty — see similarity()
PLAUSIBLE = 0.6  # between PLAUSIBLE and CERTAIN, it's uncertain — ask the user



def normalize(text: str | None) -> str:
    if not text:
        return ""
    return " ".join(text.strip().lower().split())


def similarity(a: str | None, b: str | None, by_parts: bool = True) -> float:
    """How alike two names are, comparing whole strings and individual parts.

    Parts matter because people are called by one name, not their record: "Anna" against
    "Anna Peterson" scores ~0.47 as whole strings — below any sane threshold — so a lookup
    by the name actually used would come back empty and the agent would report that nobody
    like that exists. Comparing "anna" to the part "anna" gives what it should.
    """
    a_norm, b_norm = normalize(a), normalize(b)
    if not a_norm or not b_norm:
        return 0.0
    whole = SequenceMatcher(None, a_norm, b_norm).ratio()
    if not by_parts:
        return whole
    # Every part of what was asked must find its counterpart: "Pete Ivanson" is not "Anna
    # Peterson" just because "pete" resembles "peterson" — "ivanson" resembles nothing there.
    # One part asked ("Annie") still only needs one part to match.
    b_parts = b_norm.split()
    parts = min(
        max(SequenceMatcher(None, a_part, b_part).ratio() for b_part in b_parts)
        for a_part in a_norm.split()
    )
    # A part matching is enough to consider someone, never enough to be sure of them:
    # "Alan" matches "Alan Turing" perfectly and would still be the wrong Alan if the user
    # knows two. Capping it below CERTAIN keeps that case going to the user.
    return max(whole, min(parts, PART_CEILING))


def known_names(instance, name_key: str | None) -> list:
    """Every name an entity answers to: its own, plus any aliases recorded for it."""
    names = []
    if name_key:
        value = getattr(instance, name_key, None)
        if isinstance(value, str) and value:
            names.append(value)
    aliases = [a for a in (getattr(instance, ALIAS_KEY, None) or []) if isinstance(a, str)]
    names += aliases
    # A person goes by a nickname with their surname too: "Barb Liskov" is Barbara Liskov.
    if name_key == "full_name" and names and len(names[0].split()) > 1:
        surname = names[0].split()[-1]
        names += [f"{a} {surname}" for a in aliases if len(a.split()) == 1]
    return names


def name_similarity(incoming: str, instance, name_key: str | None) -> float:
    by_parts = type(instance).__name__ in PART_MATCH_CLASSES
    return max((similarity(incoming, known, by_parts) for known in known_names(instance, name_key)), default=0.0)


def _distinguished(instance, class_name: str, attrs: dict) -> bool:
    """True when an attribute both sides have proves they are different entities."""
    for key in DISTINGUISHING_KEYS.get(class_name, []):
        incoming, current = attrs.get(key), getattr(instance, key, None)
        if incoming is None or current is None:
            continue
        if hasattr(incoming, "date") and hasattr(current, "date"):
            if incoming.date() != current.date():
                return True
        elif incoming != current:
            return True
    return False


def strong_key_match(existing, class_name: str, attrs: dict) -> bool:
    for key in STRONG_KEYS.get(class_name, []):
        incoming = attrs.get(key)
        current = getattr(existing, key, None)
        if incoming and current and _same_value(existing, key, incoming, current):
            return True
    return False


def score_candidates(existing_instances: list, class_name: str, attrs: dict, filter_others: bool = False) -> list[tuple]:
    """Return [(instance, score)] sorted best-first, keeping only plausible ones.

    `filter_others` distinguishes the two jobs this serves. A *query* means every attribute
    given constrains the result, so `find(Person, organization=acme)` must actually filter by
    employer. *Identifying* an entity is different: attributes beyond the identifying ones are
    new information, not conditions — filtering on them would make "Ada now works at DataWorks"
    fail to find the Ada who is still recorded at TechCorp, and quietly create a second one.
    """
    name_key = NAME_KEYS.get(class_name)
    incoming_name = attrs.get(name_key) if name_key else None
    strong = STRONG_KEYS.get(class_name, [])
    others = {k: v for k, v in attrs.items() if k != name_key and k not in strong}

    scored = []
    for instance in existing_instances:
        if filter_others and not all(_holds(instance, k, v) for k, v in others.items()):
            continue
        if strong_key_match(instance, class_name, attrs):
            scored.append((instance, 1.0))
            continue
        # Only when identifying: in a query, start_time is a condition to satisfy, not a
        # sign of being a different entity.
        if not filter_others and _distinguished(instance, class_name, attrs):
            continue
        if incoming_name:
            score = name_similarity(str(incoming_name), instance, name_key)
            if score >= PLAUSIBLE:
                scored.append((instance, score))
        elif filter_others and others:
            scored.append((instance, 1.0))  # matched every condition asked for
    return sorted(scored, key=lambda pair: -pair[1])


class FindResult(list):
    """Search results split into what actually matches and what merely resembles.

    Iterating gives everything, best first, so it still behaves like a list. The split is
    what matters: `main` holds entities that match for certain, `similar` holds ones that
    only look alike. When `main` is empty, nothing in the world actually matches — and that
    has to be unmissable, because a flat list makes a 0.62 resemblance look like an answer.

    The cut is by threshold alone. A "biggest gap" rule was considered and rejected against
    real data: on every case that mattered the threshold already separated them correctly,
    and the only thing a gap rule added was promoting a lone resemblance to a match — the
    exact guess this design exists to prevent.
    """

    def __init__(self, main: list, similar: list):
        super().__init__(list(main) + list(similar))
        self.main = list(main)
        self.similar = list(similar)

    @property
    def matched(self) -> bool:
        return bool(self.main)

    def __repr__(self):
        if not self.main:
            return f"FindResult(no exact match; {len(self.similar)} similar: {list.__repr__(self.similar)})"
        return f"FindResult(matched={list.__repr__(self.main)}, also similar={list.__repr__(self.similar)})"


def contradictions(instance, attrs: dict) -> list[tuple]:
    """[(attr, existing_value, incoming_value)] where stored data disagrees with new data."""
    found = []
    for attr, incoming in attrs.items():
        current = getattr(instance, attr, None)
        if current is None or incoming is None:
            continue
        if isinstance(current, list) or isinstance(incoming, list):
            continue  # lists accumulate rather than conflict
        if not _same_value(instance, attr, incoming, current):
            found.append((attr, current, incoming))
    return found


def _same_value(instance, attr: str, a, b) -> bool:
    """Equal as the attribute's kind compares them: one phone number however it's written.

    Plain strings keep the looser comparison (case and spacing ignored); an email, phone or
    URL goes through its kind's own normalize.
    """
    found = values.kind_of(type(instance)._spec, attr)
    if found is not None and found[0] is not values.Value and isinstance(a, str) and isinstance(b, str):
        kind, options = found
        return kind.normalize(a, **options) == kind.normalize(b, **options)
    return label(a) == label(b)


def _holds(instance, attr: str, wanted) -> bool:
    """Whether an entity satisfies a query condition on one attribute.

    A list attribute is satisfied by containing the value, not by equalling it. Without
    this, `Event.find(participants=owner)` and `Vacancy.find(stack="Python")` quietly return
    nothing — the worst kind of wrong answer, since an empty result reads as "there are none".
    """
    current = getattr(instance, attr, None)
    if isinstance(wanted, Condition):
        return wanted.test(current)
    if isinstance(current, list) and not isinstance(wanted, list):
        return any(label(item) == label(wanted) for item in current)
    return _same_value(instance, attr, current, wanted)


def label(value) -> str:
    """Comparable label for a value, so two refs to the same entity don't look different.

    Guarded on entities on purpose: a plain str has a .title *method*, so a naive
    attribute check would compare bound-method reprs and call equal strings different.
    """
    if isinstance(value, Entity):
        for attr in ("full_name", "name", "title"):
            label = getattr(value, attr, None)
            if isinstance(label, str):
                return normalize(label)
    return normalize(str(value))
