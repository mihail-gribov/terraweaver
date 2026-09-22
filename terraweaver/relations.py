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

import difflib

from terraweaver import assembly, ontology, timeutil
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

    def __getattr__(self, name):
        """What kind of link this is — 'membership', 'service' — when the type doesn't declare
        a `kind` of its own. Reached only when normal lookup fails, so a relation that has its
        own `kind` attribute keeps it; hosts ask for this constantly and got Python's bare
        message instead."""
        if name == "kind":
            return spec(type(self))["kind"]
        return Entity.__getattr__(self, name)

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

    def retract(self, why: str = "withdrawn") -> None:
        """Drop a link the world worked out and no longer believes.

        Not `expire()`: ending it says it held and then stopped, which about a guess is a second
        untruth on top of the first. Retracting takes back the statements that made it and
        removes the link itself; a relation the person actually stated is not retractable here —
        it was said, and what was said stays.
        """
        from terraweaver.ontology import current_world

        world = current_world()
        said = [s for s in world.facts.about(self.id) if not s.is_conclusion]
        if said:
            raise TypeError(
                f"{self.display_name()} was stated, not worked out — what was said stays. If it "
                f"has stopped holding, end it: rel.keep(until=...) or rel.expire().")
        for statement in world.facts.about(self.id):
            world.facts.retract(statement.id, by=why)
        world.store.forget(self.id)
        ontology.note_hint(f"{self.display_name()} was the world's own conclusion and is dropped "
                           f"({why}) — the statements it rested on are untouched.")

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
            # A word that was merged away still lands where its idea went. Refusing it would
            # cost the fact to save the tidiness, and the host learned this word from us.
            if rel.get("same_as"):
                return resolve_kind(classes, rel["same_as"])
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


def _type_the_label_belongs_to(world, name: str, cls, rel: dict, attrs: dict) -> str | None:
    """The type a label really belongs to: "husband" is a partner, not kin.

    Recording it under the wrong type loses every check that type would do, so the link goes to
    the right one. This used to refuse and print the call the host should have written — which
    cost a turn to be told something the world had already worked out, and the second try was as
    often prose as the corrected call. Where the correction is unambiguous the world applies it
    and says so, the same bargain `take_as` makes for a misspelt word.
    """
    label = str(attrs.get("label") or "").strip()
    if not label or rel.get("free"):
        return None
    if label.lower() in [l.lower() for l in rel.get("labels", [])] or match_role(cls, label):
        return None
    fitting = type_for_label(world.classes, label) or role_type(world.classes, label)
    return fitting if fitting and fitting != name else None


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

def _as_free_link(world, subject, obj, kind: str, period: dict, attrs: dict, basis, why: str):
    """A link the named type cannot hold is still a link: record it free rather than refuse it.

    Refusing cost far more than it protected. A host told that `located_in` goes Place → Continent
    does not look for a better type — it writes the fact into a description, and prose cannot be
    superseded, so the later correction settles beside the old sentence instead of replacing it.
    Half the notes in a 455-fact run arrived that way. The word the host reached for is kept as
    the label, which is also how restructuring finds the type the world is missing: a label that
    keeps turning up is a type waiting to be declared.
    """
    free = next((n for n, c in relation_classes(world.classes).items() if spec(c).get("free")), None)
    if free is None:                                   # a world without the free type has no room
        raise ValueError(why)
    label = str(attrs.get("label") or "").strip() or str(kind).strip()
    extras = {k: v for k, v in attrs.items() if k not in ("label", "description")}
    said = str(attrs.get("description") or "").strip()
    described = said or (f"{subject.display_name()} {label.replace('_', ' ')} {obj.display_name()}"
                         + (f" ({', '.join(f'{k}: {v}' for k, v in extras.items())})" if extras else ""))
    ontology.note_hint(
        f"{why} — recorded as a free link labelled '{label}' instead, so the fact is kept and can "
        f"be superseded later. Don't write it out as a description as well: that would be the "
        f"same fact twice, and the sentence would outlive any correction."
    )
    return relate(world, subject, obj, spec(world.classes[free])["kind"], period,
                  {"label": label, "description": described}, basis)


