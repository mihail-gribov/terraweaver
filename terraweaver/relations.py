"""Relations: instances that link two entities.

A relation has a `subject` and an `object` and otherwise is an entity like any other — its own
attributes, validity period, value history, comments. Each relation type is a class in the
ontology with a `relation` section that says how the link behaves; the world checks that in code:

    from / to              which classes may stand at each end ("any" for anything)
    symmetric              seen the same from both ends (Kin, Partner, Social)
    irreflexive            nothing relates to itself
    functional             "at_any_time": a subject has at most one current such relation
    inverse_functional     "at_any_time": an object has at most one current such relation
    acyclic                no cycle through the chain (Authority, PartOf)
    transitive             the chain counts (PartOf: a department of a division of a company)
    transitive_via         another type's chain extends this one (Membership via PartOf)
    reverse                the name read from the object's end ("members")
    labels                 what users typically call it; used to point a free Related link,
                           or a relationship label, to the type that fits
    one_of_a_label         a label names a post one person holds at a time (a dentist, a
                           manager) — a second one is worth a question; "friend" is not
    free                   Related: no characteristics, label and description required

"At any time" is checked by overlapping validity periods, not by "now": divorced in 2020 and
married in 2022 is no conflict. Design: docs/relations.md.
"""
from typing import Any

from terraweaver import ontology, timeutil
from terraweaver.ontology import Entity


class Relation(Entity):
    """Common ancestor of relation types: an instance linking a subject and an object."""

    def display_name(self) -> str:
        """The relation as a sentence, so a reversed one is easy to spot: "Greg Hunt is
        Michael's landlord (service)", not an arrow whose direction has to be remembered."""
        subject, obj = getattr(self, "subject", None), getattr(self, "object", None)
        kind = type(self)._spec["relation"]["kind"]
        what = self.__dict__.get("label") or (self.__dict__.get("role") or "").replace("_", " ") or kind
        left = subject.display_name() if isinstance(subject, Entity) else "?"
        right = obj.display_name() if isinstance(obj, Entity) else "?"
        # "you's dentist" is nobody's English: the owner reads as a person being spoken to.
        whose = "your" if right.lower() in ("you", "yourself") else f"{right}'s"
        return f"{left} is {whose} {what} ({kind})"

    def both_ways(self) -> str:
        """The link said from each end. A reversed relation is caught here or not at all: the
        host wrote "Kevin reports to Tom" and what went in was "Kevin is Tom's manager", and the
        only moment it can still fix that cheaply is while it is holding the user's words."""
        rel = type(self)._spec["relation"]
        subject, obj = getattr(self, "subject", None), getattr(self, "object", None)
        said = self.display_name()
        if rel.get("symmetric") or not isinstance(subject, Entity) or not isinstance(obj, Entity):
            return said
        word = str(self.__dict__.get("role") or self.__dict__.get("label") or "").strip().lower()
        for role in rel.get("roles", []):
            if word == role["name"] or word in [s.lower() for s in role.get("synonyms", [])]:
                if role.get("inverse"):
                    return f"{said} — so {obj.display_name()} is {subject.display_name()}'s {role['inverse']}"
        return said

    @property
    def counterpart(self):
        """The end that isn't the one you asked from — set when the relation came out of
        entity.relations(...), which is where a host means "the other one"."""
        asked = self.__dict__.get("_asked_from")
        if asked is None:
            raise AttributeError(
                "this relation wasn't read from one end, so there is no 'other' one: use "
                "rel.subject, rel.object, or rel.other(entity)."
            )
        return self.other(asked)

    def related(self, kind=None, **kw):
        """A relation has two ends and they have names — asking it for "the related one" is the
        question it can't answer, so say which end you mean."""
        raise TypeError(
            "a relation links two ends: rel.counterpart is the end that isn't the one you asked "
            "from (michael.relations('served_by')[0].counterpart), or name it — rel.subject, "
            "rel.object, rel.other(entity). rel.role_of(entity) says what an end is to the other."
        )

    def other(self, entity):
        """The end of this relation that isn't `entity`."""
        return self.object if same(self.subject, entity) else self.subject

    def role_of(self, entity):
        """What `entity` is to the other end: the subject plays `role`, the object its inverse.
        Maria —mother→ Michael: role_of(maria) is "mother", role_of(michael) is "child"."""
        role = self.__dict__.get("role")
        if same(entity, self.subject):
            return role or self.__dict__.get("label")
        inverse = role_info(type(self), role).get("inverse") if role else None
        return inverse or self.__dict__.get("label_reverse") or (self.__dict__.get("label") if spec(type(self)).get("symmetric") else None)


