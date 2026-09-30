"""Look at one link properly, once, with everything the world knows about it.

The world checks a link against its own record — the run of its type, a cycle, a second holder
where one is allowed. What it cannot check is whether the link says what somebody meant: a
`capital_of` written from the country instead of the city is a wrong fact and reads as a
perfectly ordinary row. Measured on a hundred-fact world, that was the commonest wrong fact
left standing once the ones that never landed were fixed.

So: hand the whole link to one of the two outside parties and ask three things about it.

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
What it says is kept as a question on the link, which is how everything uncertain in
this world is kept: it outlives the run, it is asked once, and answering it closes it.

The party is passed in. Nemotron through Token Factory is the one this was written for; Jev
answers the direction question with calibrated probabilities and is the one it was measured on.
Neither is required — a world with neither simply does not run this.
"""
import hashlib
from terraweaver import prompts
import json
import logging
from datetime import datetime, timezone

from terraweaver.store import run_script

# One failure must not stop the world, and that is not the same thing as nobody ever hearing
# about it. Measured 2026-09-30: an engineer that answers `.json(...)` was called as a function,
# the TypeError went into a bare `except`, and `look_at_types` read 0 of 28 types in every world
# ever served. The policy stays; the silence goes.
log = logging.getLogger("terraweaver")

# How long an outside party is given before the world stops waiting for it. Measured on the
# naming question: most answers come back in four or five seconds and one in several takes
# twenty. So most are had for nothing and the slow one is not paid for in a host's patience —
# it is marked unread and picked up by a later pass, which is what `unread` and `unread_types`
# are for. A host's own run is stopped after ten seconds, so nothing that waits this long may
# be called from inside one.
TTL = 10.0

# What the inspector checks, in one place, so the answer to "what does it look at" is read
# rather than reconstructed. `how` is the thing that decides the cost and the trust:
#
#   deterministic — the world works it out from its own record. Free, certain, and the only
#                   kind that may correct anything by itself.
#   closed        — one question with named options, to the picker. Cheap, calibrated,
#                   and the volume: one per link.
#   open          — a word has to be invented. Expensive, so once per type, never per link.
#
# `fixes` says whether a finding may be acted on or only said. Only a deterministic finding may
# be acted on, and only where it is certain: what an outside party makes of the words is one
# more account of the fact, and the person's own account outranks it. Nothing is said when
# nothing was changed — the agent does not need to hear that all is well. What was changed is
# said, because a fact that turned round while nobody was looking is one the agent can no
# longer account for.
CHECKLIST = (
    {"name": "twin_type", "on": "type", "how": "deterministic", "fixes": False,
     "asks": "two types read as one idea — take one into the other, or say how they differ"},
    {"name": "ends_named", "on": "type", "how": "deterministic", "fixes": False,
     "asks": "the type does not say what its two ends are, so no link of it can be checked"},
    {"name": "ends_could_be", "on": "type", "how": "open", "fixes": False,
     "asks": "what each end is, in words a thing can be checked against"},
    {"name": "name_says_direction", "on": "type", "how": "open", "fixes": False,
     "asks": "the word does not say which end it starts from; a clearer one would"},
    {"name": "against_the_run", "on": "link", "how": "deterministic", "fixes": True,
     "asks": "this link runs the opposite way to the rest of its type — turned where the run "
             "is unambiguous (one against five or more), asked about otherwise"},
    {"name": "ends_fit_their_roles", "on": "link", "how": "closed", "fixes": False,
     "asks": "whether each end is the kind of thing that belongs at its end"},
)

# Never any of them. Whether a fact is TRUE is not the inspector's business and must not become
# it: this world holds what the person said, a benchmark of it holds deliberate absurdities on
# purpose, and a capital really does get moved. What is read from outside about the truth of a
# fact is kept as a remark and never as grounds for anything.
NOT_CHECKED = "whether the fact is true"

SCHEMA = """
CREATE TABLE IF NOT EXISTS link_checks (
    link_id TEXT NOT NULL,
    digest TEXT NOT NULL,      -- the link as it was when read; changed, it is read again
    looked_at TEXT NOT NULL,
    reader TEXT NOT NULL,        -- which party looked: the engineer or the picker
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
    """Everything the world holds about one link, in the form it is given in.

    Both ends by name and by class and by whatever was said about them, the type by its name and
    description and the words for its ends, and the link's own description. A party given only
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


