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

from terraweaver import assembly, initiative, matching, ontology, timeutil
from terraweaver.ontology import Entity


class Relation(Entity):
    """Common ancestor of relation types: an instance linking a subject and an object."""

    def display_name(self) -> str:
        """The relation as a sentence, so a reversed one is easy to spot.

        Two shapes, because there are two kinds of link. A role is possessed — "Greg Hunt is
        Michael's landlord (service)" — and reads that way. A predicate is not: rendered the
        same way, `born_in` came out as "Thomas Kyd is London's born_in", which is not English
        and reads like a mistake. A recorder shown that at the close of its task concluded the
        link was backwards, wrote *"the relations need to be reversed"*, expired every correct
        one and recorded them the other way round. The sentence the world uses to make a
        reversal visible was itself producing reversals.
        """
        subject, obj = getattr(self, "subject", None), getattr(self, "object", None)
        kind = type(self)._spec["relation"]["kind"]
        said = self.__dict__.get("label") or (self.__dict__.get("role") or "").replace("_", " ")
        left = subject.display_name() if isinstance(subject, Entity) else "?"
        right = obj.display_name() if isinstance(obj, Entity) else "?"
        if said:
            # "you's dentist" is nobody's English: the owner reads as a person being spoken to.
            whose = "your" if right.lower() in ("you", "yourself") else f"{right}'s"
            return f"{left} is {whose} {said} ({kind})"
        return f"{left} {kind.replace('_', ' ')} {right} ({kind})"

    def both_ways(self) -> str:
        """The link said from each end. A reversed relation is caught here or not at all: the
        host wrote "Kevin reports to Tom" and what went in was "Kevin is Tom's manager", and the
        only moment it can still fix that cheaply is while it is holding the user's words."""
        rel = type(self)._spec["relation"]
        subject, obj = getattr(self, "subject", None), getattr(self, "object", None)
        said = self.display_name()
        if rule(rel, "symmetric") or not isinstance(subject, Entity) or not isinstance(obj, Entity):
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


# What a nature means, in one place. The rules are read from it, never copied beside it: a type
# that carried both `nature` and its own `transitive`/`symmetric` fields would be two statements
# of one thing, and two statements of one thing is how supersession was lost earlier today.
# What follows from each nature. `starts_required` is here rather than on the type because it
# is a property of the kind of link, not of the particular one: a department is part of a
# company and a chief executive is a kind of head, and nobody states the day either began —
# those are how things are arranged, not events. Something related_to another and holding one
# at a time is the opposite: which of two holds now is a question about when each began, and
# with no date the only answer left is the order they happened to be typed in. Inferred from
# the cardinality instead, the requirement reached `part_of` and refused facts nobody had a
# date for; the nature is the thing that tells these apart, which is what it is for.
BY_NATURE = {
    "part_of": {"transitive": True, "acyclic": True, "irreflexive": True,
                "starts_required": False},
    "kind_of": {"transitive": True, "acyclic": True, "irreflexive": True,
                "starts_required": False},
    "same_as": {"symmetric": True, "transitive": True, "starts_required": False},
    # A conclusion holds from the moment of what it was drawn from, which the world takes from
    # the basis rather than asking the host for.
    "derived_from": {"acyclic": True, "irreflexive": True, "starts_required": False},
    "related_to": {"starts_required": "when_it_changes"},
}


def _wants_a_start(rel: dict) -> bool:
    """Whether this kind of link is one whose beginning has to be said."""
    wanted = rule(rel, "starts_required", False)
    if wanted == "when_it_changes":
        return "at_any_time" in (rel.get("functional"), rel.get("inverse_functional"))
    return bool(wanted)


def rule_for(link, name: str, default=None):
    """One link's behaviour: its own nature if it named one, else its type's.

    A free link carries its nature itself, because it is written before any type exists and the
    nature is the only thing about it the world can act on — that a part is part of a whole all
    the way up, that a kind is a kind of a kind. Waiting for a type to be defined before behaving
    correctly would mean the first dozen of them behave wrongly.
    """
    mine = getattr(link, "nature", None)
    if mine and name in BY_NATURE.get(mine, {}):
        return BY_NATURE[mine][name]
    return rule(spec(type(link)), name, default)