def same(a, b) -> bool:
    if a is b:
        return True
    return isinstance(a, Entity) and isinstance(b, Entity) and a.id is not None and a.id == b.id


def spec(cls) -> dict:
    return cls._spec.get("relation") or {}


def relation_classes(classes: dict[str, type]) -> dict[str, type]:
    return {name: cls for name, cls in classes.items() if "relation" in cls._spec}


def resolve_kind(classes: dict[str, type], kind: str) -> tuple[str, bool]:
    """(relation class name, whether `kind` was the reverse name)."""
    wanted = str(kind).strip().lower().replace(" ", "_").replace("-", "_")
    for name, cls in relation_classes(classes).items():
        rel = spec(cls)
        if wanted in (rel["kind"], name.lower()):
            return name, False
        if rel.get("reverse") and wanted == rel["reverse"]:
            return name, True
    known = []
    for name, cls in relation_classes(classes).items():
        rel = spec(cls)
        known.append(rel["kind"] + (f" / {rel['reverse']}" if rel.get("reverse") else ""))
    words = [w.strip() for line in known for w in line.split(" / ")]
    near = ontology.did_you_mean(wanted, words)
    if near:
        return resolve_kind(classes, ontology.take_as("relation type", kind, near))
    raise ValueError(f"no relation type {kind!r}; the types are: {', '.join(known)}")


def _check_label_fits(world, name: str, cls, rel: dict, attrs: dict) -> None:
    """A label is a user's word, but some words are another type's business: "husband" is a
    partner, not kin. Recording it under the wrong type loses every check that type would do,
    so the world refuses and says where it belongs."""
    label = str(attrs.get("label") or "").strip()
    if not label or rel.get("free"):
        return
    if label.lower() in [l.lower() for l in rel.get("labels", [])] or match_role(cls, label):
        return
    fitting = type_for_label(world.classes, label) or role_type(world.classes, label)
    if fitting and fitting != name:
        other = spec(world.classes[fitting])
        raise ValueError(
            f"'{label}' is a {other['kind']} relation, not {rel['kind']}: "
            f"a.relate(b, '{other['kind']}', label='{label}'). "
            f"{other['kind']} knows how that link behaves — {fitting} checks apply."
        )


def role_type(classes: dict[str, type], label: str) -> str | None:
    """The relation type one of whose roles this label names ("mom" -> Kin)."""
    for name, cls in relation_classes(classes).items():
        if spec(cls).get("roles") and match_role(cls, label):
            return name
    return None


def type_for_label(classes: dict[str, type], label: str) -> str | None:
    """The relation type whose typical labels include this one ("recruiter" -> Service)."""
    wanted = label.strip().lower()
    for name, cls in relation_classes(classes).items():
        if wanted in [l.lower() for l in spec(cls).get("labels", [])]:
            return name
    return None


_QUALIFIERS = ("older ", "younger ", "elder ", "big ", "little ", "baby ", "twin ", "my ", "late ", "ex-", "ex ")


def role_info(cls, role: str | None) -> dict:
    return next((r for r in spec(cls).get("roles", []) if r["name"] == role), {})


def match_role(cls, label: str | None) -> str | None:
    """The role a label names: "older brother" -> sibling, "mom" -> mother."""
    if not label:
        return None
    text = " ".join(str(label).lower().split())
    stripped = True
    while stripped:
        stripped = False
        for q in _QUALIFIERS:
            if text.startswith(q):
                text, stripped = text[len(q):], True
    roles = spec(cls).get("roles", [])
    for r in roles:
        if text in [x.lower() for x in r.get("synonyms", [])] or text == r["name"].replace("_", " "):
            return r["name"]
    last = text.split()[-1] if text.split() else text
    for r in roles:
        if last in [x.lower() for x in r.get("synonyms", []) if " " not in x]:
            return r["name"]
    return None


def _check_roles(world, name, cls, subject, obj, role, start, end) -> None:
    """A role's limit: a person has at most one mother, two parents, four grandparents."""
    info = role_info(cls, role)
    limits = [(role, info.get("max"), {role})] if info.get("max") else []
    group = info.get("counts_as")
    if group:
        members = {r["name"] for r in spec(cls).get("roles", []) if r.get("counts_as") == group} | {group}
        limits.append((group, role_info(cls, group).get("max"), members))
    for label, most, members in limits:
        if not most:
            continue
        holders = []
        for r in world.all(name, limit=None, history=True):
            if not _overlaps(r, start, end):
                continue
            plays = r.role_of(r.subject) if same(r.object, obj) else r.role_of(r.object) if same(r.subject, obj) else None
            if plays in members and not same(r.other(obj), subject):
                holders.append(r.other(obj))
        if len(holders) >= most:
            alternatives = info.get("alternatives") or role_info(cls, group).get("alternatives") or []
            names = ", ".join(h.display_name() for h in holders)
            raise ValueError(
                f"{obj.display_name()} already has {'a ' + label if most == 1 else str(most) + ' ' + label + 's'}: "
                f"{names}. A person has at most {most}. "
                + (f"If {subject.display_name()} is a {' or '.join(alternatives)}, say so in the label. " if alternatives else "")
                + "If the existing record is wrong, end or forget it first — ask the user which is right."
            )


