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


# A title is how a name is said, not part of it: "Dr. Rao" is Arun Rao, and a lookup that
# insists on the word "dr" finds nobody.
TITLES = {"dr", "mr", "mrs", "ms", "mx", "miss", "prof", "professor", "sir", "madam", "rev", "fr"}


def drop_titles(text: str) -> str:
    kept = [part for part in text.split() if part.strip(".,") not in TITLES]
    return " ".join(kept) if kept else text


def similarity(a: str | None, b: str | None, by_parts: bool = True) -> float:
    """How alike two names are, comparing whole strings and individual parts.

    Parts matter because people are called by one name, not their record: "Anna" against
    "Anna Peterson" scores ~0.47 as whole strings — below any sane threshold — so a lookup
    by the name actually used would come back empty and the agent would report that nobody
    like that exists. Comparing "anna" to the part "anna" gives what it should.
    """
    a_norm, b_norm = drop_titles(normalize(a)), drop_titles(normalize(b))
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
    # Both names in several parts: judge by the parts. The whole strings of "Kevin Liu" and
    # "Darren Liu" are 60% alike through the shared surname — siblings, not one person.
    if len(a_norm.split()) > 1 and len(b_parts) > 1:
        return whole if whole >= CERTAIN else min(parts, PART_CEILING)
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


class Matches(list):
    """The matches themselves. A list — but `result.matches.full_name` is the shape hosts reach
    for, and a bare 'list has no attribute' tells them nothing.

    With exactly one match there is nothing to choose between, so the attribute is read from it
    and the reading is announced: one match, one answer, the caveat said. With none or several
    it refuses and says where to look — reading "the" name of three people would be a guess, and
    reading one out of nothing would be an invention. Discarding the run over a shape the world
    could resolve was the commonest way a host lost its work (four of eight failing scenarios in
    one pool)."""

    def __init__(self, items, which: str):
        super().__init__(items)
        self._which = which

    def __getattr__(self, name: str):
        if name.startswith("_"):
            raise AttributeError(name)
        if len(self) == 1 and hasattr(self[0], name):
            from terraweaver import ontology

            ontology.note_assumed(
                f"result.{name} read from the one match ({self[0].display_name()}) — "
                f"a search result is a list, and result.{self._which}[0] is that one")
            return getattr(self[0], name)
        from terraweaver import ontology

        # `main` was this list's name until hosts kept reading it as "the main one" — the word
        # is gone, and anyone who learned it is sent to the one that replaced it.
        near = ontology.did_you_mean(name, ["matches", "similar", "matched"],
                                     {"main": "matches", "result": "matches", "all": "matches"})
        if near:   # a word for the result itself, read off the wrong part of it
            raise AttributeError(
                f"a list of matches has no {name!r} — did you mean result.{near}? "
                f"result.matches are the ones that match, result.similar the ones that resemble.")
        where = (f"one of them ({len(self)} here), e.g. result.{self._which}[0].{name}" if self
                 else "there are none — say so rather than filling the gap")
        raise AttributeError(f"these are the matches, not one entity: no {name!r} on a list. Use {where}.")


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

    def __init__(self, matches: list, similar: list, class_name: str | None = None):
        super().__init__(list(matches) + list(similar))
        self._class_name = class_name or (type(matches[0]).__name__ if matches else
                                          type(similar[0]).__name__ if similar else "")
        self.matches = Matches(matches, "matches")
        self.similar = Matches(similar, "similar")

    @property
    def matched(self) -> bool:
        return bool(self.matches)

    def __getattr__(self, name: str):
        # `Person.find(...).full_name` — the host took the search for the person it found. A bare
        # AttributeError on 'list' says nothing; this says which entity it meant to reach.
        # (A property would be unreachable here: one that raises AttributeError falls through
        # to __getattr__, so the rule for `main` lives in it rather than beside it.)
        if name.startswith("_"):
            raise AttributeError(name)
        if name == "main":
            return self._the_one()
        if len(self.matches) == 1:
            return getattr(self.matches, name)   # one match, one answer, the caveat said there
        if self.matches:
            where = f"one of result.matches ({len(self.matches)} matched), e.g. result.matches[0].{name}"
        elif self.similar:
            where = (f"nothing matched; {len(self.similar)} merely resemble it (result.similar) — "
                     f"say so rather than serving the closest one")
        else:
            where = "nothing in the world matches — say so, don't fill the gap"
        raise AttributeError(f"a search result has no {name!r}: it's the matches, not the entity. Use {where}.")

    def _the_one(self):
        """The one this search found — when the search found exactly one.

        `result.main` is what a host reaches for, and it should be right: one match and nothing
        to choose between is an answer. Where there is a choice the world does not make it; it
        says what to look at and what would narrow it, because picking the first of several is
        the guess this design exists to prevent.
        """
        if len(self.matches) == 1:
            return self.matches[0]
        if self.matches:
            raise AttributeError(
                f"the search wasn't unambiguous: {len(self.matches)} of them match. Look with "
                f"result.matches and narrow what you asked — one more attribute usually settles "
                f"it (email, organization, a date). result.matches[0] is right only if you have "
                f"a reason to prefer it.")
        what = self._class_name or "one"
        made = f"{what}.new(...)" if self._class_name else "Class.new(...)"
        if self.similar:
            raise AttributeError(
                f"nothing matched, though {len(self.similar)} resemble it — they are in "
                f"result.similar, look before deciding. Three ways on, and they are different "
                f"answers: one of those is the one meant (name it, or ask the user which), or "
                f"what you asked needs changing (another attribute, a fuller name), or this "
                f"{what} is not in the world yet and the user is telling you about it now — "
                f"then record it with {made}. Serving the closest resemblance is none of them.")
        raise AttributeError(
            f"nothing in the world matches that. Either what you asked needs changing — a "
            f"fuller name, another attribute, any_time=True for something ended — or there is "
            f"no such {what} here yet: if the user is telling you about it, record it with "
            f"{made}; if they are asking about it, say it isn't there rather than filling the "
            f"gap. result.matched is False for exactly this.")

    def __repr__(self):
        if not self.matches:
            return f"FindResult(no exact match; {len(self.similar)} similar: {list.__repr__(self.similar)})"
        return f"FindResult(matched={list.__repr__(self.matches)}, also similar={list.__repr__(self.similar)})"


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
    # Two entities are the same only if they are the same record — not if they share a name.
    if isinstance(a, Entity) and isinstance(b, Entity):
        return a is b or (a.id is not None and a.id == b.id)
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
        return any(_same_value(instance, attr, item, wanted) for item in current)
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