def rule(rel: dict, name: str, default=None):
    """A relation's behaviour: what its nature says, unless the type states otherwise itself.

    The nature is an attribute, not a class — it names which rules apply. Reading them through
    here means a type and its nature cannot drift apart, and a nature gained or corrected is
    gained or corrected everywhere at once.
    """
    if name in rel:
        return rel[name]
    return BY_NATURE.get(rel.get("nature") or "", {}).get(name, default)


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
    if initiative.TAKES_NEAR_WORD:
        words = [w.strip() for line in known for w in line.split(" / ")]
        near = ontology.did_you_mean(wanted, words)
        if near:
            return resolve_kind(classes, ontology.take_as("relation type", kind, near))
    # A word this world has no type for makes one; it is not quietly read as the nearest word
    # that does. The nearest word is a number, and the number was wrong: "worked_in_city" stood
    # at 0.769 against "born_in_city" and "died_in_city" at 0.667, so a recorder that wrote
    # both correctly, four times each, had Pedro Pierluisi born in Washington and Amy Winehouse
    # born in Camden Town. Whether two words are one idea is not the world's to decide — it has
    # a similarity, the agent has the sentence the user said. The near one is named where the
    # type is made, and `take_in` moves the links if the agent agrees.
    raise ValueError(f"no relation type {kind!r}; the types are: {', '.join(known)}")


def _type_the_label_belongs_to(world, name: str, cls, rel: dict, attrs: dict) -> str | None:
    """The type a label really belongs to: "husband" is a partner, not kin.

    Recording it under the wrong type loses every check that type would do, so the link goes to
    the right one. This used to refuse and print the call the host should have written — which
    cost a turn to be told something the world had already worked out, and the second try was as
    often prose as the corrected call. Where the correction is unambiguous the world applies it
    and says so, the same bargain `take_as` makes for a misspelt word.
    """
    if not initiative.REROUTES_BY_LABEL:
        return None
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