def _fits(entity, allowed: list[str]) -> bool:
    return "any" in allowed or type(entity).__name__ in allowed


def _overlaps(rel, start, end) -> bool:
    """Whether a relation's validity period overlaps [start, end); None is open.

    A relation with no start holds from when it was recorded — it doesn't reach back forever,
    so a marriage entered today is no obstacle to recording one that ran 2010 to 2015."""
    r_start = getattr(rel, "valid_from", None) or getattr(rel, "created_at", None)
    r_end = getattr(rel, "valid_until", None)
    if r_end is not None and start is not None and timeutil.as_datetime(r_end) <= start:
        return False
    if end is not None and r_start is not None and timeutil.as_datetime(r_start) >= end:
        return False
    return True


# --- writing ---

def relate(world, a, b, kind: str, period: dict, attrs: dict):
    """Record that `a` stands in relation `kind` to `b` — or update that relation if it exists."""
    name, reverse = resolve_kind(world.classes, kind)
    subject, obj = (b, a) if reverse else (a, b)
    cls = world.classes[name]
    rel = spec(cls)
    for end in (subject, obj):
        if hasattr(end, "skill") and hasattr(end, "candidates"):  # an unanswered question, not an entity
            raise TypeError(
                f"{name} links two entities, and one of them is still a question: {end.reason}. "
                f"Settle it first — ask the user, then world.settle(<it>, <the one they meant>)."
            )
    if not isinstance(subject, Entity) or not isinstance(obj, Entity):
        raise TypeError(f"{name} links two entities; got {type(subject).__name__} and {type(obj).__name__}")
    if not _fits(subject, rel["from"]) or not _fits(obj, rel["to"]):
        raise ValueError(
            f"{name} goes {' / '.join(rel['from'])} → {' / '.join(rel['to'])}; "
            f"not {type(subject).__name__} → {type(obj).__name__}. For a link no type fits, use 'related'."
        )
    if rel.get("same_class") and type(subject) is not type(obj):
        raise ValueError(f"{name} links two of the same kind: {type(subject).__name__} and {type(obj).__name__} differ")
    if rel.get("irreflexive", True) and same(subject, obj):
        raise ValueError(f"{subject.display_name()} can't be in a {name} relation with itself")
    _check_label_fits(world, name, cls, rel, attrs)
    if rel.get("free"):
        missing = [k for k in ("label", "description") if not str(attrs.get(k) or "").strip()]
        if missing:
            raise ValueError(f"a Related link needs a label and a description of what it is; missing: {', '.join(missing)}")
        fitting = type_for_label(world.classes, attrs["label"])
        if fitting:
            ontology.note_hint(f"'{attrs['label']}' is what {fitting} is for — "
                               f"{spec(world.classes[fitting])['kind']} knows how that link behaves")
    if rel.get("roles"):
        given = attrs.get("role")
        text_field = rel.get("role_text")
        if given and not role_info(cls, given):
            if text_field and not attrs.get(text_field):
                # role="VP" is how people write a position: keep it as the title, find the role in it.
                attrs = {**attrs, text_field: given}
                attrs.pop("role")
                given = None
            else:
                raise ValueError(f"{name} has no role {given!r}; its roles: {', '.join(r['name'] for r in rel['roles'])}")
        found_role = given or match_role(cls, attrs.get("label")) or (match_role(cls, attrs.get(text_field)) if text_field else None)
        if found_role:
            attrs = {**attrs, "role": found_role}
    for end in (subject, obj):
        if end.id is None:
            world.save(end)

    existing = [r for r in world.all(name, limit=None) if _between(r, subject, obj, rel.get("symmetric"))]
    if existing:
        found = existing[0]
        # Seen from the other end of a symmetric relation, a label is that side's label:
        # "Darren is Kevin's younger brother" after "Kevin is Darren's older brother".
        if rel.get("symmetric") and not same(found.subject, subject):
            attrs = dict(attrs)
            attrs.pop("role", None)  # said from the other end: the stored role is the other side's
            if "label" in attrs and any(a["name"] == "label_reverse" for a in cls._spec["attributes"]):
                attrs["label_reverse"] = attrs.pop("label")
        for attr, value in attrs.items():
            if getattr(found, attr, None) != value:
                setattr(found, attr, value)
        if period:
            world.apply_period(found, period)
        return found

    start = period.get("valid_from") or timeutil.now()
    end = period.get("valid_until")
    _check_functional(world, name, rel, subject, obj, start, end, attrs)
    if attrs.get("role"):
        _check_roles(world, name, cls, subject, obj, attrs["role"], start, end)
    if rel.get("acyclic") and _reaches(world, name, obj, subject):
        raise ValueError(f"{name} can't form a cycle: {obj.display_name()} already leads to {subject.display_name()}")
    _note_flipped(world, name, rel, subject, obj, attrs)
    created = world.create(name, {"subject": subject, "object": obj, **attrs})
    if period:
        world.apply_period(created, period)
    _note_same_label(world, name, rel, subject, obj, attrs, start, end, created)
    return created