def relate(world, a, b, kind: str, period: dict, attrs: dict, basis: list | None = None):
    """Record that `a` stands in relation `kind` to `b` — or update that relation if it exists."""
    try:
        name, reverse = resolve_kind(world.classes, kind)
    except ValueError as unknown:                      # no such type: the link is still a link
        if not isinstance(a, Entity) or not isinstance(b, Entity):
            raise
        return _as_free_link(world, a, b, kind, period, attrs, basis, str(unknown))
    subject, obj = (b, a) if reverse else (a, b)
    cls = world.classes[name]
    rel = spec(cls)
    for end in (subject, obj):
        if hasattr(end, "skill") and hasattr(end, "candidates"):  # an unanswered question, not an entity
            # Held, not refused — the same as writing to a question directly (resolution.py).
            # Raising here discarded whole runs over one unsettled end: everything else the host
            # recorded in that block went with it.
            if end is subject:
                end.relate(obj, kind, **attrs)          # held on the question itself
            else:
                # The question is the far end, so the call that will make this link starts from
                # the other one. Holding `question.relate(subject, ...)` would settle into a
                # link pointing the wrong way.
                end.context.setdefault("held", []).append(("relate_to", (subject, kind), attrs))
                ontology.note_hint(
                    f"{end.reason}: this {kind} link is held until that is settled — "
                    f"world.settle(<this question>, <the one they meant>) makes it. Nothing "
                    f"else in this run is affected.")
            return None
    if not isinstance(subject, Entity) or not isinstance(obj, Entity):
        raise TypeError(f"{name} links two entities; got {type(subject).__name__} and {type(obj).__name__}")
    if not _fits(subject, rel["from"]) or not _fits(obj, rel["to"]):
        # Recorded, and noted. Classes are not fixed on a relation: the declaration says what has
        # been seen so far, and a link between other ends is news about the type rather than an
        # error in the link. `world.verify()` is where it is weighed.
        ontology.note_hint(
            f"{name} has run {' / '.join(rel['from'])} → {' / '.join(rel['to'])} until now, and "
            f"this one is {type(subject).__name__} → {type(obj).__name__}. Recorded as it is. If "
            f"it reads backwards, turn it round; if the type is wider than it was declared, it "
            f"is the declaration that is behind."
        )
    if rel.get("same_class") and type(subject) is not type(obj):
        raise ValueError(f"{name} links two of the same kind: {type(subject).__name__} and {type(obj).__name__} differ")
    if rel.get("irreflexive", True) and same(subject, obj):
        raise ValueError(f"{subject.display_name()} can't be in a {name} relation with itself")
    belongs = _type_the_label_belongs_to(world, name, cls, rel, attrs)
    if belongs:
        other = spec(world.classes[belongs])
        ontology.note_hint(
            f"'{attrs['label']}' is a {other['kind']} relation, not {rel['kind']} — recorded as "
            f"{other['kind']}, which knows how that link behaves. Say it that way next time."
        )
        return relate(world, subject, obj, other["kind"], period, attrs, basis)
    if rel.get("free"):
        # A label is what makes a free link readable; a description is prose about it. Requiring
        # the prose to accept the structure is backwards, and it refused four links in one run.
        if not str(attrs.get("label") or "").strip():
            raise ValueError("a Related link needs a label — one word for what this link is")
        if not str(attrs.get("description") or "").strip():
            attrs = {**attrs, "description": f"{subject.display_name()} "
                                             f"{attrs['label'].replace('_', ' ')} {obj.display_name()}"}
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
    if basis:
        _supersede_own_conclusions(world, name, rel, subject, obj, start, basis)
    _check_functional(world, name, rel, subject, obj, start, end, attrs)
    if attrs.get("role"):
        _check_roles(world, name, cls, subject, obj, attrs["role"], start, end)
    if rel.get("acyclic") and _reaches(world, name, obj, subject):
        raise ValueError(f"{name} can't form a cycle: {obj.display_name()} already leads to {subject.display_name()}")
    _note_flipped(world, name, rel, subject, obj, attrs)
    created = world.create(name, {"subject": subject, "object": obj, **attrs}, basis=basis,
                           period=period)
    if period and basis:
        period = {}      # already on it, and stated as the conclusion it is
    waiting = getattr(subject, "_waiting_title", None)
    if waiting and name == "Membership" and attrs.get("primary") and not attrs.get("title"):
        created.title = waiting          # the title that was set before there was a job
        object.__setattr__(subject, "_waiting_title", None)
    if period:
        world.apply_period(created, period)
    _note_same_label(world, name, rel, subject, obj, attrs, start, end, created)
    if rel.get("free"):
        _note_a_type_is_wanted(world, created)
    return created


# How many times one idea has to be written without a type before the world says so. Twice is a
# coincidence; the third is a habit, and a habit with stable ends is a type.
WANTED_AFTER = 3