def _make_the_type(world, subject, obj, kind: str, period: dict, attrs: dict, basis, why: str):
    """A word with no type behind it makes one, and the world says what it assumed.

    Free links were the answer before: keep the fact, count the word, and wait for somebody to
    define a type on the third showing. It kept the fact, but it left the host with a vocabulary
    that grew only when it remembered to look — and it never looked. Making the type at once is
    what the host meant by using the word, and everything guessed in the making is said out loud
    so it can be corrected: the nature, and that nothing is known yet about how many there may be.

    Nothing here is narrow. The ends stay open, because a type named after its first example
    refusing its second is what filled one run with `X_thing_to_thing`. And a word that reads
    like a type already here is handed that one instead, which is what keeps this from making a
    type per phrasing.
    """
    from terraweaver import authoring

    word = str(kind).strip().lower().replace(" ", "_").replace("-", "_")
    made = None
    try:
        made = authoring.Authoring(world, getattr(world, "grown_dir", None)).define_relation(
            word,
            # About the relation, never about the two things in front of it. Built from their
            # names, four spellings of one idea read as four ideas — the check that compares
            # descriptions saw "Thomas Kyd is to London" against "Amy Winehouse is to Camden"
            # and found them far apart, which they are, and made a type for each.
            str(attrs.get("description") or "").strip()
            or f"one {type(subject).__name__.lower()} {word.replace('_', ' ')} "
               f"one {type(obj).__name__.lower()}",
            nature="related_to", subject=None, object=None,
            # One value per subject, and a later telling corrects an earlier one. Made with no
            # limit, a person was born in two cities and played two positions at once: the type
            # the world invents is the type most of what a person says needs, and saying "as many
            # as you like" is not the cautious choice — it is a claim that nothing supersedes.
            cardinality="many-to-one", over_time=False)
    except Exception as refused:               # noqa: BLE001 - a world with no authoring, or a bad word
        free = next((n for n, c in relation_classes(world.classes).items()
                     if spec(c).get("free")), None)
        if free is None:
            raise ValueError(f"{why}; and no type could be made of {kind!r}: {refused}") from None
        label = str(attrs.get("label") or "").strip() or word.replace("_", " ")
        ontology.note_hint(f"{why} — kept as an untyped link labelled '{label}'.")
        return relate(world, subject, obj, spec(world.classes[free])["kind"], period,
                      {"label": label, "description": f"{subject.display_name()} {label} "
                                                      f"{obj.display_name()}"}, basis)

    theirs = spec(made)
    if theirs["kind"] != word:
        pass       # nothing swaps a word now; the near neighbour is said when the type is made
    else:
        ontology.note_hint(
            f"there was no type for '{kind}', so I made one: nature=related_to, between "
            f"anything and anything, one value per subject — saying it again with something "
            f"else corrects it, and the first stays in the record. If there can be several at "
            f"once (everything somebody has written, every place they have lived), or if it is "
            f"a part, a kind or the same thing, say so the way you would of anything: "
            f"{word}.nature = \"part_of\" (or kind_of / same_as / derived_from / related_to), "
            f"{word}.one_per_subject = False, {word}.changes = True — changes means a new one "
            f"ends the last instead of correcting it."
        )
    kept = {k: v for k, v in attrs.items()
            if k in {a["name"] for a in theirs.get("attributes", [])}}
    link = relate(world, subject, obj, theirs["kind"], period, kept, basis)
    if theirs["kind"] == word:
        # The hint above says this in the run that made the type, and a hint lives for that run
        # only. The assumption outlives it: the type is in the world for good with a nature
        # nobody confirmed, and the next task has no way of knowing one was guessed. A question
        # is the part that has to survive — raised once, on the link that caused the type.
        world.questions.raise_(
            link, f"nature_of_{theirs['kind']}",
            f"I made the type '{theirs['kind']}' for this and read it as: "
            f"\"{link.display_name()}\". Does that sentence say what you meant? If the two ends "
            f"are the wrong way round, write it from the other end — the subject is the one the "
            f"word describes. And I guessed at the rest: nature related_to, one per subject, no "
            f"time to it. Is that what the word means?",
            options=["related_to", "part_of", "kind_of", "same_as", "derived_from"],
        )
    return link