def _note_gap(world, name: str, obj, label: str, start, created) -> None:
    """A handover that leaves a day with nobody in the post.

    Periods here run from the start up to but not including the end, and nothing says so where
    a host is looking. Told "from October 1 it's Dr Patel instead of Dr Rao", a host ends Rao on
    September 30 and starts Patel on October 1 — which reads, to every question this world can
    be asked, as a day with no dentist. The dates are both plausible, so the world does not
    correct them; it says what they add up to and names the one that closes it.
    """
    from datetime import timedelta

    if start is None:
        return
    begins = timeutil.as_datetime(start)
    for r in world.all(name, limit=None, history=True):
        if same(r, created) or not same(r.object, obj):
            continue
        if str(getattr(r, "label", None) or getattr(r, "role", None) or "").strip().lower() != label:
            continue
        ends = getattr(r, "valid_until", None)
        if ends is None:
            continue
        space = begins - timeutil.as_datetime(ends)
        # A short space between two spells of one post is a slip; a long one is a real gap that
        # somebody meant — unless the old one was ended *now* while the new one starts later,
        # which is `.expire()` reached for where a date was needed. That one is always a slip.
        ended_today = abs(timeutil.as_datetime(ends) - timeutil.now()) < timedelta(hours=12)
        if timedelta(0) < space and (space <= timedelta(days=3) or ended_today):
            ontology.note_hint(
                f"{r.display_name()} ends {timeutil.show(ends)} and this one starts "
                f"{timeutil.show(begins)}, leaving no {label} in between for "
                f"{obj.display_name()}. "
                f"A period runs up to but not including its end, so a handover ends the old one "
                f"where the new one begins: old.keep(until={timeutil.show(begins)})."
            )
            return


def _note_flipped(world, name: str, rel: dict, subject, obj, attrs: dict) -> None:
    """The one kind of reversed link no type check can catch: both ends the same kind of thing.

    `user.relate(nina, "service", label="dentist")` records that the user is Nina's dentist. The
    type is satisfied — Person to Person — and the sentence is wrong. The world can still see it,
    not by knowing what a dentist is, but by reading what it already holds: every other 'dentist'
    link in this world has this person at the other end. That is consistency with its own data,
    which is its business; what a dentist is, is not.
    """
    label = str(attrs.get("label") or attrs.get("role") or "").strip().lower()
    if not label or rel.get("symmetric"):
        return
    others = [r for r in world.all(name, limit=None, history=True)
              if str(getattr(r, "label", None) or getattr(r, "role", None) or "").strip().lower() == label]
    if not others:
        return
    as_object = [r for r in others if same(r.object, subject)]
    as_subject = [r for r in others if same(r.subject, subject)]
    if as_object and not as_subject:
        ontology.note_hint(
            f"This records {subject.display_name()} as {obj.display_name()}'s {label}. Every "
            f"other {label} link here goes the other way — {as_object[0].display_name()}. If you "
            f"meant it the usual way round: {obj.display_name().split()[0].lower()}"
            f".relate({subject.display_name().split()[0].lower()}, '{rel['kind']}', label='{label}')."
        )