def _note_a_type_is_wanted(world, created) -> None:
    """Say when the same untyped link keeps being written, and hand over the call that ends it.

    This is the world's half of the work. The host records what it can; the world counts, and
    when a word turns into a habit it says so with the definition already written out. Left to
    ask, a host never asks — it has no way of knowing it has said the same thing three times.

    The counting here is exact spelling, not meaning: it runs on every write, and a census that
    embeds is for `free_shapes()`, which is asked rather than triggered.
    """
    idea, _ = _asked(getattr(created, "label", "") or "")
    if not idea:
        return
    ends = {type(created.subject).__name__, type(created.object).__name__}
    kin = [r for r in world.all(type(created).__name__, limit=None)
           if _asked(getattr(r, "label", "") or "")[0] == idea
           and {type(r.subject).__name__, type(r.object).__name__} == ends]
    if len(kin) < WANTED_AFTER:
        return
    a, b = type(created.subject).__name__, type(created.object).__name__
    ontology.note_hint(
        f"'{idea}' has been written {len(kin)} times as a link with no type, always between "
        f"{a} and {b}. That is a type this world hasn't got: "
        f"world.define_relation(\"{idea.replace(' ', '_')}\", \"<what it is>\", subject={a}, "
        f"object={b}, cardinality=\"many-to-many\", over_time=<one at a time?>). "
        f"Then world.take_in(<the type>, \"{idea}\") moves the ones already written into "
        f"it — nothing is "
        f"re-read, they were structured all along."
    )


def _note_the_ones_that_did_not_fit(world, name: str, rel: dict, asked: str, moving: list) -> None:
    """Say when the same word was written between ends the type does not take.

    Refusing these at the door is what made the vocabulary worse: told that
    `affiliated_with_religion` goes Person → Thing, a host defined
    `affiliated_with_religion_thing_to_thing` rather than concluding its own type was too narrow.
    The type usually is too narrow — it was declared from the first example anybody saw. So the
    links stay free and the world says which type they were reaching for, because a host that
    hears "these do not fit" invents; one that hears "your type is narrower than your facts"
    can widen it.
    """
    free = [n for n, c in relation_classes(world.classes).items() if spec(c).get("free")]
    left = [link for n in free for link in world.all(n, limit=None)
            if link.subject is not None and link.object is not None
            and _asked(getattr(link, "label", "") or "")[0] == asked
            and not any(link.id == one.id for one in moving)]
    if not left:
        return
    shapes = sorted({f"{type(l.subject).__name__} → {type(l.object).__name__}" for l in left})
    ontology.note_hint(
        f"{len(left)} more link(s) say '{asked}' but between {' and '.join(shapes)}, and "
        f"{name} takes {' / '.join(rel.get('from') or ['any'])} → "
        f"{' / '.join(rel.get('to') or ['any'])}. They are still here, untyped. Most likely the "
        f"type is narrower than the facts — it was named after the first example. A second type "
        f"with the class names in it is the one thing not to do: that is two words for one idea, "
        f"and every later question has to ask both."
    )


