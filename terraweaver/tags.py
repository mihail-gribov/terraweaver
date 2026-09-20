"""Tags: the loosest way to tie things together, and the one that rots fastest.

A tag is what someone reaches for when things belong together and no relation says how —
"job-search", "berlin", "to-read". It is the place for a tie too vague to formalise: everything
about the move, everyone from that conference, the things that matter this month. A relation type
would have to say what the tie *is*; a tag only says that there is one. It costs nothing to add, which is its virtue and its
problem: within a month a world has `job-search`, `job search`, `jobsearch` and `work`, and none
of them finds the others.

So the world does two things and refuses a third.

**It holds them to one shape.** A tag is kept in one form — lower case, single spaces, no
trailing punctuation — because a tag typed three ways is three categories that never find each
other. That is data uniformity, which is the world's business.

Tidying is a rule, though, and rules belong to the assembly rather than to the record: the
statement keeps the tag as it was given, the entity holds it in one form. So the rule can change
— a different way of folding spaces, a decision to keep case — and the world is rebuilt from what
was actually written. It is the same arrangement as an email address: stored as typed, compared
in one form.

**It counts them.** What tags exist, how often each is used and on what — the evidence any
review needs. A tag used once is not a category, it is a note someone left.

**It says when a tag is worth looking at again.** Not on a calendar — a tag nobody has touched
since spring needs no review, and one that gained eleven members last week does. What is
recorded is how many things a tag covered when it was last looked at; when that number has moved
enough, the tag comes back on the list. New information is what makes a judgement stale, not time.

**It does what it is told.** Merging two words into one, taking a tag off everything, picking
out what carries several at once — those are operations, and the world performs them as ordinary
writes: stated, reversible, visible in the record.

**It does not tidy them.** Whether `job-search` and `work` are the same idea, whether a tag that
covers forty things should be split, whether one nobody has used since March should go — those
are judgements about what this person means by a word, and they belong to the model, on the
agenda, as proposals. The world measures; somebody decides.
"""
import re
from datetime import datetime, timezone

from terraweaver.store import run_script

_TIDY = re.compile(r"[\s_]+")

SCHEMA = """
CREATE TABLE IF NOT EXISTS tag_reviews (
    tag TEXT PRIMARY KEY,
    reviewed_at TEXT NOT NULL,
    members_then INTEGER NOT NULL
)
"""

# How much a tag must have grown since it was last looked at before it is worth looking again.
GROWN_BY = 0.5


def canonical(tag: str) -> str:
    """The form a tag is compared in — not the form it is stored in."""
    text = _TIDY.sub("-", str(tag).strip().lower())
    return text.strip("-•,.;:!?").replace("--", "-")


def tidy(values) -> list[str]:
    """A list of tags as the world keeps them: one form each, in order, without repeats."""
    out: list[str] = []
    for tag in values or []:
        if not isinstance(tag, str) or not tag.strip():
            continue
        clean = canonical(tag)
        if clean and clean not in out:
            out.append(clean)
    return out


def tags_of(entity) -> list[str]:
    values = getattr(entity, "tags", None)
    return [t for t in (values or []) if isinstance(t, str) and t.strip()]


def vocabulary(world) -> dict[str, dict]:
    """Every tag in this world: how often it is used, on what, and how it has been written.

    The spellings matter as much as the count — three ways of writing one tag is exactly the
    thing worth reviewing, and it is invisible if they are folded together silently.
    """
    found: dict[str, dict] = {}
    for class_name, cls in world.classes.items():
        if not any(a["name"] == "tags" for a in cls._spec["attributes"]):
            continue
        for entity in world.all(class_name, limit=None, history=True):
            for tag in tags_of(entity):
                entry = found.setdefault(canonical(tag),
                                         {"count": 0, "classes": set(), "spellings": set(),
                                          "entities": []})
                entry["count"] += 1
                entry["classes"].add(class_name)
                entry["spellings"].add(tag)
                entry["entities"].append(entity)
    return found


def tagged(world, tag: str) -> list:
    """Everything carrying this tag, however it was written."""
    entry = vocabulary(world).get(canonical(tag))
    return list(entry["entities"]) if entry else []


def once_only(world) -> list[str]:
    """Tags used a single time — a note someone left, not a category."""
    return sorted(tag for tag, entry in vocabulary(world).items() if entry["count"] == 1)


def written_several_ways(world) -> list[tuple[str, list[str]]]:
    """Tags typed more than one way, read from the record rather than from the entities.

    The entities hold the tidy form — that is the point of tidying — so the spellings are only
    in the statements, which keep what was given. Worth knowing: a tag written four ways is
    usually a host being careless, and occasionally two ideas that got folded into one.
    """
    spellings: dict = {}
    for statement in world.facts.with_slot("tags"):
        for tag in statement.value or []:
            if isinstance(tag, str) and tag.strip():
                spellings.setdefault(canonical(tag), set()).add(tag)
    return sorted((tag, sorted(ways)) for tag, ways in spellings.items() if len(ways) > 1)


