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
from terraweaver import matching, nameforms

SAME_AS, NOT_SAME_AS = "same_as", "not_same_as"
# What a subject turned out to be. A class lives in the image and in the code the host writes;
# the record only says where the statements are kept, which is our business and never changes.
# So a thing can become a Sport later without a row moving and without a basis reference going
# stale — the world is told what it is, the way it is told everything else, and the image is
# built again. Said later, it supersedes; retracted, the thing is a Thing again.
IS_A = "is_a"

# Slots that say "this is a different one" when two subjects disagree about them. A name can be
# written half a dozen ways; an email address is either the same address or someone else's.
# One word for one place: free text lives in `descriptions`. `notes` and `description`
# are older spellings of it, still on disk in worlds written before the rename.
ONE_WORD_FOR_TEXT = {"notes": "descriptions", "description": "descriptions"}

DISTINGUISHING = ("email", "phone")


@dataclass
class Image:
    """One entity as the world currently reads it, with what it was built from."""

    id: str                      # the leading subject of the cluster: stable while it holds
    subjects: list[str]          # every subject this image was assembled from
    names: list = field(default_factory=list)    # forms someone vouched for, fullest first
    proposed_names: list = field(default_factory=list)  # forms only the world itself has offered
    values: dict[str, Any] = field(default_factory=dict)
    sources: dict[str, str] = field(default_factory=dict)   # slot -> whose word it is
    conflicts: dict[str, list] = field(default_factory=dict)  # slot -> statements left standing
    judged: set = field(default_factory=set)    # slots the world worked out rather than was told
    stale: set = field(default_factory=set)     # judgements whose basis has moved since

    def __repr__(self):
        name = self.values.get("full_name") or self.values.get("name") or self.id
        joined = f" ←{len(self.subjects)} subjects" if len(self.subjects) > 1 else ""
        return f"<image {name}{joined}>"


def same_name(a_facts: list, b_facts: list) -> bool:
    """The default rule: they answer to the same name, and nothing distinguishing says otherwise.

    Deliberately loose. Under the old architecture a wrong merge was a wound; here it is a guess
    that the next fact corrects."""
    # What class each was recorded under, which the statement's own id carries. Two things
    # recorded as different kinds are not one thing because they answer to one name: a city
    # called Paris and a person called Paris merged on rebuild, and the city was gone — not
    # corrected by the next fact, as a loose rule is supposed to be, but absent. A world that
    # asks about a shared name while it is running must not merge on it while rebuilding.
    a_classes = {f.id.split(":", 1)[0] for f in a_facts if ":" in str(f.id)}
    b_classes = {f.id.split(":", 1)[0] for f in b_facts if ":" in str(f.id)}
    if a_classes and b_classes and not (a_classes & b_classes):
        return False
    for slot in DISTINGUISHING:
        a_values = {_text(f.value) for f in a_facts if f.slot == slot}
        b_values = {_text(f.value) for f in b_facts if f.slot == slot}
        if a_values and b_values and not (a_values & b_values):
            return False
    # Only names someone vouched for: a nickname the world guessed at must not merge two people.
    a_names = [_text(f.value) for f in a_facts
               if f.slot in matching.NAME_KEYS.values() and f.source != facts_module.WORKED]
    b_names = [_text(f.value) for f in b_facts
               if f.slot in matching.NAME_KEYS.values() and f.source != facts_module.WORKED]
    # Both ways round: "Anna" asked against "Anna Sullivan" scores differently from the reverse,
    # and which of them the host happened to write down first shouldn't decide who someone is.
    #
    # But a name inside another name is only a short form where names work that way. It scores
    # exactly PART_CEILING, and applied to everything it merged Berkeley into the University of
    # California, Berkeley, rugby into rugby union, Australia into the Australian Open and
    # Bucharest into Bucharest Municipality — four cities and a sport, gone from the world on
    # rebuild. The live world has always known this and restricts it to the classes where it
    # holds; this did not, which is how the two disagreed about the same names.
    by_parts = any(one.split("facts_", 1)[-1] in matching.PART_MATCH_CLASSES
                   for one in (a_classes | b_classes))
    bar = matching.PART_CEILING if by_parts else matching.CERTAIN
    return any(max(matching.similarity(a, b), matching.similarity(b, a)) >= bar
               for a in a_names for b in b_names)