def note_gap_on_ending(world, relation) -> None:
    """The same slip made from the other end: ending the old holder today when the new one
    starts later. Whichever order a host does it in, the world says what the dates add up to."""
    rel = spec(type(relation))
    if not rel.get("one_of_a_label"):
        return
    label = str(getattr(relation, "label", None) or getattr(relation, "role", None) or "").strip().lower()
    ends = getattr(relation, "valid_until", None)
    obj = getattr(relation, "object", None)
    if not label or ends is None or not isinstance(obj, Entity):
        return
    from datetime import timedelta

    closed = timeutil.as_datetime(ends)
    for other in world.all(type(relation).__name__, limit=None, history=True):
        if same(other, relation) or not same(other.object, obj):
            continue
        if str(getattr(other, "label", None) or getattr(other, "role", None) or "").strip().lower() != label:
            continue
        starts = getattr(other, "valid_from", None)
        if starts is None:
            continue
        space = timeutil.as_datetime(starts) - closed
        if space > timedelta(0):
            when = timeutil.show(starts)
            ontology.note_hint(
                f"{relation.display_name()} now ends {timeutil.show(closed)}, and "
                f"{other.display_name()} starts {when} — leaving no {label} in "
                f"between for {obj.display_name()}. If one replaces the other, end this one "
                f"where that one begins: rel.keep(until={when})."
            )
            # And keep it, because a hint is read once. A gap is the kind of thing nobody
            # notices until the day somebody asks who the dentist was that week.
            world.questions.raise_(
                obj, "gap_between",
                f"no {label} between {timeutil.show(closed)} and {when}: "
                f"{relation.display_name()} ends, {other.display_name()} starts. "
                f"Was there really a gap, or does one replace the other?",
                options=[f"one replaces the other — end the old at {when}",
                         "there really was a gap"],
                involves=[relation, other],
                touches=[f"relation:{spec(type(relation))['kind']}", f"label:{label}"],
            )
            return


def _between(rel, subject, obj, symmetric: bool) -> bool:
    if same(rel.subject, subject) and same(rel.object, obj):
        return True
    return bool(symmetric) and same(rel.subject, obj) and same(rel.object, subject)


def _how_to_make_room(start) -> str:
    """What actually ends the old one where the new one begins.

    Offering `.expire()` first is advice to end it today, and when the new one starts in March
    that leaves months with nothing in the post — which is how a reorganisation announced ahead
    of time turned into a refusal the host could not get past."""
    if start is not None and timeutil.as_datetime(start) > timeutil.now():
        return (f"end that one where this one begins — old.keep(until={timeutil.show(start)}) — "
                f"or give this one a later starts=")
    return "end that one first (its .expire(), or keep(until=...)), or give this one starts= after it ends"


def _check_functional(world, name, rel, subject, obj, start, end, attrs) -> None:
    candidates = [r for r in world.all(name, limit=None, history=True) if _overlaps(r, start, end)]
    if rel.get("functional") == "at_any_time":
        for r in candidates:
            if same(r.subject, subject) or (rel.get("symmetric") and (same(r.object, subject) or same(r.subject, obj) or same(r.object, obj))):
                taken = subject if (same(r.subject, subject) or same(r.object, subject)) else obj
                raise ValueError(
                    f"{taken.display_name()} already has a {name} for that time: {r.display_name()}. "
                    f"One at a time — {_how_to_make_room(start)}."
                )
    if rel.get("inverse_functional") == "at_any_time":
        for r in candidates:
            if same(r.object, obj):
                raise ValueError(
                    f"{obj.display_name()} already has a {name} for that time: {r.display_name()}. "
                    f"One at a time — {_how_to_make_room(start)}."
                )
    if name == "Membership" and attrs.get("primary"):
        for r in candidates:
            if same(r.subject, subject) and getattr(r, "primary", False):
                later = start is not None and timeutil.as_datetime(start) > timeutil.now()
                raise ValueError(
                    f"{subject.display_name()} already has a primary membership for that time: "
                    f"{r.display_name()}. "
                    + (f"A move that begins later ends the old one there: "
                       f"old.keep(until={timeutil.show(start)}), then record this one."
                       if later else
                       "Assign person.organization instead — it closes the old one and opens the new one.")
                )