def note(world, link, account: dict, looked_by: str, verdict: str, said: str = "",
         can_ask: bool = True) -> None:
    """Mark the link as read, and keep what was said about it where it can be answered.

    `can_ask=False` for a pass with nobody to answer — a sweep over an old world, a nightly
    run. The finding is still written down, so the same link is not read twice and a later pass
    with somebody there can put the question; it simply is not put to an agent that is not
    listening. A question nobody is there for is not caution, it is a queue.
    """
    run_script(world.store.conn, SCHEMA)
    world.store.conn.execute(
        "INSERT OR REPLACE INTO link_checks (link_id, digest, looked_at, reader, verdict, said) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (link.id, digest_of(account), datetime.now(timezone.utc).isoformat(), looked_by,
         verdict, said))
    world.store.conn.commit()
    if verdict == "right" or not can_ask:
        return
    # Kept as a question, not acted on. A party outside the world is one more account of the
    # fact, and the person's own account outranks it — the world says what it noticed and the
    # host decides, which is the rule everything unasked in this world is held to.
    world.questions.raise_(
        link, f"read as {verdict}", said or f"read from outside as {verdict}",
        options=(["it is backwards — record it the other way and retract this one",
                  "it is right as written"] if verdict == "reversed" else
                 ["these two do not stand in this relation — retract it",
                  "it is right as written"]))


def look(world, ask, looked_by: str = "outside", limit: int = 200,
         can_ask: bool = True) -> dict:
    """Read every link nobody has read yet. `ask(account) -> (verdict, said)`.

    `can_ask=False` reads and records without putting anything to an agent — see `note`.
    """
    tally = {"right": 0, "reversed": 0, "impossible": 0, "unsure": 0, "failed": 0}
    for link, account in unread(world, limit):
        try:
            verdict, said = ask(account)
        except Exception as wrong:  # noqa: BLE001 - one that fails is not a world that fails
            log.debug("look: %s could not be read: %r", getattr(link, "id", link), wrong,
                      exc_info=True)
            tally["failed"] += 1
            continue
        if verdict not in tally:
            verdict = "unsure"
        tally[verdict] += 1
        note(world, link, account, looked_by, verdict, said, can_ask=can_ask)
    return tally


def type_account(world, name: str) -> dict | None:
    """One link type as it is handed over: its word, what it says it is, its ends, its use."""
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

    A word is the whole of what a type offers whoever comes to it later: `Author` does not say
    which end it starts from, `Plays` does not say what is played, `Related` says nothing at all.
    The engineer is asked for a clearer word, and nothing is renamed — a name that can be changed afterwards
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
        except Exception as wrong:  # noqa: BLE001 - one that fails is not a world that fails
            log.debug("naming: %s could not be read: %r", name, wrong, exc_info=True)
            continue
        if said and not said.get("clear", True):
            out.append({**said, "class": name, "kind": account["kind"]})
    return out


TYPE_CHECKS = """
CREATE TABLE IF NOT EXISTS type_checks (
    class_name TEXT PRIMARY KEY,
    looked_at TEXT,
    reader TEXT,               -- which party looked
    said TEXT                  -- JSON: what the engineer offered, or null while nobody has looked
);
"""


def engineer_of(world):
    """The engineer this world was given, or None. A world without one simply skips.

    What comes back answers `.say(system, asked)` and `.json(system, asked)` — an
    `outside.Open`. It is not a function, and anything here that wants a question asked wraps it
    in the asker for that question (`outside.namer` for the ends of a type). Calling it directly
    raises `TypeError`, which is how this whole pass was dead in the served world until
    2026-09-30 — see docs/code-review-2026-09-30.md, finding 3.4.1.
    """
    return getattr(world, "engineer", None)


def names_asker(world, ask=None):
    """The thing that answers `ask(account) -> dict` about the ends of a type.

    Given one, it is used as it is — that is how the tests and the experiments pass a stub in.
    Otherwise the world's engineer is wrapped in `outside.namer`, which is the adapter from
    `.json(system, asked)` to this question.
    """
    if ask is not None:
        return ask
    engineer = engineer_of(world)
    if engineer is None:
        return None
    if callable(engineer) and not hasattr(engineer, "json"):
        return engineer
    from terraweaver import outside

    return outside.namer(engineer)