def take_in(world, kind, idea: str | None = None) -> list:
    """Move the free links that were waiting for this type into it.

    The other half of defining a type. A host that defines one and leaves the links behind has
    two vocabularies for one idea, which is the state the type was meant to end. Nothing is
    interpreted and nothing moves on disk: each link is told what it is, the same statement a
    thing gets when the world learns its name.
    """
    name = kind if isinstance(kind, str) else getattr(kind, "__name__", str(kind))
    if name not in world.classes:
        raise ValueError(f"there is no relation type {name!r} here")
    rel = spec(world.classes[name])
    one_way = list(rel.get("from", [])) != list(rel.get("to", []))

    def fits_the_type(link) -> bool:
        """Each end against its own side of the type, in the direction it would be taken in.

        This was one unordered set of both sides, and a Thing → Thing link passed a
        Person → Thing type because Thing is in it somewhere. It went through here and failed
        where it was written instead, which read to the host as the type being wrong — and the
        host answered by defining a second type with the class names in it.
        """
        if link.subject is None or link.object is None:
            return False
        inverted = one_way and _asked(getattr(link, "label", "") or "")[1]
        start, end = (link.object, link.subject) if inverted else (link.subject, link.object)
        return _fits(start, rel.get("from") or ["any"]) and _fits(end, rel.get("to") or ["any"])

    free = [n for n, c in relation_classes(world.classes).items() if spec(c).get("free")]
    waiting = [link for n in free for link in world.all(n, limit=None) if fits_the_type(link)]
    asked = _asked(idea or rel.get("kind") or name)[0]
    theirs = {link.id: _asked(getattr(link, "label", "") or "")[0] for link in waiting}
    mine = {i for i, said in theirs.items() if said == asked}
    if waiting:
        # A type is rarely called what its links were called: `authorship` was written as
        # "author of", and no spelling rule crosses that. So the type is read as what it says it
        # is — its name and its description together — and the labels are ranked against that.
        # A looser bar than the one that groups labels with each other: taking them in is a
        # thing the host asked for, not a guess the world made on its own.
        ideas = sorted({said for said in theirs.values() if said})
        says = f"{rel.get('kind') or name}. {rel.get('description') or spec(world.classes[name]).get('description', '')}"
        vectors = world.meanings.model.embed([says] + ideas)
        close = {idea for idea, v in zip(ideas, vectors[1:])
                 if sum(a * b for a, b in zip(vectors[0], v)) >= _ONE_KIND}
        # Added to what matched by spelling, not instead of it. Running only when nothing matched
        # left every inverse spelling behind: three links called "author of" were taken and the
        # one called "authored by" stayed free, which is the case this was written for.
        mine |= {i for i, said in theirs.items() if said in close}
    # Told all at once and read again once. Becoming one at a time would rebuild the world
    # between each, and every link still in hand would be a stale copy of a thing that moved.
    moving = [link for link in waiting if link.id in mine]
    _note_the_ones_that_did_not_fit(world, name, rel, asked, moving)
    taken = []
    for link in moving:
        if one_way and _asked(getattr(link, "label", "") or "")[1]:
            # Written from the far end — "authored by" starts at the book. A type that runs one
            # way would take it in backwards, and a backwards link is a wrong fact, not an
            # untidy one. Turn it round first; the word that turned it is kept in a remark.
            with ontology.trusted_writes():
                link.subject, link.object = link.object, link.subject
            link.describe(f"turned round on becoming {name}: it was written "
                          f"'{getattr(link, 'label', '')}'")
        world.facts.state(getattr(link, "subject_id", None) or link.id, assembly.IS_A, name,
                          class_name=type(link).__name__)
        taken.append(world.retype(link, name))
    return taken


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


def _supersede_own_conclusions(world, name, rel, subject, obj, start, basis) -> None:
    """A later conclusion closes an earlier one of its own kind. Only its own.

    Between two things the world worked out for itself, the later evidence wins and the earlier
    reading ends where it begins — that is what supersession means, and refusing the second
    leaves the first standing as the answer, which is how a restructuring pass made a world
    worse than it found it. Between a conclusion and something the person said, nothing of the
    sort: the world does not overrule what it was told, and the ordinary refusal stands.
    """
    if rel.get("functional") != "at_any_time" and rel.get("inverse_functional") != "at_any_time":
        return
    for r in world.all(name, limit=None, history=True):
        if not (same(r.subject, subject) if rel.get("functional") == "at_any_time"
                else same(r.object, obj)):
            continue
        if not _overlaps(r, start, None) or getattr(r, "valid_until", None) is not None:
            continue
        said = [s for s in world.facts.about(r.id) if not s.is_conclusion]
        if said:
            continue                       # the person's, not the world's: leave it alone
        with ontology.trusted_writes(), ontology.not_recording():
            r.valid_until = start
        world.store.save_graph(r)
        world.facts.conclude(r.id, "valid_until", timeutil.as_datetime(start).isoformat(),
                             basis=basis, class_name=name)
        ontology.note_hint(
            f"{r.display_name()} was the world's own reading and ends {timeutil.show(start)}, "
            f"where the later one begins — both were worked out, so the later evidence wins.")


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
    by_label = None
    if kind is None:
        chosen = [(name, None) for name in relation_classes(world.classes)]
    else:
        try:
            name, reverse = resolve_kind(world.classes, kind)
            chosen = [(name, reverse)]
        except ValueError as unknown:
            # Not a type — but the world took this word when it was written, as the label of a
            # link it had no type for. Refusing to answer to it would mean a world that accepts
            # a host's own word and then cannot be asked about it, which is acceptance worth
            # nothing. So the free links are searched by what they were called.
            chosen = [(n, None) for n, c in relation_classes(world.classes).items()
                      if spec(c).get("free")]
            by_label = _asked(kind)[0]
            written = {_asked(getattr(r, "label", "") or "")[0]
                       for n, _ in chosen for r in world.all(n, limit=None, history=True)}
            if not by_label or by_label not in written:
                # Neither a type nor a word anybody has used. Answering "none" to that reads as
                # "there are no such links", when what is true is that the world has never heard
                # the word — and a typo would pass for an answer.
                near = ontology.did_you_mean(by_label or str(kind), sorted(written))
                raise ValueError(
                    str(unknown).rstrip(".") + (f"; nor is anything labelled {kind!r}"
                                                if not near else
                                                f"; nothing is labelled {kind!r} either — "
                                                f"did you mean {near!r}?")
                ) from None
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
            if by_label is not None and _asked(getattr(r, "label", "") or "")[0] != by_label:
                continue
            if history or r.current():
                found.append(r)
            else:
                hidden.append(r)
    if hidden:
        _note_hidden(entity, kind, hidden)
    if kind is not None and not found and not hidden and not strict:
        found = _from_the_other_end(world, entity, kind, *chosen[0], history=history)
    # What was said outranks what was worked out, and only then does the latest come first.
    # A slot has always been read this way (assembly.resolve: trust, then time) and a relation
    # was not — so a link the world derived for itself competed with one the person stated and
    # won on recency. That is how a restructuring pass made a world worse than it found it: it
    # added readings to the one channel where their source was never consulted.
    found.sort(key=lambda r: (_stated_rank(world, r),
                              timeutil.as_datetime(r.valid_from or r.created_at), r.created_at),
               reverse=True)
    for relation in found:  # so rel.counterpart knows which end the host asked from
        relation.__dict__["_asked_from"] = entity
    return found