def relate(world, a, b, kind: str, period: dict, attrs: dict, basis: list | None = None):
    """Record that `a` stands in relation `kind` to `b` — or update that relation if it exists."""
    try:
        name, reverse = resolve_kind(world.classes, kind)
    except ValueError as unknown:                      # no such type: the link is still a link
        if not isinstance(a, Entity) or not isinstance(b, Entity):
            raise
        if not initiative.MAKES_TYPES:
            word = str(kind).strip().lower().replace(" ", "_").replace("-", "_")
            # The instruction first, the list of what exists after it. The other way round the
            # list is thirty types long and the one line that says what to do is off the end.
            raise ValueError(
                f"There is no relation type {word!r}. Define it, then say this again:\n"
                f"    world.define_relation(\"{word}\", \"<what this link is>\", "
                f"nature=\"related_to\", cardinality=\"many-to-one\", over_time=False)\n"
                f"nature is one of related_to / part_of / kind_of / same_as / derived_from. "
                f"over_time=True when one holds at a time and a new one ends the last (an "
                f"employer, a spouse); False when they simply accumulate.\n{unknown}"
            ) from None
        return _make_the_type(world, a, b, kind, period, attrs, basis, str(unknown))
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
    if rule(rel, "irreflexive", True) and same(subject, obj):
        raise ValueError(f"{subject.display_name()} can't be in a {name} relation with itself")
    belongs = _type_the_label_belongs_to(world, name, cls, rel, attrs)
    if belongs:
        other = spec(world.classes[belongs])
        ontology.note_hint(
            f"'{attrs['label']}' is a {other['kind']} relation, not {rel['kind']} — recorded as "
            f"{other['kind']}, which knows how that link behaves. Say it that way next time."
        )
        return relate(world, subject, obj, other["kind"], period, attrs, basis)
    # The three base types are natures wearing a type's clothes: `part_of`, `kind_of` and
    # `related` say how a link behaves and have no word of their own. Used directly as the type
    # of a fact, the fact's word is gone — "the capital of France is Paris" recorded as part_of
    # is true and unanswerable, because part_of is not one-per-object and Paris and Harare both
    # stand as parts of France. Twenty-four facts in the slice measured, eight of them a pair.
    # Sometimes "part of" really is the word, so this asks once per type per task rather than
    # refusing.
    if (rel["kind"] in ("part_of", "kind_of", "related") and not basis
            and not world.all(name, limit=1, history=True)):
        # Once, on the first link of this kind: the doubt is about the type, not about any one
        # link, and asked per link it is asked per fact.
        world.questions.raise_(
            subject, f"a_name_for_{rel['kind']}",
            f"You recorded this as {rel['kind']}, which says how the link behaves and not what "
            f"it is called. If the fact has a word of its own — 'the capital of', 'a branch "
            f"of' — define it and give it this nature, so the word can be asked about and can "
            f"supersede: world.define_relation('capital_of', '<what it is>', "
            f"nature='{rel['kind'] if rel['kind'] != 'related' else 'related_to'}', "
            f"cardinality='one-to-one', over_time=False). If '{rel['kind'].replace('_', ' ')}' "
            f"is the word, say so and I will not ask again.",
            options=["it has its own word", "this is the word"],
        )
    # The first link of a type is where its direction is settled, and the world knows the
    # sentence that link makes. "The capital of Germany is Berlin" went in as
    # `Germany -> CapitalOf -> Berlin`, which reads "Germany is Berlin's capital", and every
    # later link followed it — consistently backwards, so nothing that compares links with each
    # other can see it. Read back once, it is obvious; the world has the reading and the host
    # has the sentence, so the world shows its reading and asks.
    first_of_its_kind = (rel["kind"] not in ("part_of", "kind_of", "related") and not basis
                         and not world.all(name, limit=1, history=True))
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

    existing = [r for r in world.all(name, limit=None) if _between(r, subject, obj, rule(rel, "symmetric"))]
    if existing:
        found = existing[0]
        # Seen from the other end of a symmetric relation, a label is that side's label:
        # "Darren is Kevin's younger brother" after "Kevin is Darren's older brother".
        if rule(rel, "symmetric") and not same(found.subject, subject):
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

    if period.get("valid_from") is None and _wants_a_start(rel):
        # Required because the type says so, not because the world worked it out from the
        # cardinality. Inferred, it reached `part_of` and `partner` — a department is part of a
        # company and nobody states the day that began — and refused facts nobody had a date
        # for. Whoever defines the type is the one who knows whether its start is part of it;
        # `define_relation(over_time=True)` says yes, and a core type says so in its own file.
        # It is a required argument like any other, and it is checked where the others are.
        raise ValueError(
            f"{name} holds one at a time, so when it began is part of the fact and I will not "
            f"invent it. Say when:\n"
            f"    t = now()                       # or date(2006, 1, 1), or \"3 years ago\"\n"
            f"    a.{rel['kind']}(b, starts=t)\n"
            f"Take the moment once and pass the same value to everything you record in this "
            f"breath: two calls to now() are microseconds apart, and I would read that as two "
            f"deliberate overlapping claims. If all you know is which side of something it "
            f"falls on, starts=before(now()) and starts=after(date(2006, 1, 1)) say that."
        )
    start = period.get("valid_from") or timeutil.now()
    end = period.get("valid_until")
    if basis:
        _supersede_own_conclusions(world, name, rel, subject, obj, start, basis)
    _check_functional(world, name, rel, subject, obj, start, end, attrs)
    if attrs.get("role"):
        _check_roles(world, name, cls, subject, obj, attrs["role"], start, end)
    if rule(rel, "acyclic") and _reaches(world, name, obj, subject):
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
    if False:  # asked for before the link is made now, not noted after
        # A type that changes is a type with a time, so here the time is part of the fact and
        # not decoration on it. The world used to fill it in with today, which reads back a year
        # later as the day the job began — a date nobody said, indistinguishable from one
        # somebody did. So it asks, and it takes words: nobody knows the day they started
        # caring about something, and "before now" is a true sentence about it.
        ontology.note_hint(
            f"{name} holds one at a time, so when it began is part of the fact — and none was "
            f"said, so this one has no start. Say when, in whatever words you have: "
            f"starts='now', 'yesterday', '3 years ago', '2006-01-01', or, when that is all you "
            f"know, starts=before(now) / starts=after(date(2006, 1, 1)). Until then I cannot "
            f"tell this from the one before it except by which you told me last."
        )
    if rel.get("free"):
        _note_a_type_is_wanted(world, created)
    if first_of_its_kind:
        # Not a question of its own. Three blocking questions per task is ceremony, and the
        # sentence is already printed with every link the run makes — what is missing is a
        # moment when the host has to read them rather than skim past. That moment is the
        # close, where they are shown together, once.
        ontology.note_first_reading(name, created.display_name())
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
        f"world.define_relation(\"{idea.replace(' ', '_')}\", \"<what it is>\", "
        f"nature=\"related_to\", subject={a}, object={b}, "
        f"cardinality=<how many?>, over_time=<one at a time?>). "
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
    if not label or rule(rel, "symmetric"):
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