def _note_same_label(world, name: str, rel: dict, subject, obj, attrs: dict, start, end, created) -> None:
    """Two dentists at once is allowed — people do have two doctors — but "the new dentist
    instead of the old one" is what the user usually means, and the old one stays current
    unless someone ends it. Say it; don't decide it — and keep the doubt (questions.py), because
    a hint is read once and this one outlives the run that raised it."""
    label = str(attrs.get("label") or attrs.get("role") or "").strip().lower()
    if not label or rel.get("functional") == "at_any_time" or not rel.get("one_of_a_label"):
        # Only where a label names a post one person holds — a dentist, a manager. Two friends at
        # once is not a contradiction, and a world that asks about it teaches people to ignore it.
        return
    same_label = [
        r for r in world.all(name, limit=None, history=True)
        if same(r.object, obj) and not same(r, created) and _overlaps(r, start, end)
        and str(getattr(r, "label", None) or getattr(r, "role", None) or "").strip().lower() == label
    ]
    if not same_label:
        _note_gap(world, name, obj, label, start, created)
        return
    if same_label:
        old = same_label[0]
        # Name the exact fix, with the date: a replacement that begins in October ends the old
        # one in October, not today. A host told to ".expire() it" does it today and the world
        # ends up saying the user had no dentist for ten days.
        starts = getattr(created, "valid_from", None)
        if starts is not None and timeutil.as_datetime(starts) > timeutil.now():
            how = f"old.keep(until={timeutil.show(starts)}) — it ends where the new one begins"
        else:
            how = "old.expire() — it ends now, where the new one begins"
        ontology.note_hint(
            f"{obj.display_name()} already has a {label} for that time: {old.display_name()}. "
            f"Both stand unless you end one — if this replaces it: {how}."
        )
        world.questions.raise_(
            obj, "two_at_once",
            f"two {label}s at once: {old.other(obj).display_name()} and {subject.display_name()}. "
            f"Did the new one replace the old one?",
            options=[f"{subject.display_name()} replaces them — {how}", "both stand"],
            involves=[old, created],
            touches=[f"relation:{rel['kind']}", f"label:{label}"],
        )


def _reaches(world, name: str, start, target) -> bool:
    """Whether following `name` forward from `start` arrives at `target`."""
    seen, frontier = set(), [start]
    while frontier:
        node = frontier.pop()
        if same(node, target):
            return True
        key = node.id or id(node)
        if key in seen:
            continue
        seen.add(key)
        frontier += [r.object for r in world.all(name, limit=None) if same(r.subject, node)]
    return False


# --- reading ---

def relations_of(world, entity, kind: str | None = None, history: bool = False,
                 strict: bool = False) -> list:
    """The relations `entity` takes part in — of one type (by its name or reverse name) or all.

    `strict=True` turns off answering from the other end. A question asked about one entity is
    better answered with a correction than with a silence, but a filter over many is not a
    question: if "everyone with a membership" quietly matched the organizations too, the
    direction would stop meaning anything at all."""
    if kind is None:
        chosen = [(name, None) for name in relation_classes(world.classes)]
    else:
        name, reverse = resolve_kind(world.classes, kind)
        chosen = [(name, reverse)]
    found, hidden = [], []
    for name, _ in chosen:
        ontology.ask_if_questioned(entity, f"relation:{spec(world.classes[name])['kind']}")
    for name, reverse in chosen:
        symmetric = spec(world.classes[name]).get("symmetric")
        for r in world.all(name, limit=None, history=True):
            if symmetric or reverse is None:
                hit = same(r.subject, entity) or same(r.object, entity)
            else:
                hit = same(r.object, entity) if reverse else same(r.subject, entity)
            if not hit:
                continue
            if history or r.current():
                found.append(r)
            else:
                hidden.append(r)
    if hidden:
        _note_hidden(entity, kind, hidden)
    if kind is not None and not found and not hidden and not strict:
        found = _from_the_other_end(world, entity, kind, *chosen[0], history=history)
    # The one that was said last comes first, always and for every host. Where two relations
    # contradict each other this is the world's standing reading (questions.py, RULES), so a
    # singular answer — "who is my dentist" — is the same whoever asks and whenever they ask.
    found.sort(key=lambda r: (timeutil.as_datetime(r.valid_from or r.created_at), r.created_at),
               reverse=True)
    for relation in found:  # so rel.counterpart knows which end the host asked from
        relation.__dict__["_asked_from"] = entity
    return found


def _note_hidden(entity, kind: str | None, hidden: list) -> None:
    """Reads show what holds now. When that silence hides something — a relation that ended, or
    one that starts later — say so, or "she has no partner" gets answered about an ex."""
    now = timeutil.now()
    over = [r for r in hidden if r.valid_until and timeutil.as_datetime(r.valid_until) <= now]
    ahead = [r for r in hidden if r not in over]
    parts = []
    if over:
        parts.append(f"{len(over)} that ended ({'; '.join(r.display_name() for r in over[:3])})")
    if ahead:
        parts.append(f"{len(ahead)} that start later ({'; '.join(r.display_name() for r in ahead[:3])})")
    what = f"{kind} relations" if kind else "relations"
    ontology.note_hint(f"{entity.display_name()}: {' and '.join(parts)} — not shown, because {what} "
                       f"read as they hold now; any_time=True includes them")