def _stated_rank(world, relation) -> int:
    """2 for a link somebody stated, 1 for one the world worked out.

    The same order of trust the slots use, in the one place that lacked it. A conclusion is the
    weakest thing in this world; it should be read last, not first because it is newest."""
    try:
        said = world.facts.about(relation.id)
    except Exception:  # noqa: BLE001 - ordering must never be what breaks a read
        return 2
    return 1 if said and all(s.is_conclusion for s in said) else 2


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
    try:
        name, reverse = resolve_kind(world.classes, kind)
    except ValueError:
        # A word the world took as a label rather than a type. `relations_of` knows how to look
        # for those; there is no chain to follow, because an untyped link has no behaviour yet.
        return _unique([r.other(entity) for r in relations_of(world, entity, kind, history)])
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
        # Held rather than refused: a title with nobody to hold it under is not wrong, it is
        # early. The host usually writes the two lines in the other order, and refusing cost it
        # the statement seven times in one pool. It lands the moment an employer does.
        object.__setattr__(person, "_waiting_title", title)
        ontology.note_hint(
            f"{person.display_name()} has no employer recorded yet, so {title!r} is held as the "
            f"title and set the moment one is: person.relate(org, 'membership', primary=True), "
            f"or person.organization = org.")
        return
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


# --- what the free links are asking for ---

# Words that hang off a link's name without changing what it is. Only "by" and "from" turn it
# around, and only that matters here: which end the host started from.
_TAIL_WORDS = ("of", "by", "in", "at", "to", "for", "with", "from", "on")
_INVERTING = ("by", "from")
# How close two labels must read to count as one word for one thing. 0.8 keeps "author of" with
# "authored by" (0.92) and away from unrelated prose (0.62) on the model we use.
_ONE_IDEA = 0.8
# How close a label has to read to the type a host is taking it into. Looser, because the host
# has already said these belong together; the world is only deciding which ones it meant.
_ONE_KIND = 0.65


def _asked(label: str) -> tuple[str, bool]:
    """A label without its grammar, and whether the host started from the far end."""
    words = str(label or "").lower().replace("_", " ").replace("-", " ").split()
    inverted = bool(words) and words[-1] in _INVERTING
    while words and words[-1] in _TAIL_WORDS:
        words.pop()
    return " ".join(words), inverted


def _one_idea(world, labels: list[str]) -> list[list[str]]:
    """Labels grouped into the ideas behind them, by the world's own index of meaning.

    Spelling was tried first and is not enough: "performer of" and "performed by" are one idea
    and share four letters, while "author" loses its own name to a suffix rule. Meaning is what
    tells them apart, and the world already keeps an index of it. Where no model answers, the
    stand-in embedder still separates spellings of one word, which is most of the work.
    """
    if len(labels) < 2:
        return [list(labels)]
    vectors = world.meanings.model.embed(labels)
    groups: list[list[int]] = []
    for i in range(len(labels)):
        for group in groups:
            if any(sum(a * b for a, b in zip(vectors[i], vectors[j])) >= _ONE_IDEA for j in group):
                group.append(i)
                break
        else:
            groups.append([i])
    return [[labels[i] for i in group] for group in groups]