def _not_ours_to_end(link, start=None) -> bool:
    """Whether ending this link is a thing the world may decide by itself.

    Nothing in the data tells a handover from a correction — "her partner is Lena" after "her
    partner is Naomi" reads both ways, and no rule decides it. Two things make it the person's
    call rather than ours:

    A date. Given one, the link is a claim about a stretch of time, said deliberately; ending it
    on our own initiative overrides what somebody meant.

    Symmetry. A partnership or a kinship is a state two people are in together, and ending it is
    a claim about both of them at once — not a role one of them moved out of. Work, headship,
    managing a department run one way: the person's part in it changed, and the organisation is
    not displaced by that. A first attempt at this rule looked for a person at either end, and it
    refused every change of job, because the person changing jobs is at one of them.

    Everything else hands over, which is what a one-at-a-time relation is for.

    One exception to the date, and it decides the benchmark's whole subject: when the new link
    starts at the same moment the standing one does, the dates carry no ordering at all. Two
    equal timestamps are not a deliberate claim about overlapping stretches — they are the
    absence of a claim, and refusing over them loses the fact outright. This is what a recorder
    produces when it is told to say when and has not been told: `starts="now"` on both, which
    is the same invented date the world stopped writing, moved one step out. Measured: with no
    date the handover works and both are kept; with `starts="now"` on both the second was
    refused and nowhere in the world afterwards.
    """
    # Symmetry first, and it is not overruled by any date. A partnership is a state two people
    # are in together: ending it is a claim about both of them, and a date on one side does not
    # make it one side's to decide. Checked after the date, it stopped being checked at all.
    if rule(spec(type(link)), "symmetric"):
        return True
    when = getattr(link, "valid_from", None)
    if when is not None:
        if start is None:
            return True          # nothing to end it at but a date nobody gave
        # The new one's own start is where the old one ends. That is not the world deciding
        # anything: the boundary is a date the host gave, on the link it gave it for. The rule
        # this replaces was written when ending a dated link meant inventing its end, and it
        # refused every handover the moment starts became required — which is every handover.
        # A start *earlier* than the standing one is a different matter: it is a claim about a
        # stretch already spoken for, and which of them is wrong is not ours to pick.
        return timeutil.as_datetime(start) < timeutil.as_datetime(when)
    return False