def on_new_type(world, name: str) -> list[str]:
    """Look at a type the moment it is defined, while the host is still holding the pen.

    This is the one moment the correction is cheap. A type is defined once and every link
    written under it inherits whatever was wrong with it — a word that does not say which end
    starts, a second word for an idea the world already has. Found a hundred facts later, the
    links are already written and somebody has to go back over them; found here, it is one more
    argument on the call being made.

    Nothing is refused and nothing is changed: what comes back is said to the host, which is
    the rule everything the world notices is held to. If no engineer is configured, or it does
    not answer in time, the type is marked as unread and `unread_types` finds it later — the
    check is worth doing late, and never worth making the host wait.
    """
    run_script(world.store.conn, TYPE_CHECKS)
    lines = []
    for a, b, score in twins(world):
        if name in (a, b):
            other = b if a == name else a
            lines.append(
                f"{name} reads almost exactly like {other} ({score}). If they are one idea, "
                f"the world should hold one word for it: world.take_in({other}, \"<the word "
                f"{name} was written with>\") moves the links across. If they are two ideas, "
                f"say so in the descriptions — that is what tells them apart later.")
    # Nothing that talks to the outside happens here. A host's run is stopped after ten
    # seconds and an engineer that thinks before it answers takes longer than that, so asking one
    # from inside a run is asking for the run to die — which is the opposite of the point. What
    # the world can do for free it does now; the rest is marked unread and done at the close,
    # where nothing is waiting. The user's rule: online where it keeps up, deferred with a mark
    # where it does not.
    world.store.conn.execute(
        "INSERT OR IGNORE INTO type_checks (class_name, looked_at, reader, said) "
        "VALUES (?, NULL, NULL, NULL)", (name,))
    world.store.conn.commit()
    return lines


def look_at_types(world, limit: int = 20, can_ask: bool = True) -> dict[str, list[str]]:
    """Read the types nobody has read, and say what the engineer offered. Called at the close.

    Here there is no ten-second limit and the host is between pieces of work, which is where
    everything else this world asks for is asked. One open question per type, asked once.
    """
    run_script(world.store.conn, TYPE_CHECKS)
    ask = names_asker(world)
    if ask is None:
        return {}
    out: dict[str, list[str]] = {}
    for name in unread_types(world)[:limit]:
        account = type_account(world, name)
        if account is None:
            continue
        try:
            said = ask(account)
        except Exception as wrong:  # noqa: BLE001 - one that fails is not a world that fails
            log.debug("look_at_types: %s could not be read: %r", name, wrong, exc_info=True)
            continue
        # Written in either way: a blank filled is not a question, and a pass with nobody
        # listening still leaves the type checkable for the next one. So it is called for what it
        # writes, and what it would have said is dropped when nobody is listening — as a
        # statement, not as a boolean expression standing in for one.
        offered = _what_it_offered(name, account, said, world)
        lines = offered if can_ask else []
        world.store.conn.execute(
            "INSERT OR REPLACE INTO type_checks (class_name, looked_at, reader, said) "
            "VALUES (?, ?, ?, ?)",
            (name, datetime.now(timezone.utc).isoformat(), "outside",
             json.dumps(said) if said else None))
        if lines:
            out[name] = lines
    world.store.conn.commit()
    return out


def name_the_ends(world, name: str, subject_is: str, object_is: str,
                  said_by: str = "outside") -> bool:
    """Write what each end of a type is. Safe to do without asking, and this is why.

    A role is not a statement. Nothing in the record is written under it and nothing already
    said changes meaning when it is filled in — it says how a link of this type is to be
    *checked*, which is the world's own bookkeeping. Compare an attribute's type or an entity's
    name, where everything already recorded was recorded meaning the old one and no later
    telling repairs that: those are refused, and this is not.

    Only where nobody has said them. A type whose ends the host named keeps what the host said;
    the disagreement is put to the host instead, because there the world would be overruling
    somebody rather than filling a blank.
    """
    cls = world.classes.get(name)
    rel = cls._spec.get("relation") if cls else None
    # Not the free type. It is what a bare link is an instance of — anything to anything, by
    # construction — so names for its two ends say nothing and would be read as a rule for
    # checking every untyped link in the world (docs/code-review-2026-09-30.md 3.4.12).
    if not rel or rel.get("free") or rel.get("roles") or not (subject_is and object_is):
        return False
    # Who said it, kept beside it. Not so the class can be treated as a lesser kind — a class
    # is a class here and where it came from changes nothing about how it works — but because
    # "read from outside" and "the person said so" are different weights of evidence, and the
    # only place that difference can live is on the thing itself. What may honestly differ
    # between two classes is how settled each is, and that is read from what has accumulated
    # under it, not from who wrote it down first.
    rel["roles"] = [{"name": subject_is, "inverse": object_is, "said_by": said_by}]
    grow = (world.extras or {}).get("define_relation")
    made = getattr(grow, "__self__", None)
    if made is not None and hasattr(made, "_save"):
        made._save(cls._spec)        # so the world reopened tomorrow still knows them
    return True