def look_alike(world, closeness: float = 0.8) -> list[tuple[str, str, float]]:
    """Pairs of tags that read like the same idea — candidates for a review, never a merge.

    Measured by meaning where a model is there, and by spelling where it isn't. Either way this
    is a list to look at: what a person means by a word is not the world's to decide.
    """
    from difflib import SequenceMatcher

    names = sorted(vocabulary(world))
    if len(names) < 2:
        return []
    vectors = {}
    try:
        for name, vector in zip(names, world.meanings.model.embed(names)):
            vectors[name] = vector
    except Exception:  # noqa: BLE001 - no model, no meaning: spelling still says something
        vectors = {}
    pairs = []
    for i, one in enumerate(names):
        for other in names[i + 1:]:
            if vectors:
                score = sum(a * b for a, b in zip(vectors[one], vectors[other]))
            else:
                score = SequenceMatcher(None, one, other).ratio()
            if score >= closeness:
                pairs.append((one, other, round(score, 3)))
    return sorted(pairs, key=lambda triple: -triple[2])


def reviewed(world, tag: str, members: int | None = None) -> None:
    """Record that somebody looked at this tag, and how much it covered at the time."""
    run_script(world.store.conn, SCHEMA)
    if members is None:
        members = len(tagged(world, tag))
    world.store.conn.execute(
        "INSERT OR REPLACE INTO tag_reviews (tag, reviewed_at, members_then) VALUES (?, ?, ?)",
        (canonical(tag), datetime.now(timezone.utc).isoformat(), members))
    world.store.conn.commit()


def due_for_review(world) -> list[tuple[str, int, int]]:
    """(tag, what it covers now, what it covered when last looked at) — for tags that have moved.

    A tag nobody has added to since it was last considered is settled as far as anyone knows. One
    that has half again as much under it may have become two ideas, or drifted into meaning
    something else, and that is worth a look. Never looked at at all counts as due, once there is
    enough under it to be a category rather than a note.
    """
    run_script(world.store.conn, SCHEMA)
    seen = {tag: members for tag, members in world.store.conn.execute(
        "SELECT tag, members_then FROM tag_reviews")}
    due = []
    for tag, entry in vocabulary(world).items():
        now = entry["count"]
        before = seen.get(tag)
        if before is None:
            if now >= 3:
                due.append((tag, now, 0))
        elif now >= before + max(2, before * GROWN_BY):
            due.append((tag, now, before))
    return sorted(due, key=lambda row: row[1] - row[2], reverse=True)


def merge(world, into: str, *others: str) -> int:
    """Make several tags one: everything carrying any of them ends up carrying the first.

    Deduplication proper — not the shapes of one word, which are already one tag, but two words a
    person used for one idea. It is an ordinary write, so it is stated, reversible and visible in
    the record; and it is done because somebody decided, never because the world felt like it.
    """
    run_script(world.store.conn, SCHEMA)
    keep = canonical(into)
    losing = {canonical(other) for other in others} - {keep}
    if not losing:
        return 0
    changed = 0
    for tag in losing:
        for entity in tagged(world, tag):
            kept = [t for t in tags_of(entity) if canonical(t) not in losing]
            if keep not in [canonical(t) for t in kept]:
                kept.append(keep)
            entity.tags = kept
            world.save(entity)
            changed += 1
        world.store.conn.execute("DELETE FROM tag_reviews WHERE tag = ?", (tag,))
    reviewed(world, keep)
    return changed


def remove(world, tag: str, *, among: list | None = None) -> int:
    """Take a tag off everything, or off the ones given. The other half of tagging.

    A tag put on in March stops meaning anything by September, or was a mistake to begin with.
    Taking it off is an ordinary write — stated, reversible, visible — and it is done because
    somebody said so, never because the world decided the tag had gone stale.
    """
    run_script(world.store.conn, SCHEMA)
    gone = canonical(tag)
    changed = 0
    for entity in (among if among is not None else tagged(world, gone)):
        kept = [t for t in tags_of(entity) if canonical(t) != gone]
        if len(kept) != len(tags_of(entity)):
            entity.tags = kept
            world.save(entity)
            changed += 1
    world.store.conn.execute("DELETE FROM tag_reviews WHERE tag = ?", (gone,))
    return changed


def all_of(world, *wanted: str) -> list:
    """Everything carrying every one of these tags — the narrowing that makes tags useful.

    One tag gathers; two pick out. "Everyone from the conference who is also in Berlin" is the
    question a person actually asks, and it is an intersection, not a search."""
    if not wanted:
        return []
    sets = [{e.id: e for e in tagged(world, tag)} for tag in wanted]
    shared = set.intersection(*(set(group) for group in sets)) if sets else set()
    return [sets[0][entity_id] for entity_id in shared]


def suggest(world, entity, limit: int = 3) -> list[tuple[str, float]]:
    """Tags worth considering for this one, from whatever else reads like it.

    Candidates and their strength, nothing applied. What earns a tag is a judgement about what
    this person means by the word, and the host — or the model, on the agenda — makes it.
    """
    close = world.meanings.similar(world, entity, limit=8)
    mine = {canonical(t) for t in tags_of(entity)}
    scored: dict = {}
    for other, _, score in close:
        for tag in tags_of(other):
            clean = canonical(tag)
            if clean not in mine:
                scored[clean] = max(scored.get(clean, 0.0), round(score, 3))
    return sorted(scored.items(), key=lambda pair: -pair[1])[:limit]