# Two starts this close were meant to be the same moment. A host writing `starts=now()` on each
# line gets timestamps microseconds apart, and the world, reading them as two deliberate and
# overlapping claims, refuses the second and the fact is gone. The distance is the giveaway:
# nobody says "this began 300 microseconds after that one did".
_MEANT_THE_SAME_MOMENT = 2.0        # seconds


def _why_not_to_assume(link, start=None) -> str:
    when = getattr(link, "valid_from", None)
    if when is not None:
        if start is not None:
            apart = abs((timeutil.as_datetime(start) - timeutil.as_datetime(when)).total_seconds())
            if apart <= _MEANT_THE_SAME_MOMENT:
                return (
                    f"That one starts {apart:.3f}s before this one, which is not a difference "
                    f"anybody meant — it is `now()` called twice. If the two begin at the same "
                    f"moment, take it once and pass the same value to both:\n"
                    f"    t = now()\n"
                    f"    a.relate(x, kind, starts=t)\n"
                    f"    b.relate(x, kind, starts=t)\n"
                    f"Then the later telling hands over and both stay in the record. If they "
                    f"really do begin at different times, say when each one does."
                )
        return "That one was given a date, so ending it is not something to assume."
    return ("That kind of link is a state the two of them are in together, so ending it is not "
            "something to decide from one side.")


def _correct(world, standing, name: str, instead) -> None:
    """A second value for something that has only one, ever: the later reading is taken.

    A handover and a correction are not the same thing and the world had only the first. Work
    changes — both employers are true, in their turn. A birthplace does not: only one of the two
    is so, and the later telling is the one to believe, because it is the one the person said
    last. The earlier stays in the record as what was said, marked as no longer held, so the
    change is visible and reversible. Nothing is erased; `functional: True` was simply never
    checked at all, and a person could be born in two cities.
    """
    ontology.note_hint(
        f"{name} has one value and no more: {standing.display_name()} was recorded and this says "
        f"{instead.display_name()} instead. Taking the later as a correction — what was said "
        f"earlier stays in the record and is not what holds. Nothing is dated by this: a "
        f"correction is not a change, and saying it ended today would be inventing a day."
    )


# How many times one end can be handed over before the type itself is in doubt. A thing that
# changes hands three times may simply have changed hands three times; by the sixth the type is
# more likely to be wrong about how many there can be.
_HANDOVERS_BEFORE_ASKING = 3


def _too_many_handovers(world, name: str, rel: dict, end, side: str) -> None:
    """A type that keeps ending the last one on the same thing is a type that may be wrong.

    `citizen_of` was declared one citizen per country. Every American in the slice ended the
    last American's citizenship: twelve links to the United States, six of them still holding.
    The world cannot know that a country has many citizens — that is what the word means — but
    it can count the times it has ended one, and six is not a coincidence.
    """
    ended = [r for r in world.all(name, limit=None, history=True)
             if getattr(r, "valid_until", None) is not None
             and same(r.object if side == "object" else r.subject, end)]
    if len(ended) < _HANDOVERS_BEFORE_ASKING:
        return
    world.questions.raise_(
        end, f"one_{rel['kind']}_per_{side}_really",
        f"{end.display_name()} has had {len(ended) + 1} of {name} in this world, each ending "
        f"the last, because the type says there is one at a time. If a thing can have several "
        f"at once — a country has many citizens, a company many employees — say so and the "
        f"ones that were ended come back: {rel['kind']}.one_per_{side} = False.",
        options=["one at a time is right", "it can have several at once"],
    )