def _what_it_offered(name: str, account: dict, said: dict | None, world=None) -> list[str]:
    lines: list[str] = []
    if said:
        if said.get("subject_is") and not (account or {}).get("subject_is"):
            written = world is not None and name_the_ends(
                world, name, said["subject_is"], said["object_is"])
            lines.append(
                (f"Nothing said what the two ends of {name} are, so nothing could tell a link "
                 f"of it written backwards from one written right. Read from outside and "
                 f"written down: subject_is=\"{said['subject_is']}\", "
                 f"object_is=\"{said['object_is']}\". They are how links of this type will be "
                 f"checked from now on, not a claim about any fact — say them yourself on "
                 f"define_relation if these are wrong."
                 if written else
                 f"Nothing says what the two ends of {name} are, and without that no later "
                 f"reading can tell a link written backwards from one written right. Read from "
                 f"outside, they look like: subject_is=\"{said['subject_is']}\", "
                 f"object_is=\"{said['object_is']}\". Say them if they are right — it is one "
                 f"more argument on define_relation and it is what makes the type checkable."))
        if said.get("clear_name") and said["clear_name"] not in (name, account.get("kind")):
            lines.append(
                f"The word {account.get('kind')!r} does not say which end it starts from; "
                f"{said['clear_name']!r} would. Nothing is renamed here — define the clearer "
                f"word and world.take_in it, which moves the links and leaves the record saying "
                f"what it always said.")
    return lines


def unread_types(world) -> list[str]:
    """Types nobody has looked at yet — what a deferred pass over the world would pick up.

    Every relation type, not only the ones this world wrote for itself. There was a version
    that split them, on the grounds that what the world ships with is not the host's to fix —
    and that is not a distinction the world has. A class is a class; a type whose ends are not
    named cannot have its links checked, and it makes no difference who wrote it. Where the
    answer is worth keeping it goes beside the core file rather than into it, which is what
    `growth` is for: the core is read as it is and never written to, and additions live beside
    it and are merged in.
    """
    run_script(world.store.conn, TYPE_CHECKS)
    looked = {r[0] for r in world.store.conn.execute(
        "SELECT class_name FROM type_checks WHERE looked_at IS NOT NULL")}
    return [n for n, c in sorted(world.classes.items())
            if c._spec.get("relation") and n not in looked]


# How long a run has to be before a single link going the other way is taken as a mistake
# rather than as the second of two readings. Five against one: at two or three the majority is
# not a majority, and it is at two or three that a type is young — which is where every reversal
# in the measured run was written. The number is deliberately dull; being late is cheap here and
# being wrong is not.
A_RUN = 5


def turn_the_odd_ones(world, least_run: int = A_RUN) -> list[str]:
    """Turn a link that runs against an unambiguous run of its own type, and say so.

    The one thing in this file that changes anything. It is allowed to because it is
    deterministic — counted from the world's own links, not read from outside — and because it
    is held to the narrow case: exactly one link going one way against at least five going the
    other. Anything less clear is a question, not a correction.

    Nothing is said when nothing was changed. What was changed is said, because a fact that
    turned round while nobody was looking is a fact the agent can no longer account for, and a
    remark on the link keeps the reason where the next reader will find it.
    """
    from terraweaver import ontology, relations

    turned = []
    try:
        found = relations.verify(world, least=2)
    except Exception as wrong:  # noqa: BLE001 - a check must never be what stops the world
        log.debug("put_the_clear_ones_round: verify failed: %r", wrong, exc_info=True)
        return []
    for one in found:
        if one.get("about") != "against the run of its type" or one.get("tied"):
            continue
        if one.get("seen") != 1 or one.get("usual", 0) < least_run:
            continue
        for link_id in one.get("links", []):
            try:
                link = world.store.load(link_id, world.classes)
            except Exception as wrong:  # noqa: BLE001
                log.debug("put_the_clear_ones_round: %s would not load: %r", link_id, wrong,
                          exc_info=True)
                continue
            if link is None:
                continue
            was = link.display_name()
            with ontology.trusted_writes():
                link.subject, link.object = link.object, link.subject
                world.save(link)
            with ontology.stating("world"):
                link.describe(
                    f"turned round by the world: it was written {was}, and {one['usual']} other "
                    f"links of this type run the other way with none beside this one")
            turned.append(f"{was}  ->  {link.display_name()}")
    return turned