@dataclass
class Unsettled:
    """Two subjects that might be one person, with what would settle it."""

    subjects: tuple
    names: tuple
    missing: list          # what neither of them has, and either would decide it

    def __repr__(self):
        return (f"<unsettled {self.names[0]!r} / {self.names[1]!r} — "
                f"would settle it: {', '.join(self.missing)}>")


def unsettled(facts, rule: Callable[[list, list], bool] = same_name) -> list[Unsettled]:
    """Pairs the rules can neither join nor separate, and what would decide them.

    A third outcome, and the useful one to act on. The agent writes about "Anna" and the world
    already knows two; there is nothing to merge on and nothing to tell them apart by, so the
    statements sit on a subject of their own and the image is a stranger. What is needed is not a
    better rule — it is one more fact, and the world knows exactly which: an email, a surname,
    where she works. Asking for that is a better question than asking which of two rows to pick.
    """
    belongs = clusters(facts, rule)
    by_subject = {s: facts.about(s) for s in facts.subjects()}
    told_apart = {frozenset((f.subject, f.refers_to)) for f in facts.with_slot(NOT_SAME_AS)
                  if f.refers_to}
    out = []
    for a, b in matching_pairs(by_subject, rule, told_apart):
        if belongs[a] == belongs[b]:
            continue  # already one entity: nothing to ask
        a_names, b_names = _names_of(by_subject[a]), _names_of(by_subject[b])
        if not a_names or not b_names:
            continue
        missing = [slot for slot in DISTINGUISHING
                   if not any(f.slot == slot for f in by_subject[a])
                   or not any(f.slot == slot for f in by_subject[b])]
        out.append(Unsettled((a, b), (a_names[0], b_names[0]), missing or ["a fuller name"]))
    return out


def _names_of(statements: list) -> list:
    return [_text(f.value) for f in statements
            if f.slot in matching.NAME_KEYS.values() and f.source != facts_module.WORKED]


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

    def leads(subject: str) -> tuple:
        # The two parties lead whatever they are joined to. Everything else falls back on the
        # id itself, so a merge of two ordinary subjects lands on the same leader every time.
        #
        # Without this, the user is merged away by the first entity the host records under their
        # own name — and an id is a hex string, so which of the two survived was decided by
        # which sorted first. A rebuilt world then had a person nobody could look up, an
        # assistant with no owner, and `world.owner` returning None: the world no longer knew
        # whose it was. It only showed up on a rebuild, because until then both sat in the
        # images side by side.
        return (subject not in facts_module.THE_PARTIES, subject)

    def union(a: str, b: str) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            first, second = sorted((ra, rb), key=leads)
            leader[second] = first

    for a, b in told_same:  # what the user settled is not the rule's business
        if a in leader and b in leader:
            union(a, b)
    # Who could be whom, worked out for everyone before anything is joined. Doing it as we go
    # would let the order subjects happen to be in decide who someone is: the first Anna would
    # take the ambiguous mention and the second would never get a look.
    matches = matching_pairs(by_subject, rule, told_apart)
    partners: dict = {subject: set() for subject in by_subject}
    for a, b in matches:
        partners[a].add(b)
        partners[b].add(a)
    for a, b in matches:
        # One candidate each way is an answer. Two is a question — and merging into either would
        # be a guess dressed up as a fact. The world knows two Annas; a third mention of "Anna"
        # belongs to neither until something says which (see `unsettled`).
        if len(partners[a]) == 1 and len(partners[b]) == 1:
            union(a, b)
    return {subject: find(subject) for subject in by_subject}


def matching_pairs(by_subject: dict, rule: Callable[[list, list], bool], told_apart: set) -> list:
    """Every pair the rule would join, before anything is decided about them."""
    out = []
    subjects = sorted(by_subject)
    for i, a in enumerate(subjects):
        for b in subjects[i + 1:]:
            if frozenset((a, b)) in told_apart:
                continue
            if rule(by_subject[a], by_subject[b]):
                out.append((a, b))
    return out


def _kept_apart(told_apart: set, find: Callable[[str], str], a: str, b: str) -> bool:
    """Merging these two would also merge a pair the user has said are different."""
    for pair in told_apart:
        one, other = tuple(pair)
        if {find(one), find(other)} == {find(a), find(b)}:
            return True
    return False