def _from_the_other_end(world, entity, kind: str, name: str, reverse, history: bool) -> list:
    """Asked from the end with nothing on it, answer from the end that has it — and say so.

    A link has two ends with two names, and mixing them up is not a thing only hosts do; people
    do it constantly ("my dentist" and "I'm her patient" are one fact). Answering an empty list
    is technically right and practically a lie: the relation is right there, seen from the other
    side. So the world answers with what it has and corrects the wording, rather than leaving a
    silence the asker has no reason to question.

    Only ever a fallback: when the end asked about has anything at all, that is the answer, and
    this never runs. Nothing is guessed — the correction names the word that would have been
    right, so the next question can be asked properly.
    """
    rel = spec(world.classes[name])
    if rel.get("symmetric") or not rel.get("reverse"):
        return []
    mine = "object" if not reverse else "subject"
    theirs, later = [], []
    for r in world.all(name, limit=None, history=True):
        if not same(getattr(r, mine, None), entity):
            continue
        (theirs if (history or r.current()) else later).append(r)
    if not theirs:
        return []
    word = rel["kind"] if reverse else rel["reverse"]
    ontology.note_hint(
        f"{entity.display_name()}: nothing as {kind!r}, so this is the other end — {len(theirs)} "
        f"read as {word!r} ({'; '.join(r.display_name() for r in theirs[:3])}). You asked which "
        f"way round it was; it is the other way. Say {word!r} to ask for it directly."
        + (f" {len(later)} more are outside the period; any_time=True includes them." if later else ""))
    return theirs


def related(world, entity, kind: str, history: bool = False) -> list:
    """The entities at the other end — plus, for transitive types, the rest of the chain."""
    name, reverse = resolve_kind(world.classes, kind)
    rel = spec(world.classes[name])
    direct = [r.other(entity) for r in relations_of(world, entity, kind, history)]
    out = _unique(direct)
    if not reverse:
        if rel.get("transitive"):
            out = _unique(out + [x for d in direct for x in _chain(world, name, d)])
        if rel.get("transitive_via"):
            out = _unique(out + [x for d in direct for x in _chain(world, rel["transitive_via"], d)])
    return out


def _chain(world, name: str, start) -> list:
    """Everything reached by following `name` forward from `start`, nearest first."""
    out, node, seen = [], start, set()
    while True:
        nxt = [r.object for r in world.all(name, limit=None) if same(r.subject, node)]
        if not nxt or (nxt[0].id in seen):
            return out
        node = nxt[0]
        seen.add(node.id)
        out.append(node)


def _unique(items: list) -> list:
    out = []
    for item in items:
        if not any(same(item, x) for x in out):
            out.append(item)
    return out


def how_related(world, a, b, max_hops: int = 3) -> str | None:
    """How `b` is connected to `a` through current relations, in words, with a family name for
    the chain when there is one (sister's husband -> sibling-in-law)."""
    frontier = [(a, [])]
    seen = {a.id}
    for _ in range(max_hops):
        nxt = []
        for node, path in frontier:
            for r in relations_of(world, node):
                other = r.other(node)
                if other.id in seen:
                    continue
                step = path + [(r, other)]
                if same(other, b):
                    return _describe_path(world, a, step)
                seen.add(other.id)
                nxt.append((other, step))
        frontier = nxt
    return None


def _step_role(r, entity) -> str:
    role = r.role_of(entity)
    return role or spec(type(r))["kind"]


def _describe_path(world, a, path) -> str:
    parts = [a.display_name()]
    for r, entity in path:
        own = entity is r.subject and r.__dict__.get("label") or r.__dict__.get("label_reverse") if not same(entity, r.subject) else r.__dict__.get("label")
        parts.append(f"{own or _step_role(r, entity)} {entity.display_name()}")
    target = path[-1][1]
    name = _family_name(world, [(r, e) for r, e in path])
    lead = f"{target.display_name()} is {a.display_name()}'s {name.replace('_', ' ')}" if name else \
        f"{target.display_name()} is connected to {a.display_name()}"
    return f"{lead}: " + " → ".join(parts)


def _family_name(world, path) -> str | None:
    """The kinship term for a chain of family and partner steps, if the rules name it."""
    kin = world.classes.get("Kin")
    if kin is None:
        return None
    roles = []
    for r, entity in path:
        kind = spec(type(r))["kind"]
        if kind == "partner":
            roles.append("partner")
        elif kind == "kin":
            role = r.role_of(entity)
            roles.append(role_info(kin, role).get("counts_as") or role)
        else:
            return None
    if len(roles) == 1:
        return roles[0]
    for rule in spec(kin).get("compose", []):
        if rule["path"] == roles:
            return rule["gives"]
    return None


# --- attributes derived from relations ---

def _primary(world, person, history: bool = False) -> list:
    return [r for r in relations_of(world, person, "membership", history) if getattr(r, "primary", False)]