def _hand_over(world, standing, held, start, name: str) -> None:
    """A new holder of a one-at-a-time relation ends the last one, rather than being refused.

    This relation exists to be changed — that is what `over_time` says about it — and the change
    is the commonest thing anybody records: a new employer, a new capital, the sport a position
    turns out to belong to. Refusing it made the world answer "which one now" with the first
    thing it had ever been told: eight of ten wrong answers in one run were a superseded value
    still standing, because the statement that would have replaced it was turned away at the
    door and never written anywhere.

    What was said is not erased. The old link keeps its period and its history; it simply stops
    holding at the moment the new one starts.
    """
    if start is not None:
        # Written as the world's own, not the host's. It is a conclusion drawn from what the
        # type says about how many there can be — and when that is withdrawn, so is this: a
        # country declared to have one citizen ended six of them, and `one_per_object = False`
        # afterwards left every one of them ended, because nothing said who had ended them.
        with ontology.trusted_writes(), ontology.stating("world"):
            standing.valid_until = timeutil.as_datetime(start)
            world.save(standing)
        ontology.note_hint(
            f"{held.display_name()} had {standing.display_name()}, and {name} holds one at a "
            f"time, so that one ends {timeutil.show(start)} — the date this one starts."
        )
        return
    # No date, so none is written. Ending it today would say the world changed today, when all
    # that happened today is that somebody mentioned it; the two live in different fields and
    # putting the telling time into the other one invents an event. What holds is decided by what
    # was said last, the way it has always been decided for an attribute.
    #
    # This is the one case where the missing date changed the answer — it decided which of two
    # holds — so it is worth more than a hint that dies with the run.
    world.questions.raise_(
        standing, "when_it_changed",
        f"{held.display_name()} had {standing.display_name()} and now has this instead. Neither "
        f"was dated, so I am going by which I was told last. When did it change?",
    )
    ontology.note_hint(
        f"{held.display_name()} had {standing.display_name()} and now has "
        f"{'this' if True else ''} — {name} holds one at a time, so the later telling is what "
        f"holds. Neither is dated: if you know when it changed, say starts=... and I will put "
        f"the boundary there."
    )


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
            if same(r.subject, subject) or (rule(rel, "symmetric") and (same(r.object, subject) or same(r.subject, obj) or same(r.object, obj))):
                # The same link said again is both ends the same. Matching on the far end
                # alone let a symmetric relation through: "Vera's husband is Michael" and then
                # "Zoya's husband is Michael" share an object and are not one link.
                if same(r.subject, subject) and same(r.object, obj):
                    continue
                if rule(rel, "symmetric") and same(r.object, subject) and same(r.subject, obj):
                    continue
                if _not_ours_to_end(r, start):
                    raise ValueError(
                        f"{subject.display_name()} already has a {name} for that time: "
                        f"{r.display_name()}. {_why_not_to_assume(r, start)} {_how_to_make_room(start)}."
                    )
                _hand_over(world, r, subject, start, name)
    if rule(rel, "functional") is True:          # one ever, not one at a time
        for r in candidates:
            if same(r.subject, subject) and not same(r.object, obj):
                _correct(world, r, name, obj)
        # One per subject says nothing about the object, and that is where half of what people
        # say lands: "the chairperson of Fatah is Mahmoud Abbas" makes the person the subject,
        # so a later "the chairperson of Fatah is Yasser Arafat" is a different subject and
        # nothing supersedes. Measured on the benchmark's own pair: the world held both. The
        # world cannot know whether an organisation has one chairperson — that is what the word
        # means, and it has only the shape — but it can count, and two holders at once is worth
        # asking about once.
        for r in candidates:
            if same(r.object, obj) and not same(r.subject, subject):
                world.questions.raise_(
                    obj, f"one_{rel['kind']}_per_object",
                    f"{obj.display_name()} now has two: {r.subject.display_name()} and "
                    f"{subject.display_name()}, both {rel['kind'].replace('_', ' ')} it. If a "
                    f"thing has only one at a time, say so and the later one will supersede "
                    f"rather than join: {rel['kind']}.one_per_object = True. If it can have "
                    f"several, nothing to do.",
                    options=["one at a time", "several is right"],
                    involves=[r.subject, subject],
                )
                break
    if rule(rel, "inverse_functional") is True:
        for r in candidates:
            if same(r.object, obj) and not same(r.subject, subject):
                _correct(world, r, name, subject)
    if rel.get("inverse_functional") == "at_any_time":
        for r in candidates:
            if same(r.object, obj) and not same(r.subject, subject):
                if _not_ours_to_end(r, start):
                    raise ValueError(
                        f"{obj.display_name()} already has a {name} for that time: "
                        f"{r.display_name()}. {_why_not_to_assume(r, start)} {_how_to_make_room(start)}."
                    )
                _hand_over(world, r, obj, start, name)
                _too_many_handovers(world, name, rel, obj, "object")
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
    if not history:
        found = _only_what_still_holds(world, found)
    for relation in found:  # so rel.counterpart knows which end the host asked from
        relation.__dict__["_asked_from"] = entity
    return found


