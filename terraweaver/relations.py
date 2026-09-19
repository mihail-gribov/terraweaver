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
        subject, obj = getattr(self, "subject", None), getattr(self, "object", None)
        kind = type(self)._spec["relation"]["kind"]
        own = self.__dict__.get("label")
        shown = f"{kind}: {own}" if own else kind
        left = subject.display_name() if isinstance(subject, Entity) else "?"
        right = obj.display_name() if isinstance(obj, Entity) else "?"
        arrow = "↔" if type(self)._spec["relation"].get("symmetric") else "→"
        return f"{left} {arrow} {right} ({shown})"

    def other(self, entity):
        """The end of this relation that isn't `entity`."""
        return self.object if same(self.subject, entity) else self.subject


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
    raise ValueError(f"no relation type {kind!r}; the types are: {', '.join(known)}")


def type_for_label(classes: dict[str, type], label: str) -> str | None:
    """The relation type whose typical labels include this one ("recruiter" -> Service)."""
    wanted = label.strip().lower()
    for name, cls in relation_classes(classes).items():
        if wanted in [l.lower() for l in spec(cls).get("labels", [])]:
            return name
    return None


def _fits(entity, allowed: list[str]) -> bool:
    return "any" in allowed or type(entity).__name__ in allowed


def _overlaps(rel, start, end) -> bool:
    """Whether a relation's validity period overlaps [start, end); None is open."""
    r_start, r_end = getattr(rel, "valid_from", None), getattr(rel, "valid_until", None)
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
    if rel.get("free"):
        missing = [k for k in ("label", "description") if not str(attrs.get(k) or "").strip()]
        if missing:
            raise ValueError(f"a Related link needs a label and a description of what it is; missing: {', '.join(missing)}")
        fitting = type_for_label(world.classes, attrs["label"])
        if fitting:
            ontology.note_hint(f"'{attrs['label']}' is what {fitting} is for — "
                               f"{spec(world.classes[fitting])['kind']} knows how that link behaves")
    for end in (subject, obj):
        if end.id is None:
            world.save(end)

    existing = [r for r in world.all(name, limit=None) if _between(r, subject, obj, rel.get("symmetric"))]
    if existing:
        found = existing[0]
        # Seen from the other end of a symmetric relation, a label is that side's label:
        # "Darren is Kevin's younger brother" after "Kevin is Darren's older brother".
        if rel.get("symmetric") and not same(found.subject, subject) and "label" in attrs \
                and any(a["name"] == "label_reverse" for a in cls._spec["attributes"]):
            attrs = dict(attrs)
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
    if rel.get("acyclic") and _reaches(world, name, obj, subject):
        raise ValueError(f"{name} can't form a cycle: {obj.display_name()} already leads to {subject.display_name()}")
    created = world.create(name, {"subject": subject, "object": obj, **attrs})
    if period:
        world.apply_period(created, period)
    return created


def _between(rel, subject, obj, symmetric: bool) -> bool:
    if same(rel.subject, subject) and same(rel.object, obj):
        return True
    return bool(symmetric) and same(rel.subject, obj) and same(rel.object, subject)


def _check_functional(world, name, rel, subject, obj, start, end, attrs) -> None:
    candidates = [r for r in world.all(name, limit=None, history=True) if _overlaps(r, start, end)]
    if rel.get("functional") == "at_any_time":
        for r in candidates:
            if same(r.subject, subject) or (rel.get("symmetric") and (same(r.object, subject) or same(r.subject, obj) or same(r.object, obj))):
                taken = subject if (same(r.subject, subject) or same(r.object, subject)) else obj
                raise ValueError(
                    f"{taken.display_name()} already has a {name} for that time: {r.display_name()}. One at a time — "
                    f"end that one first (its .expire(), or keep(until=...)), or give this one starts= after it ends."
                )
    if rel.get("inverse_functional") == "at_any_time":
        for r in candidates:
            if same(r.object, obj):
                raise ValueError(
                    f"{obj.display_name()} already has a {name} for that time: {r.display_name()}. One at a time — "
                    f"end that one first, or give this one starts= after it ends."
                )
    if name == "Membership" and attrs.get("primary"):
        for r in candidates:
            if same(r.subject, subject) and getattr(r, "primary", False):
                raise ValueError(
                    f"{subject.display_name()} already has a primary membership for that time: {r.display_name()}. "
                    f"Assign person.organization instead — it closes the old one and opens the new one."
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

def relations_of(world, entity, kind: str | None = None, history: bool = False) -> list:
    """The relations `entity` takes part in — of one type (by its name or reverse name) or all."""
    if kind is None:
        chosen = [(name, None) for name in relation_classes(world.classes)]
    else:
        name, reverse = resolve_kind(world.classes, kind)
        chosen = [(name, reverse)]
    found = []
    for name, reverse in chosen:
        symmetric = spec(world.classes[name]).get("symmetric")
        for r in world.all(name, limit=None, history=history):
            if symmetric or reverse is None:
                hit = same(r.subject, entity) or same(r.object, entity)
            else:
                hit = same(r.object, entity) if reverse else same(r.subject, entity)
            if hit:
                found.append(r)
    return found


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
    return job.role if job is not None else None


def _set_job_title(person, title) -> None:
    job = _primary_membership(person)
    if job is None:
        raise TypeError(
            "job_title is the role in the person's primary membership — set their organization first, "
            "or person.relate(org, 'membership', role=...)"
        )
    job.role = title


def _history_job_title(person) -> list:
    job = _primary_membership(person)
    return job.history("role") if job is not None else []


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