def _get_organization(person):
    world = ontology.current_world()
    primary = _primary(world, person)
    if primary:
        return primary[0].object
    jobs = relations_of(world, person, "membership")
    return jobs[0].object if len(jobs) == 1 else None


def _set_organization(person, org) -> None:
    world = ontology.current_world()
    if person.id is None:
        world.save(person)
    for r in _primary(world, person):
        if org is not None and same(r.object, org):
            return
        r.expire()
    if org is None:
        return
    current = [r for r in relations_of(world, person, "membership") if same(r.object, org)]
    if current:
        current[0].primary = True
        return
    relate(world, person, org, "membership", {}, {"primary": True, "kind": "employment"})


def _history_organization(person) -> list:
    from terraweaver.history import Past

    world = ontology.current_world()
    jobs = sorted(_primary(world, person, history=True),
                  key=lambda r: timeutil.as_datetime(r.valid_from or r.created_at))
    return [Past(r.object, r.valid_until) for r in jobs if r.valid_until is not None] + \
           [Past(r.object, None) for r in jobs if r.valid_until is None]


def _primary_membership(person):
    world = ontology.current_world()
    primary = _primary(world, person)
    if primary:
        return primary[0]
    jobs = relations_of(world, person, "membership")
    return jobs[0] if len(jobs) == 1 else None


def _get_job_title(person):
    job = _primary_membership(person)
    return job.title if job is not None else None


def _set_job_title(person, title) -> None:
    job = _primary_membership(person)
    if job is None:
        raise TypeError(
            "job_title is the role in the person's primary membership — set their organization first, "
            "or person.relate(org, 'membership', title=...)"
        )
    job.title = title


def _history_job_title(person) -> list:
    job = _primary_membership(person)
    return job.history("title") if job is not None else []


def _get_relationship(person):
    world = ontology.current_world()
    owner = world.owner
    if owner is None or same(owner, person):
        return None
    labels = []
    for r in relations_of(world, person, history=True):
        if not same(r.other(person), owner):
            continue
        label = getattr(r, "label", None) or spec(type(r))["kind"]
        ended = r.valid_until is not None and timeutil.as_datetime(r.valid_until) <= timeutil.now()
        labels.append(f"former {label}" if ended else label)
    return ", ".join(labels) or None


def _set_relationship(person, text) -> None:
    """Record what `person` is to the owner, from how the user put it."""
    world = ontology.current_world()
    owner = world.owner
    if owner is None or not text:
        return
    if person.id is None:
        world.save(person)
    label = str(text).strip()
    former = label.lower().startswith("former ")
    core = label[len("former "):] if former else label
    name = type_for_label(world.classes, core) or "Social"
    kind = spec(world.classes[name])["kind"]
    period = {"valid_until": timeutil.now()} if former else {}
    if name in ("Authority", "Service"):  # they manage / serve the owner
        relate(world, person, owner, kind, period, {"label": core})
    elif name in ("Kin", "Partner", "Social"):
        relate(world, owner, person, kind, period, {"label": core})
    else:
        relate(world, owner, person, "social", period, {"label": label})


def _get_employees(org):
    world = ontology.current_world()
    return _unique([r.subject for r in relations_of(world, org, "members")])


# (class, attribute) -> (getter, setter or None, history or None)
DERIVED = {
    ("Person", "organization"): (_get_organization, _set_organization, _history_organization),
    ("Person", "job_title"): (_get_job_title, _set_job_title, _history_job_title),
    ("Person", "relationship"): (_get_relationship, _set_relationship, None),
    ("Organization", "employees"): (_get_employees, None, None),
}

# The order derived attributes given at construction are applied in: a job title needs the job.
APPLY_ORDER = ["organization", "job_title", "relationship"]


def describe_relations(specs: dict[str, dict], class_name: str) -> list[str]:
    """Lines listing the relations a class takes part in, for the host's description."""
    notes = specs[class_name].get("relations", {})
    lines = []
    for name, s in specs.items():
        rel = s.get("relation")
        if not rel or rel.get("free"):
            continue
        labels = ", ".join(rel.get("labels", [])[:5])
        if class_name in rel["from"] or "any" in rel["from"]:
            arrow = "↔" if rel.get("symmetric") else "→"
            note = notes.get(rel["kind"], labels)
            lines.append(f"      {rel['kind']} {arrow} {' / '.join(rel['to'])}  — {note}")
        if not rel.get("symmetric") and rel.get("reverse") and (class_name in rel["to"] or "any" in rel["to"]):
            note = notes.get(rel["reverse"], f"read from this end of {rel['kind']}")
            lines.append(f"      {rel['reverse']} ← {' / '.join(rel['from'])}  — {note}")
    lines.append("      related → any  — anything no type fits (label and description required)")
    return lines