def _only_what_still_holds(world, found: list) -> list:
    """For a type with one value and no more, the latest telling — the rest is history.

    A correction has no date to it: saying "its head office is Tallinn" after "…is Dublin" is
    not news that it moved, it is being told the first was wrong, and writing an end date would
    invent the day it moved. So the earlier one is not ended, it is simply not what holds — and
    that is decided here, on the way out, the way a slot has always decided it.

    It has to be decided somewhere. Removing the invented end date left `_correct` announcing a
    correction and doing nothing, so a thing had two head offices and a person two birthplaces,
    and every count agreed with the host that ten facts were recorded.

    `history=True` (and `any_time=True`, which passes through it) still gives everything: what
    was said is never lost, it is only read as past.
    """
    # Counted per type, not across them. Held in one set, a person with a birthplace and a book
    # lost the book: both types say one value per subject, and the second link of the *second*
    # type was taken for a second value of the first. It showed as "the fact is not in the
    # world" while `relations("author_of")` returned it and its period was open.
    kept, seen_subject, seen_object = [], set(), set()
    for relation in found:              # already latest-first: stated over concluded, then time
        rel = spec(type(relation))
        kind = rel["kind"]
        subject_id = getattr(relation.subject, "id", None)
        object_id = getattr(relation.object, "id", None)
        if rule(rel, "functional") is True and subject_id is not None:
            if (kind, subject_id) in seen_subject:
                continue
            seen_subject.add((kind, subject_id))
        if rule(rel, "inverse_functional") is True and object_id is not None:
            if (kind, object_id) in seen_object:
                continue
            seen_object.add((kind, object_id))
        kept.append(relation)
    return kept


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
    if rule(rel, "symmetric") or not rel.get("reverse"):
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
        if rule(rel, "transitive"):
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
            arrow = "↔" if rule(rel, "symmetric") else "→"
            note = notes.get(rel["kind"], labels)
            lines.append(f"      {rel['kind']} {arrow} {' / '.join(rel['to'])}  — {note}")
        if not rule(rel, "symmetric") and rel.get("reverse") and (class_name in rel["to"] or "any" in rel["to"]):
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
        if rel.get("free") or rule(rel, "symmetric"):
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
            # With the same number each way there is no majority, and which of the two is
            # backwards is not something counting can tell. Naming one of them anyway picked
            # the right link and called it the wrong one — a coin toss dressed as a finding.
            tied = len(these) == len(shapes[usual])
            found.append({
                "about": "against the run of its type", "type": name,
                "links": [r.id for r in these] + ([r.id for r in shapes[usual]] if tied else []),
                "seen": len(these), "usual": len(shapes[usual]), "tied": tied,
                "said": (f"{name} has been written both ways: {len(these)} go "
                         f"{shape[0]} → {shape[1]} and {len(shapes[usual])} go {usual[0]} → "
                         f"{usual[1]}, and nothing says which is right. {rel.get('reads', '')}"
                         if tied else
                         f"{len(these)} {name} link(s) go {shape[0]} → {shape[1]} where "
                         f"{len(shapes[usual])} go {usual[0]} → {usual[1]}. "
                         f"{rel.get('reads', '')}").strip(),
                "settled_by": ("say which way it reads and turn the others round" if tied
                               else "turn them round, or say the type goes both ways"),
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
