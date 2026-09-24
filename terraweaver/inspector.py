"""Look at one link properly, once, with everything the world knows about it.

The world checks a link against its own record — the run of its type, a cycle, a second holder
where one is allowed. What it cannot check is whether the link says what somebody meant: a
`capital_of` written from the country instead of the city is a wrong fact and reads as a
perfectly ordinary row. Measured on a hundred-fact world, that was the commonest wrong fact
left standing once the ones that never landed were fixed.

So: hand the whole link to a reader outside the world and ask three things about it.

**Which way it runs.** Not whether it is true — this record deliberately holds claims that
contradict common knowledge, and those are what it exists to keep. Whether each end is the kind
of thing that belongs at its end. "Rome capital of Japan" is well formed and false; "Japan
capital of Rome" is malformed. Only the second is the world's business.

**Whether the type is the right word**, and whether the world already has one that means the
same. A recorder builds its vocabulary as it meets the words and has no way to look back: one
run held `Plays` beside `PlaysPosition`, `Created` beside `CreatedBy`. Two words for one idea
answer for neither.

**Once.** A link checked is a link marked, and a link that has not changed since is not asked
about again — the mark is over the link's own content, so an end that moves is asked afresh.
What the reader says is kept as a question on the link, which is how everything uncertain in
this world is kept: it outlives the run, it is asked once, and answering it closes it.

The reader is passed in. Nemotron through Token Factory is the one this was written for; Jev
answers the direction question with calibrated probabilities and is the one it was measured on.
Neither is required — a world with no reader simply does not run this.
"""
import hashlib
import json
from datetime import datetime, timezone

from terraweaver.store import run_script

SCHEMA = """
CREATE TABLE IF NOT EXISTS link_checks (
    link_id TEXT NOT NULL,
    digest TEXT NOT NULL,      -- the link as it was when read; changed, it is read again
    looked_at TEXT NOT NULL,
    reader TEXT NOT NULL,
    verdict TEXT NOT NULL,     -- right | reversed | impossible | unsure
    said TEXT,
    PRIMARY KEY (link_id, digest)
);
CREATE INDEX IF NOT EXISTS idx_link_checks ON link_checks(link_id);
"""


def digest_of(account: dict) -> str:
    """What was read, as a short string — so a link nobody has touched is not read twice."""
    return hashlib.sha256(json.dumps(account, sort_keys=True).encode()).hexdigest()[:16]


def account_of(world, link) -> dict | None:
    """Everything the world holds about one link, in the form a reader is given it.

    Both ends by name and by class and by whatever was said about them, the type by its name and
    description and the words for its ends, and the link's own description. A reader given only
    "Author: a → b" has to guess what a and b are; given "a is a Person described as the writer
    of six novels" it does not.
    """
    spec = type(link)._spec
    rel = spec.get("relation")
    if not rel:
        return None
    try:
        ends = (link.subject, link.object)
    except AttributeError:
        return None
    if ends[0] is None or ends[1] is None:
        return None

    def about(entity) -> dict:
        said = (getattr(entity, "name", None) or getattr(entity, "full_name", None)
                or getattr(entity, "title", None))
        return {"name": str(said) if said else entity.display_name(),
                "class": type(entity).__name__,
                "described": [str(getattr(t, "text", t))
                              for t in (getattr(entity, "descriptions", None) or [])][:3]}

    roles = (rel.get("roles") or [{}])[0]
    return {
        "kind": rel.get("kind", type(link).__name__),
        "type_is": spec.get("description", ""),
        "subject_is": roles.get("name") or "",
        "object_is": roles.get("inverse") or "",
        "subject": about(ends[0]),
        "object": about(ends[1]),
        "link_described": [str(getattr(t, "text", t))
                           for t in (getattr(link, "descriptions", None) or [])][:3],
    }


def unread(world, limit: int = 200) -> list:
    """Links nobody has looked at, or whose ends have moved since they were looked at."""
    run_script(world.store.conn, SCHEMA)
    seen = {(r[0], r[1]) for r in
            world.store.conn.execute("SELECT link_id, digest FROM link_checks")}
    out = []
    for name, cls in sorted(world.classes.items()):
        if not cls._spec.get("relation"):
            continue
        for link in world.all(cls, limit=None, history=True):
            account = account_of(world, link)
            if account is None:
                continue
            if (link.id, digest_of(account)) in seen:
                continue
            out.append((link, account))
            if len(out) >= limit:
                return out
    return out