def free_shapes(world, least: int = 2) -> list[dict]:
    """The shapes the host keeps writing as free links, most asked-for first.

    A free link is a fact the world had no type for, recorded under the host's own word rather
    than refused. Counted, those words are the world's own evidence of what its vocabulary is
    missing: one idea, stable classes at each end, written often enough to be a habit.

    The two directions are one shape. `author of` from a Person and `authored by` from the thing
    are the same link read from opposite ends — which is precisely what a type's kind and its
    reverse name are, so the pair is what gets proposed, not two types.

    What a model does here is group spellings of one idea. What it does not do is decide the
    ends or the count: those are classes the world already assigned and arithmetic over them.
    Naming the type well comes afterwards, and is the only part worth a prompt.
    """
    free = [name for name, cls in relation_classes(world.classes).items() if spec(cls).get("free")]
    links: dict = {}
    for name in free:
        for link in world.all(name, limit=None):
            subject, obj = getattr(link, "subject", None), getattr(link, "object", None)
            label = str(getattr(link, "label", "") or "")
            idea, inverted = _asked(label)
            if subject is None or obj is None or not idea:
                continue
            ends = sorted((type(subject).__name__, type(obj).__name__))
            forward = (type(subject).__name__, type(obj).__name__) == tuple(ends)
            links.setdefault(tuple(ends), []).append(
                {"label": label, "idea": idea, "id": link.id,
                 "from_first_end": forward != inverted})

    shapes = []
    for ends, group in links.items():
        ideas = sorted({one["idea"] for one in group})
        for together in _one_idea(world, ideas):
            mine = [one for one in group if one["idea"] in together]
            if len(mine) < least:
                continue
            spellings: dict = {}
            for one in mine:
                spellings[one["label"]] = spellings.get(one["label"], 0) + 1
            leading = max(spellings, key=lambda w: spellings[w])
            starts_at = sum(1 for one in mine if one["from_first_end"])
            first, second = ends
            shapes.append({
                "asked": leading,
                "from": first if starts_at >= len(mine) - starts_at else second,
                "to": second if starts_at >= len(mine) - starts_at else first,
                "seen": len(mine),
                "both_ways": 0 < starts_at < len(mine),
                "labels": dict(sorted(spellings.items(), key=lambda kv: -kv[1])),
                "links": [one["id"] for one in mine],
            })
    shapes.sort(key=lambda s: (-s["seen"], s["asked"]))
    return shapes


# --- what the world knows about its own links ---

def ends_seen(world, name: str) -> dict:
    """Which classes actually stand at each end of this type, and how often.

    Declared ends are a guess somebody made from the first example. This is what the world has:
    counted, current, and its own business — no host promised it and none can get it wrong. It is
    what the type's description should say, and what an anomaly is measured against.
    """
    at: dict = {"from": {}, "to": {}}
    for link in world.all(name, limit=None, history=True):
        if link.subject is None or link.object is None:
            continue
        at["from"][type(link.subject).__name__] = at["from"].get(type(link.subject).__name__, 0) + 1
        at["to"][type(link.object).__name__] = at["to"].get(type(link.object).__name__, 0) + 1
    return {side: dict(sorted(held.items(), key=lambda kv: -kv[1])) for side, held in at.items()}


def as_it_runs(world, name: str, rel: dict) -> str:
    """The type's ends as one line — what the world has seen, falling back to what was declared."""
    seen = ends_seen(world, name)
    if not seen["from"]:
        return f"{' / '.join(rel.get('from') or ['any'])} → {' / '.join(rel.get('to') or ['any'])}"
    said = lambda side: " / ".join(f"{cls}" + (f" ×{n}" if len(seen[side]) > 1 else "")
                                   for cls, n in seen[side].items())
    return f"{said('from')} → {said('to')}"


# --- what the world can check about its own links ---

