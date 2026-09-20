"""Who is who, and what they are like: the entities, built from what was said.

Two steps, and both are rules rather than records — which is the point of splitting the layers.
Change a rule, or learn one more fact, and rebuild: nothing was destroyed, so nothing is lost.

    1. identity   which subjects are one and the same, and so share an image
    2. resolution which of several statements about one slot the image shows

Identity is deliberately allowed to be optimistic. Two people called "Anna" may be glued into
one image — that is usually right, and when it isn't, one distinguishing fact (a surname that
differs, a second email, or the user saying "those are two different people") pulls them apart
on the next rebuild, with everything each of them said still attached to the right one. Being
wrong here costs a rebuild, not data.

What the user states outranks what any rule infers. "They are the same" and "they are not" are
facts like any other — `same_as` and `not_same_as` — so a correction survives every later
rebuild instead of being undone by the next rule that fancies a merge.
"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable

from terraweaver import facts as facts_module
from terraweaver import matching

SAME_AS, NOT_SAME_AS = "same_as", "not_same_as"

# Slots that say "this is a different one" when two subjects disagree about them. A name can be
# written half a dozen ways; an email address is either the same address or someone else's.
DISTINGUISHING = ("email", "phone")


@dataclass
class Image:
    """One entity as the world currently reads it, with what it was built from."""

    id: str                      # the leading subject of the cluster: stable while it holds
    subjects: list[str]          # every subject this image was assembled from
    values: dict[str, Any] = field(default_factory=dict)
    sources: dict[str, str] = field(default_factory=dict)   # slot -> whose word it is
    conflicts: dict[str, list] = field(default_factory=dict)  # slot -> statements left standing

    def __repr__(self):
        name = self.values.get("full_name") or self.values.get("name") or self.id
        joined = f" ←{len(self.subjects)} subjects" if len(self.subjects) > 1 else ""
        return f"<image {name}{joined}>"


def same_name(a_facts: list, b_facts: list) -> bool:
    """The default rule: they answer to the same name, and nothing distinguishing says otherwise.

    Deliberately loose. Under the old architecture a wrong merge was a wound; here it is a guess
    that the next fact corrects."""
    for slot in DISTINGUISHING:
        a_values = {_text(f.value) for f in a_facts if f.slot == slot}
        b_values = {_text(f.value) for f in b_facts if f.slot == slot}
        if a_values and b_values and not (a_values & b_values):
            return False
    a_names = [_text(f.value) for f in a_facts if f.slot in matching.NAME_KEYS.values()]
    b_names = [_text(f.value) for f in b_facts if f.slot in matching.NAME_KEYS.values()]
    return any(matching.similarity(a, b) >= matching.PART_CEILING for a in a_names for b in b_names)


def clusters(facts, rule: Callable[[list, list], bool] = same_name) -> dict[str, str]:
    """subject -> the image it belongs to. The user's word first, the rule only after it."""
    by_subject = {s: facts.about(s) for s in facts.subjects()}
    told_same = [(f.subject, f.refers_to) for f in facts.with_slot(SAME_AS) if f.refers_to]
    told_apart = {frozenset((f.subject, f.refers_to)) for f in facts.with_slot(NOT_SAME_AS) if f.refers_to}

    leader: dict[str, str] = {s: s for s in by_subject}

    def find(subject: str) -> str:
        while leader[subject] != subject:
            leader[subject] = leader[leader[subject]]
            subject = leader[subject]
        return subject

    def union(a: str, b: str) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            leader[max(ra, rb)] = min(ra, rb)  # the older subject leads, so ids stay stable

    for a, b in told_same:  # what the user settled is not the rule's business
        if a in leader and b in leader:
            union(a, b)
    subjects = sorted(by_subject)
    for i, a in enumerate(subjects):
        for b in subjects[i + 1:]:
            if frozenset((a, b)) in told_apart or find(a) == find(b):
                continue
            if _kept_apart(told_apart, find, a, b):
                continue
            if rule(by_subject[a], by_subject[b]):
                union(a, b)
    return {subject: find(subject) for subject in by_subject}


def _kept_apart(told_apart: set, find: Callable[[str], str], a: str, b: str) -> bool:
    """Merging these two would also merge a pair the user has said are different."""
    for pair in told_apart:
        one, other = tuple(pair)
        if {find(one), find(other)} == {find(a), find(b)}:
            return True
    return False


def resolve(statements: list, at: datetime | None = None) -> tuple[Any, str, list]:
    """Which statement about one slot the image shows: the most trusted, then the latest.

    Returns the value, whose word it is, and anything else still standing — a disagreement isn't
    hidden, it is reported, and that is where an open question comes from."""
    at = at or datetime.utcnow()
    standing = [s for s in statements if s.holds_at(at)]
    if not standing:
        return None, "", []
    standing.sort(key=lambda s: (facts_module.trust(s.source), s.stated_at), reverse=True)
    best = standing[0]
    rivals = [s for s in standing[1:]
              if _text(s.value) != _text(best.value) and facts_module.trust(s.source) == facts_module.trust(best.source)]
    return best.value, best.source, rivals


def assemble(facts, rule: Callable[[list, list], bool] = same_name, at: datetime | None = None) -> dict[str, Image]:
    """Build every image from every fact. Cheap enough to do from scratch; the same code path
    serves "rebuild the world" and "rebuild the one entity this run touched"."""
    belongs = clusters(facts, rule)
    images: dict[str, Image] = {}
    for subject, image_id in belongs.items():
        images.setdefault(image_id, Image(id=image_id, subjects=[])).subjects.append(subject)
    for image in images.values():
        image.subjects.sort()
        by_slot: dict[str, list] = {}
        for subject in image.subjects:
            for statement in facts.about(subject):
                if statement.slot in (SAME_AS, NOT_SAME_AS):
                    continue
                by_slot.setdefault(statement.slot, []).append(statement)
        for slot, statements in by_slot.items():
            value, source, rivals = resolve(statements, at)
            if value is None:
                continue
            image.values[slot] = belongs.get(value.get("$subject")) if _is_ref(value) else value
            image.sources[slot] = source
            if rivals:
                image.conflicts[slot] = rivals
    return images


def _is_ref(value) -> bool:
    return isinstance(value, dict) and "$subject" in value


def _text(value) -> str:
    return value.get("$subject") if _is_ref(value) else ("" if value is None else str(value))