def note(world, link, account: dict, reader: str, verdict: str, said: str = "") -> None:
    """Mark the link as read, and keep what was said about it where it can be answered."""
    run_script(world.store.conn, SCHEMA)
    world.store.conn.execute(
        "INSERT OR REPLACE INTO link_checks (link_id, digest, looked_at, reader, verdict, said) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (link.id, digest_of(account), datetime.now(timezone.utc).isoformat(), reader,
         verdict, said))
    world.store.conn.commit()
    if verdict == "right":
        return
    # Kept as a question, not acted on. A reader outside the world is one more account of the
    # fact, and the person's own account outranks it — the world says what it noticed and the
    # host decides, which is the rule everything unasked in this world is held to.
    world.questions.raise_(
        link, f"read as {verdict}", said or f"read from outside as {verdict}",
        options=(["it is backwards — record it the other way and retract this one",
                  "it is right as written"] if verdict == "reversed" else
                 ["these two do not stand in this relation — retract it",
                  "it is right as written"]))


def look(world, ask, reader: str = "outside", limit: int = 200) -> dict:
    """Read every link nobody has read yet. `ask(account) -> (verdict, said)`."""
    tally = {"right": 0, "reversed": 0, "impossible": 0, "unsure": 0, "failed": 0}
    for link, account in unread(world, limit):
        try:
            verdict, said = ask(account)
        except Exception as wrong:  # noqa: BLE001 - a reader that fails is not a world that fails
            tally["failed"] += 1
            continue
        if verdict not in tally:
            verdict = "unsure"
        tally[verdict] += 1
        note(world, link, account, reader, verdict, said)
    return tally


def type_account(world, name: str) -> dict | None:
    """One link type as a reader is given it: its word, what it says it is, its ends, its use."""
    cls = world.classes.get(name)
    rel = cls._spec.get("relation") if cls else None
    if not rel:
        return None
    roles = (rel.get("roles") or [{}])[0]
    examples = []
    for link in world.all(cls, limit=3, history=True):
        try:
            a = getattr(link.subject, "name", None) or getattr(link.subject, "full_name", None)
            b = getattr(link.object, "name", None) or getattr(link.object, "full_name", None)
        except AttributeError:
            continue
        if a and b:
            examples.append(f"{a} {rel['kind'].replace('_', ' ')} {b}")
    return {"class": name, "kind": rel.get("kind", name),
            "type_is": cls._spec.get("description", ""),
            "subject_is": roles.get("name") or "", "object_is": roles.get("inverse") or "",
            "nature": rel.get("nature", ""), "examples": examples}


def naming(world, ask, only: set | None = None) -> list[dict]:
    """Ask whether each type's word says plainly what the link is. `ask(account) -> dict`.

    A word is the whole of what a type offers a later reader: `Author` does not say which end it
    starts from, `Plays` does not say what is played, `Related` says nothing at all. The reader
    is asked for a clearer word, and nothing is renamed — a name that can be changed afterwards
    makes every statement written under the old one unreadable in the way it was written. The
    honest rename is `world.define_relation(<the clear word>, ...)` and then
    `world.take_in(<it>, "<the old word>")`, which moves the links across and leaves the record
    saying what it always said.
    """
    out = []
    for name in sorted(world.classes):
        if only is not None and name not in only:
            continue
        account = type_account(world, name)
        if account is None:
            continue
        try:
            said = ask(account)
        except Exception:  # noqa: BLE001 - a reader that fails is not a world that fails
            continue
        if said and not said.get("clear", True):
            out.append({**said, "class": name, "kind": account["kind"]})
    return out


def twins(world, close: float = 0.86) -> list[tuple]:
    """Types that read like each other: two words for one idea, which answer for neither.

    By meaning, over the name and description together, the way `classes_like` finds a class —
    the recorder that wrote `Plays` beside `PlaysPosition` had no way to look back and see it.
    Reported, never merged: whether two words are one idea depends on what the person said,
    which the host has and the world does not. `world.take_in(<the type>, "<the word>")` is what
    moves the links across once somebody decides.
    """
    said = []
    for name, cls in sorted(world.classes.items()):
        rel = cls._spec.get("relation")
        if rel:
            said.append((name, f"{rel.get('kind', name)}. {cls._spec.get('description', '')}"))
    if len(said) < 2:
        return []
    vectors = world.meanings.model.embed([text for _, text in said])
    pairs = []
    for i in range(len(said)):
        for j in range(i + 1, len(said)):
            a, b = vectors[i], vectors[j]
            score = sum(x * y for x, y in zip(a, b))
            if score >= close:
                pairs.append((said[i][0], said[j][0], round(score, 3)))
    return sorted(pairs, key=lambda p: -p[2])