def verify(world, least: int = 3) -> list[dict]:
    """What the world notices about its own links, without refusing any of them.

    End types are worth having and not worth enforcing at the door: refused there, a fact turns
    into prose or into a second type with the class names in it, and both were counted. Kept as
    evidence instead, the same declaration answers three questions nobody could ask before —
    which link runs against its own type, which type is narrower than its facts, and which two
    types are one idea under two words.

    Nothing here is decided. Each finding says what was seen and what would settle it; the host
    or the person settles it, because every one of them has an innocent reading. A relation
    written from the far end is a mistake; a relation that genuinely goes both ways is not.
    """
    found: list[dict] = []
    for name, cls in relation_classes(world.classes).items():
        rel = spec(cls)
        if rel.get("free") or rel.get("symmetric"):
            continue
        links = [r for r in world.all(name, limit=None, history=True)
                 if r.subject is not None and r.object is not None]
        if not links:
            continue
        shapes: dict = {}
        for link in links:
            shapes.setdefault((type(link.subject).__name__, type(link.object).__name__),
                              []).append(link)
        usual = max(shapes, key=lambda k: len(shapes[k]))
        for shape, these in shapes.items():
            if shape == usual or shape != (usual[1], usual[0]):
                continue
            if len(these) * 2 > len(links):      # no majority to be against
                continue
            found.append({
                "about": "against the run of its type", "type": name,
                "links": [r.id for r in these], "seen": len(these),
                "said": f"{len(these)} {name} link(s) go {shape[0]} → {shape[1]} where "
                        f"{len(shapes[usual])} go {usual[0]} → {usual[1]}. "
                        f"{rel.get('reads', '')}".strip(),
                "settled_by": "turn them round, or say the type goes both ways",
            })
        # A car where a person always stands. Not reversed and not outside the declaration —
        # simply odd, which no rule catches and a reader sees at once. So the world counts what
        # usually stands at each end and names the few that do not, for the model to look at.
        already = {r.id for one in found if one["type"] == name for r in links
                   if r.id in one.get("links", [])}
        for side, position in ((0, "subject"), (1, "object")):
            standing: dict = {}
            for shape, these in shapes.items():
                standing.setdefault(shape[side], []).extend(these)
            if len(standing) < 2 or len(links) < least:
                continue
            common = max(standing, key=lambda c: len(standing[c]))
            for held, these in standing.items():
                these = [r for r in these if r.id not in already]
                if held == common or not these or len(these) * 4 > len(links):
                    continue
                # One link is one finding. Reversed, it already has one: saying the subject is
                # odd and the object is odd as well is the same news three times, and news
                # repeated three times is how a report stops being read.
                already.update(r.id for r in these)
                found.append({
                    "about": f"an odd {position}", "type": name, "seen": len(these),
                    "links": [r.id for r in these],
                    "said": f"{len(these)} {name} link(s) have a {held} as the {position} where "
                            f"{len(standing[common])} have a {common}: "
                            + "; ".join(f"{r.subject.display_name()} → {r.object.display_name()}"
                                        for r in these[:3]),
                    "settled_by": "read them: a thing standing where a person stands is usually "
                                  "a fact recorded against the wrong entity",
                })
        wider = sorted({c for shape in shapes for c in shape}
                       - {*rel.get("from", []), *rel.get("to", []), "any"})
        if wider and "any" not in rel.get("from", []) + rel.get("to", []):
            found.append({
                "about": "narrower than its facts", "type": name, "seen": len(wider),
                "said": f"{name} is declared {' / '.join(rel.get('from') or ['any'])} → "
                        f"{' / '.join(rel.get('to') or ['any'])} and holds links with "
                        f"{', '.join(wider)} at an end.",
                "settled_by": "widen the type, or these belong to another one",
            })
    each_way = _one_word_each_way(world)
    found.extend(each_way)
    # One pair, one finding: the precise reading — a link read from both ends, whose remedy is a
    # reverse name — says more than "these read alike", so it silences the looser one.
    already = {name for one in each_way for name in one["said"].split() if name in world.classes}
    found.extend(one for one in _one_idea_two_words(world, least)
                 if not already & {word.strip("(),") for word in one["said"].split()})
    return found