def twins(world, close: float = 0.82) -> list[tuple]:
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
    # Through the index, so a word already seen costs nothing: this runs from `on_new_type`,
    # inside the host's own run, and re-embedding the whole vocabulary there was a network call
    # per `define_relation` (docs/code-review-2026-09-30.md 3.4.3).
    held = world.meanings.vectors_for([(f"type:{name}", text) for name, text in said])
    vectors = [held.get(f"type:{name}") for name, _ in said]
    pairs = []
    for i in range(len(said)):
        for j in range(i + 1, len(said)):
            a, b = vectors[i], vectors[j]
            if a is None or b is None:
                continue
            score = sum(x * y for x, y in zip(a, b))
            if score >= close:
                pairs.append((said[i][0], said[j][0], round(score, 3)))
    return sorted(pairs, key=lambda p: -p[2])


# How many of a kind before the world can say what one of them is. One is an example and
# writing from it gives a line about that example — "the Finnish bat-and-ball game" where
# "what sort of sport and where it is played" was wanted. Three is a kind.
A_FEW = 3

WRITING = prompts.WRITING

WRITE_ONE = prompts.WRITE_ONE


def silent_classes(world, least: int = A_FEW) -> list[str]:
    """Classes with no line of their own and enough of them here to say what one is."""
    from terraweaver import ontology

    out = []
    for name, cls in sorted(world.classes.items()):
        spec = cls._spec
        if spec.get("what_to_say") or spec.get("own") or spec.get("relation"):
            continue
        if not spec.get("parent"):
            continue      # a root with nothing above it: its line is written by hand, on purpose
        if len(world.all(name, limit=least, history=True)) >= least:
            out.append(name)
    return out


def write_the_questions(world, engineer=None, least: int = A_FEW, limit: int = 5) -> list[str]:
    """Write the asking line for classes that have none, from what has accumulated under them.

    Offline work, and it has to be: a class is born in the middle of reading one thing, and one
    thing is an example. What a kind is shows in several of them, so this waits until there are
    several and then writes from all of them at once — the same order everything else here
    follows, accept what arrives, see the shape later.

    Until then the class inherits its parent's line, which is the honest answer: nothing more
    particular is known about these than that they are things.
    """
    from terraweaver import ontology

    engineer = engineer or engineer_of(world)
    if engineer is None:
        return []
    written = []
    for name in silent_classes(world, least)[:limit]:
        cls = world.classes[name]
        spec = cls._spec
        here = world.all(name, limit=12, history=True)
        said = []
        for one in here:
            words = [t for t in (getattr(one, "descriptions", None) or []) if isinstance(t, str)]
            said.append(f"    {one.display_name()} — {words[0][:110] if words else '(nothing said)'}")
        got = engineer.json(WRITING, WRITE_ONE.format(
            name=name, description=(spec.get("description") or "")[:200],
            parent=spec.get("parent"),
            inherited=ontology.what_to_say(world.classes[spec["parent"]], world.classes)
            if spec.get("parent") in world.classes else ontology.SAY_SOMETHING,
            attributes=", ".join(a["name"] for a in spec["attributes"] if "derived" not in a),
            count=len(here), said="\n".join(said)))
        line = (got or {}).get("what_to_say")
        if not isinstance(line, str) or not line.strip():
            continue
        _keep_the_line(world, name, line.strip())
        written.append(f"{name}: {line.strip()}")
    return written


def _keep_the_line(world, name: str, line: str) -> None:
    """Put it everywhere a spec is read from, and on disk if this world keeps its specs there."""
    import json
    from pathlib import Path

    world.classes[name]._spec["what_to_say"] = line
    specs = getattr(world, "specs", None)
    if isinstance(specs, dict) and name in specs:
        specs[name]["what_to_say"] = line
    where = getattr(world, "grown_dir", None)
    if where:
        path = Path(where) / f"{name}.json"
        if path.exists():
            spec = json.loads(path.read_text())
            spec["what_to_say"] = line
            path.write_text(json.dumps(spec, indent=2) + "\n")