def name_forms(statements: list, at: datetime) -> tuple[list, list]:
    """(the forms someone vouched for, the forms only the world has offered) — fullest first.

    A person is called several things — Michael, Mike, Michael Gribov — and none of them
    contradicts the others. They are forms of one name, collected rather than resolved, and the
    fullest is the one to show: it identifies without context.

    But a name is not an ordinary value: names decide who is who. A nickname the world merely
    guessed at — "Sota is probably that Sasha" — would quietly glue two people together on the
    next rebuild and be very hard to unpick afterwards. So a form counts as a name only if
    someone vouched for it: the user said it, or a source did. What the world worked out for
    itself waits in `proposed_names` until a word confirms it, and takes part in nothing.
    """
    standing = [s for s in statements if s.holds_at(at) and isinstance(s.value, str)]
    fullest_first = sorted(standing, key=lambda s: (len(str(s.value).split()), s.last_said),
                           reverse=True)
    vouched, proposed, seen = [], [], set()
    # Everything someone vouched for first: what the world proposes is judged against those, and
    # judging it against a half-built list would depend on the order statements happened to come.
    for statement in [s for s in fullest_first if s.source != facts_module.WORKED] + \
                     [s for s in fullest_first if s.source == facts_module.WORKED]:
        key = " ".join(str(statement.value).lower().split())
        if key in seen:
            continue
        seen.add(key)
        if statement.source != facts_module.WORKED:
            vouched.append(statement.value)
        elif any(nameforms.same_name(statement.value, form) for form in vouched):
            # Not a guess about this person: "Mike" is how the language says "Michael", and that
            # holds for everyone called Michael (nameforms.py). No one needs to confirm it.
            vouched.append(statement.value)
        else:
            proposed.append(statement.value)
    return vouched, proposed


def holds_many(specs: dict | None, class_name: str | None, slot: str) -> bool:
    """Whether a slot can hold more than one thing at a time.

    Two email addresses are not a disagreement — they are two addresses. Two employers at once
    are. Which is which is not for the assembler to guess: the class says so, by declaring the
    slot a list or not, and that is a level-2 decision (`docs/architecture.md`)."""
    spec = (specs or {}).get(class_name or "", {})
    declared = next((a.get("type", "") for a in spec.get("attributes", []) if a["name"] == slot), "")
    return declared.startswith("list[")


def resolve(statements: list, at: datetime | None = None):
    """Which statement about one slot the image shows: the most trusted, then the latest.

    Returns that statement and anything else still standing — a disagreement isn't hidden, it is
    reported, and that is where an open question comes from. A slot nobody ever states directly,
    like someone's character, is filled by what the world worked out; a slot someone did state is
    filled by them, because a conclusion is the weakest thing in the world."""
    from terraweaver import timeutil

    at = at or timeutil.now()
    standing = [s for s in statements if s.holds_at(at)]
    if not standing:
        return None, []
    # Trust, then the latest, then the later row. The third key is not decoration: two statements
    # made in the same moment used to be separated by the *string* id, where `facts_Person:10`
    # sorts before `facts_Person:9`, and a reverse sort is stable, so the earlier of the two won.
    # Under `set_now` — the replay the record exists for — every correction in a run has the same
    # `last_said` and the first one written kept the slot (docs/code-review-2026-09-30.md 3.1.3).
    standing.sort(key=lambda s: (facts_module.trust(s.source), s.last_said, _row_of(s)),
                  reverse=True)
    best = standing[0]
    rivals = [s for s in standing[1:]
              if _text(s.value) != _text(best.value) and facts_module.trust(s.source) == facts_module.trust(best.source)]
    return best, rivals


def became(facts, subjects: list[str]) -> str | None:
    """The class a subject was later said to be, latest word winning."""
    said = [s for subject in subjects for s in facts.about(subject, IS_A)]
    if not said:
        return None
    said.sort(key=lambda s: (s.valid_from or s.stated_at or "", s.id))
    return _text(said[-1].value) or None