def _one_word_each_way(world) -> list[dict]:
    """Two types that are one link read from its two ends.

    `employed_by` and `employs` came out of one run as separate types. Reading their descriptions
    cannot catch it — they are written to differ, one naming the employer and one the employed —
    and the check that compares descriptions put them comfortably apart. What gives it away is
    arithmetic: the ends are mirrored and the names share a stem. A type already has a place for
    the other end; that place is `reverse`, and a second type is a second vocabulary for it.
    """
    typed = [(name, spec(cls)) for name, cls in relation_classes(world.classes).items()
             if not spec(cls).get("free")]
    seen, out = set(), []
    for name, rel in typed:
        ends = (tuple(rel.get("from") or ["any"]), tuple(rel.get("to") or ["any"]))
        if "any" in ends[0] + ends[1]:
            continue
        stem = _asked(rel.get("kind") or name)[0]
        for other, theirs in typed:
            if other == name or (other, name) in seen:
                continue
            mirrored = (tuple(theirs.get("from") or []), tuple(theirs.get("to") or [])) == (ends[1], ends[0])
            if not mirrored:
                continue
            # By closeness, not by equality: "employed_by" reduces to "employed" and "employs"
            # to "employs", and one letter of grammar is not a different idea.
            theirs_stem = _asked(theirs.get("kind") or other)[0]
            if not theirs_stem or not stem:
                continue
            if theirs_stem != stem and difflib.SequenceMatcher(
                    None, stem, theirs_stem).ratio() < 0.7:
                continue
            seen.add((name, other))
            held = {n: len(world.all(n, limit=None, history=True)) for n in (name, other)}
            out.append({
                "about": "one link read from both ends", "type": name, "seen": 2,
                "said": f"{name} goes {' / '.join(ends[0])} → {' / '.join(ends[1])} and {other} "
                        f"goes back the other way, on the same word. "
                        f"{', '.join(f'{n}: {held[n]} links' for n in held)}.",
                "settled_by": f"keep one and let the other be its reverse name — a type already "
                              f"has somewhere for the far end",
            })
    return out


def _one_idea_two_words(world, least: int) -> list[dict]:
    """Types of the same shape whose names read alike — one idea that got named twice.

    `affiliated_with_religion` and `affiliated_with_religion_thing_to_thing` came out of one run.
    The second exists because the first refused a pair of ends, which is the world's own doing;
    saying so is the least it can offer.
    """
    typed = [(name, spec(cls)) for name, cls in relation_classes(world.classes).items()
             if not spec(cls).get("free")]
    if len(typed) < 2:
        return []
    names = [name for name, _ in typed]
    out = []
    for group in _one_idea(world, [n.replace("_", " ") for n in names]):
        if len(group) < 2:
            continue
        together = [names[[n.replace("_", " ") for n in names].index(one)] for one in group]
        held = {n: len(world.all(n, limit=None, history=True)) for n in together}
        out.append({
            "about": "one idea under two words", "type": together[0], "seen": len(together),
            "said": f"{', '.join(f'{n} ({held[n]} links)' for n in together)} read as the same "
                    f"idea.",
            "settled_by": "keep one and take the others' links into it, or say how they differ",
        })
    return out


def merge(world, keep, drop) -> dict:
    """Make two relation types one, and leave the abandoned word working.

    A vocabulary grows two names for one idea — `associated_with_sport` and
    `associated_with_sport_person_thing` came out of one run — and naming the pair is no use
    without a way to close it. Every link of the dropped type becomes the kept one, the way a
    thing becomes what the world learns to call it: a statement, nothing moved, reversible by
    retracting it.

    The dropped name is not deleted. A host that learned it will write it again, and refusing
    then would cost the fact to save the tidiness — so the name stays as another word for the
    kept type, and `relate` follows it.
    """
    names = []
    for given in (keep, drop):
        name = given if isinstance(given, str) else getattr(given, "__name__", str(given))
        if name not in world.classes:
            raise ValueError(f"there is no relation type {name!r} here")
        if spec(world.classes[name]).get("free"):
            raise ValueError(f"{name} is the free type — everything untyped lives there, so it "
                             f"is not one idea and cannot be merged away")
        names.append(name)
    kept, dropped = names
    if kept == dropped:
        raise ValueError("a type is already itself")
    into, gone = spec(world.classes[kept]), spec(world.classes[dropped])
    moving = [r for r in world.all(dropped, limit=None, history=True)]
    for link in moving:
        world.facts.state(getattr(link, "subject_id", None) or link.id, assembly.IS_A, kept,
                          class_name=dropped)
    taken = [world.retype(link, kept) for link in moving]
    # What the dropped type knew, the kept one keeps: its words, and the word itself.
    into.setdefault("labels", [])
    for label in [gone.get("kind"), *(gone.get("labels") or [])]:
        if label and label not in into["labels"]:
            into["labels"].append(label)
    gone["same_as"] = into.get("kind") or kept
    ontology.note_hint(
        f"{dropped} is now another word for {kept}: {len(taken)} link(s) moved, and writing "
        f"'{gone['kind']}' still works — it lands on {kept}."
    )
    return {"kept": kept, "dropped": dropped, "moved": len(taken)}