def _row_of(statement) -> tuple:
    """A statement's place in its table, as a number — `facts_Person:9` is before `facts_Person:10`.

    An id is `<table>:<row>`, and the row is an autoincrementing integer, so this is the order the
    statements were written in. Compared as text, ten sorts before nine.
    """
    said = str(getattr(statement, "id", "") or "")
    table, _, row = said.rpartition(":")
    try:
        return (table, int(row))
    except ValueError:
        return (table, 0)


def assemble(facts, rule: Callable[[list, list], bool] = same_name, at: datetime | None = None,
             specs: dict | None = None) -> dict[str, Image]:
    """Build every image from every fact. Cheap enough to do from scratch; the same code path
    serves "rebuild the world" and "rebuild the one entity this run touched".

    The moment is settled once, here, and on the world's clock. Read three times from
    `datetime.utcnow()` further down, the images resolved at the wall clock while `happening()`
    answered on the world's `now`, so the two disagreed under `set_now` — which is the mode the
    record was built to be replayed in (docs/code-review-2026-09-30.md 3.1.4).
    """
    from terraweaver import timeutil

    at = at or timeutil.now()
    belongs = clusters(facts, rule)
    images: dict[str, Image] = {}
    for subject, image_id in belongs.items():
        images.setdefault(image_id, Image(id=image_id, subjects=[])).subjects.append(subject)
    for image in images.values():
        image.subjects.sort()
        by_slot: dict[str, list] = {}
        for subject in image.subjects:
            for statement in facts.about(subject):
                if statement.slot in (SAME_AS, NOT_SAME_AS, IS_A):
                    continue
                # Free text had three names once, and worlds recorded before that still hold
                # statements under the other two. They are read as what they always were.
                slot = ONE_WORD_FOR_TEXT.get(statement.slot, statement.slot)
                by_slot.setdefault(slot, []).append(statement)
        class_name = became(facts, image.subjects) or next(
            (facts.class_of(s) for s in image.subjects if facts.class_of(s)), None)
        name_slot = matching.NAME_KEYS.get(class_name or "")
        # Whatever it was called before is what it is called now: a Thing's `name` read as a
        # Vacancy's `title`. Without this the one thing every entity has would be the one thing
        # lost in becoming something else.
        for was, statements in list(by_slot.items()):
            if name_slot and was != name_slot and was in matching.NAME_KEYS.values():
                by_slot.setdefault(name_slot, []).extend(statements)
        for slot, statements in by_slot.items():
            if slot == name_slot:
                image.names, image.proposed_names = name_forms(statements, at)
                if image.names:
                    image.values[slot] = image.names[0]
                    image.sources[slot] = next(s.source for s in reversed(statements)
                                               if s.source != facts_module.WORKED)
                continue
            if holds_many(specs, class_name, slot):
                # Everything still standing, newest first. Nothing here is a rival to anything.
                standing = [s for s in statements if s.holds_at(at)]
                if not standing:
                    continue
                seen, many = set(), []
                for statement in sorted(standing, key=lambda s: s.last_said, reverse=True):
                    # A statement about a list slot may carry one value or the whole list — the
                    # host writes `tags = tags + ["x"]` as often as it appends — so they are
                    # flattened here. Otherwise an image ends up holding lists of lists, which is
                    # nobody's idea of a list of tags.
                    values = statement.value if isinstance(statement.value, list) else [statement.value]
                    for value in values:
                        key = _text(value)
                        if key in seen:
                            continue
                        seen.add(key)
                        many.append(belongs.get(value.get("$subject")) if _is_ref(value) else value)
                image.values[slot] = many
                image.sources[slot] = standing[-1].source
                continue
            best, rivals = resolve(statements, at)
            if best is None or best.value is None:
                continue
            value = best.value
            image.values[slot] = belongs.get(value.get("$subject")) if _is_ref(value) else value
            image.sources[slot] = best.source
            if best.is_conclusion:
                # The image says which values were worked out rather than told, so an answer can
                # be phrased as what it is — and a judgement whose basis has moved says so.
                image.judged.add(slot)
                if facts.stale(best):
                    image.stale.add(slot)
            if rivals:
                image.conflicts[slot] = rivals
    return images


def _is_ref(value) -> bool:
    return isinstance(value, dict) and "$subject" in value


def _text(value) -> str:
    return value.get("$subject") if _is_ref(value) else ("" if value is None else str(value))
