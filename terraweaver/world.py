"""The world as the agent sees it: query and write entities without touching storage.

`identify()` is the important one — it settles who a task is about before anything is
written about them. It searches and hands back who could be meant; the host reads them and
picks, because the host has the conversation and the world does not. A name nobody here has
is recorded by that same call, because there was no other branch to take.

Writes do not identify. `new()` and `ensure()` take the name they are given: a question in
the middle of a block stops the run and settles nothing, and what two records have in common
is seen better later, over the record, with the whole world in view.
"""
import json
import logging
from typing import Any

from terraweaver import matching, ontology, resolution, timeutil, values
from terraweaver.comments import Comments
from terraweaver.history import ValueHistory
from terraweaver.facts import Facts, THE_PARTIES
from terraweaver.meaning import Meanings
from terraweaver.procedures import Procedures
from terraweaver.questions import Questions
from terraweaver.usage import Usage
from terraweaver.resolution import (
    SKILL_KINDS,
    NeedsResolution,
    ResolutionRequired,
    ambiguous_identity,
    contradicting_value,
)


CHOICES_SCHEMA = """
CREATE TABLE IF NOT EXISTS name_choices (
    class_name TEXT NOT NULL,
    name TEXT NOT NULL,          -- the name as normalized by matching
    entity_id TEXT NOT NULL,
    chosen_at TEXT NOT NULL,
    PRIMARY KEY (class_name, name)
);
"""



log = logging.getLogger("terraweaver")

class NotInWorld(LookupError):
    """get() found nothing: the entity the host meant isn't in the world."""


def _ask_its_nature(instance, class_name: str, attrs: dict) -> None:
    """A thing whose sort is unknown is asked about, with the answer written out.

    The world can say a great deal about a place and nothing at all about "a thing": that a place
    contains places, that an event has a time, that nothing owns an abstraction. Left unasked it
    is never said, because a host records the fact and moves on — so the question comes with the
    line that answers it.
    """
    declared = next((a for a in type(instance)._spec["attributes"] if a["name"] == "nature"), None)
    if declared is None or attrs.get("nature") or getattr(instance, "nature", None):
        return
    choices = declared["type"][len("enum["):-1]
    ontology.note_hint(
        f"{instance.display_name()} is new and I don't know what sort of thing it is. "
        f"{class_name}.ensure(name=..., nature=...) takes one of: {choices} — or say it now: "
        f"{instance.display_name().split()[0].lower()}.nature = \"place\". Knowing it is what "
        f"lets me answer about where something is, when it was, and what can own what."
    )


class World:
    def __init__(self, store, classes: dict[str, type], specs: dict | None = None, *,
                 selves: bool = True):
        self.store = store
        self.classes = classes
        # What each class declares — how many of a thing a slot holds, and so on. Assembly needs
        # it to build images; without it every slot is treated as holding one thing.
        # As the classes read them: a spec that called its name `full_name` is read with `name`,
        # or a lookup is checked against a word the class no longer has.
        self.specs = ({name: ontology.one_name(spec) for name, spec in specs.items()} if specs
                      else {name: cls._spec for name, cls in classes.items()})
        self.resolutions: list[dict] = []
        # Said once per class, not once per read: a link that lost an end is news, and the same
        # news forty times over is noise.
        self._said_about_ends: set[str] = set()
        # Classes whose listing came back empty while something is a kind of them; said once each.
        self._said_about_kinds: set[str] = set()
        # Host-facing calls a mode adds on top of the core — an experiment that lets the host
        # define its own classes needs `define(...)` where nothing in the core offers one. Kept
        # in a named place rather than bolted onto the facade, so what is ours and what a mode
        # brought is always distinguishable, and so `world` still lists everything it can do.
        self.extras: dict[str, Any] = {}
        self.pending: NeedsResolution | None = None
        self.comments = Comments(store, classes)
        # Who the user meant by a name, once they said so. The next "Annie" is that Annie —
        # announced, never silent, so the user can correct it.
        store.conn.executescript(CHOICES_SCHEMA)
        # Every overwrite of a known entity's attribute leaves the old value in history.
        self.history = ValueHistory(store, classes)
        self.facts = Facts(store.conn)
        self._one_name()
        self.usage = Usage(store)
        self.procedures = Procedures(store)
        self.meanings = Meanings(store)
        self.questions = Questions(store, classes, self.usage)
        ontology.set_write_guard(self._keep_old_value)
        # Lets `Person.find(...)` reach this world without each class carrying a store.
        ontology.set_world(self)
        # A world with no classes has no Person to be the owner and no Agent to keep it. It is
        # not broken, it is empty: whoever fills it names those two itself.
        if selves:
            self.ensure_selves()

    def _one_name(self) -> None:
        """A world written while a person had a `full_name` and an event a `title` is brought over.

        Once, on the way in, the way `migrate_times` brings over a moment written as text: the
        record's statements and the images say `name` from now on. Nothing is dropped — where an
        image has both, the one with a value is kept. Opening the world again finds nothing to do.
        """
        conn = self.store.conn
        tables = {n for (n,) in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
        moved = 0
        for class_name, old in ontology.NAMED_OTHERWISE.items():
            if class_name not in self.classes:
                continue
            ids = [i for (i,) in conn.execute(
                "SELECT id FROM instances WHERE class_name = ?", (class_name,))] \
                if "instances" in tables else []
            if not ids:
                continue
            marks = ",".join("?" * len(ids))
            for table in self.facts.tables():
                moved += conn.execute(
                    f'UPDATE "{table}" SET slot = ? WHERE slot = ? AND subject IN ({marks})',
                    (matching.NAME, old, *ids)).rowcount
            if "value_history" in tables:
                conn.execute(f"UPDATE value_history SET attr = ? WHERE attr = ? "
                             f"AND instance_id IN ({marks})", (matching.NAME, old, *ids))
            if class_name in tables:
                rows = conn.execute(f'SELECT instance_id, value FROM "{class_name}" WHERE attr = ?',
                                    (old,)).fetchall()
                for instance_id, value in rows:
                    held = conn.execute(
                        f'SELECT value FROM "{class_name}" WHERE instance_id = ? AND attr = ?',
                        (instance_id, matching.NAME)).fetchone()
                    if held is None or held[0] in (None, "null"):
                        conn.execute(f'INSERT OR REPLACE INTO "{class_name}" (instance_id, attr, value) '
                                     f'VALUES (?, ?, ?)', (instance_id, matching.NAME, value))
                    moved += 1
                conn.execute(f'DELETE FROM "{class_name}" WHERE attr = ?', (old,))
        if moved:
            conn.commit()
            log.info("brought %d name(s) over to `name` from the words an older world used", moved)

    # Fixed ids, so the two of them are the same rows in every world and can be found without
    # searching by name — and so nothing else can quietly take their place.
    USER_ID, AGENT_ID = THE_PARTIES

    def ensure_selves(self) -> None:
        """Every world is between two parties, so every world holds both — the person it is
        about and the assistant keeping it. A world without them has no "me" and no "you" to
        anchor a relationship to, and every fixture had to remember to invent them."""
        if "Person" not in self.classes or "AIAgent" not in self.classes:
            return
        self._agent_was_called_agent()
        with ontology.not_recording():
            agent, person = self._party(self.AGENT_ID), self._party(self.USER_ID)
            if agent is None and person is None and self.store.load_all("AIAgent", self.classes):
                return  # a fixture made its own pair; leave them be
            if person is None:
                person = self.classes["Person"](name="you")
                person.id = self.USER_ID
                self.store.save(person)
            if agent is None:
                agent = self.classes["AIAgent"](name="assistant", owner=person)
                agent.id = self.AGENT_ID
                self.store.save(agent)
            elif getattr(getattr(agent, "owner", None), "id", None) != person.id:
                # The tie between them is not a statement — it is made here and nowhere else —
                # so a rebuild, which knows only statements, leaves the assistant ownerless.
                # Re-tying them is the whole of what "both parties survived" means.
                agent.owner = person
                self.store.save(agent)

    def _party(self, entity_id: str):
        try:
            return self.store.load(entity_id, self.classes)
        except KeyError:
            return None

    def _agent_was_called_agent(self) -> None:
        """Worlds written before the class was renamed keep the assistant in an `Agent` table.

        Left alone, the world makes a fresh `AIAgent` beside it and the old one sits there
        looking like a class of its own — which is what the rename was for. Whatever it held
        (its character, anything said about it) moves with it.
        """
        held = {row[0] for row in self.store.conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name IN "
            "('Agent', 'AIAgent', 'facts_Agent', 'facts_AIAgent')")}
        for was, now in (("Agent", "AIAgent"), ("facts_Agent", "facts_AIAgent")):
            if was not in held:
                continue
            if now in held:
                self.store.conn.execute(f"INSERT OR IGNORE INTO '{now}' SELECT * FROM '{was}'")
                self.store.conn.execute(f"DROP TABLE '{was}'")
            else:
                self.store.conn.execute(f"ALTER TABLE '{was}' RENAME TO '{now}'")
        if held:
            self.store.conn.commit()

    def said_of(self, subject, obj, words: str, starts=None):
        """A fact about two things, in the words it was said in. See `sentences.say`."""
        from terraweaver import sentences

        return sentences.comes_in(self, subject, obj, words)

    def is_protected(self, entity) -> bool:
        """The two parties are not the host's to remove or replace."""
        return getattr(entity, "id", None) in (self.USER_ID, self.AGENT_ID)

    def _keep_old_value(self, instance, attr: str, existing, incoming) -> None:
        """An assignment is the host's statement and isn't questioned; what it replaces is kept.

        Questions belong to identification — ensure, get, find — where a disagreement can mean
        a different entity. An assignment says which entity and what is now true.
        """
        if ontology.filling():
            return  # filling an image from the record replaces nothing; see filling_from_record
        if matching.label(existing) == matching.label(incoming):
            return
        # A list that only grows is accumulating: nothing was replaced.
        if isinstance(existing, list) and isinstance(incoming, list):
            kept = {matching.label(item) for item in incoming}
            if all(matching.label(item) in kept for item in existing):
                return
        self.history.record(instance, attr, existing)

    # --- who the conversation is between ---

    @property
    def me(self):
        """The assistant itself."""
        agents = self.store.load_all("AIAgent", self.classes)
        return agents[0] if agents else None

    @property
    def owner(self):
        """The person whose world this is."""
        me = self.me
        return me.owner if me is not None else None

    # --- queries ---

    DEFAULT_LIMIT = 50

    def all(self, cls, limit: int | None = DEFAULT_LIMIT, history: bool = False,
            any_time: bool = False, kinds: bool = False) -> list:
        """Entities of a class, most recently worked with first.

        Limited by default: a personal world grows without bound, and an unbounded dump is
        both useless to read and a way to flood whatever consumes it. Note that `all` does
        not count as working with anything — it's a sweep, not attention, so it leaves the
        access times alone. Otherwise one listing would flatten the very signal the ordering
        is built on.

        Only what holds now — any_time=True gives everything, ended and not yet started too.

        `kinds=True` reads the classes beneath this one as well (`kinds_of`). The world's own
        sweeps go class by class and want each one exact, or an entity is met once per ancestor.
        What a host calls — `Thing.all()` — is inclusive (`Entity.all`): a kind of a thing is a
        thing, for a listing as for a lookup. It was exact until 2026-10-02 for one reason — a
        Person had no `name`, so `[i.name for i in Thing.all()]` raised on the first one and cost
        the rest of the block. Everything is called by its `name` now.
        """
        ontology.note_world_call("world_queries")
        under = self.kinds_of(self._name(cls)) if kinds else None
        instances = self.store.load_all(self._name(cls), self.classes, under)
        instances = self._whole_ones(self._name(cls), instances)
        if not (history or any_time):
            moment = timeutil.now()
            instances = [e for e in instances if timeutil.in_period(
                getattr(e, "valid_from", None), getattr(e, "valid_until", None), moment)]
        instances.sort(key=lambda e: e.accessed_at, reverse=True)
        if not instances and not kinds:
            self._say_what_is_a_kind_of_it(self._name(cls))
        return instances[:limit] if limit else instances

    def _say_what_is_a_kind_of_it(self, class_name: str) -> None:
        """Nothing is this class itself, and something is a kind of it: say so rather than "none".

        An exact listing (`kinds=False`, see `all`) of a world holding three countries answers
        nothing to `Thing` — true, and read as "there is nothing here". The world knows better and
        says which class to ask, once per class.
        """
        under = [name for name in self.kinds_of(class_name) if name != class_name]
        if not under:
            return
        held = {name: len(self.store.load_all(name, self.classes)) for name in under}
        held = {name: count for name, count in held.items() if count}
        if not held or class_name in self._said_about_kinds:
            return
        self._said_about_kinds.add(class_name)
        ontology.note_hint(
            f"nothing is a {class_name} itself, and {sum(held.values())} thing(s) are a kind of "
            f"it: " + ", ".join(f"{name} ({count})" for name, count in sorted(held.items()))
            + f". This listing was of the one class — ask the kind, {sorted(held)[0]}.all(), or "
            f"{class_name}.all() for everything under it. A lookup already reads them: "
            f"{class_name}.get(...) finds a kind of {class_name}.")

    def kinds_of(self, class_name: str) -> list[str]:
        """This class and every class that is a kind of it, however far down.

        A read of a class has to see the classes beneath it, because that is the whole of what
        "is a kind of" means. It did not, and the world then denied having things it had: the
        names pass places a thing under a class it grew (`Canada` becomes a `Country`), and from
        that moment `Thing.get(name="Canada")` answered `NotInWorld` and `Thing.all()` came back
        empty. A host or an engineer told that has one honest move left, which is to make a
        second Canada — measured 2026-10-01, six of ten duplicate-end facts in a 455-fact world,
        and an unknown share of the sixteen whose end "was never put in the world" at all.

        Writing is untouched: `Thing.new(...)` makes a Thing, and `ensure` is a write. This is
        about reading, where a kind of a thing is a thing.
        """
        below = {class_name}
        while True:
            # `own` classes are the world's own bookkeeping and are nobody's to list: a Task is a
            # kind of Event, and `Event.all()` is a host asking what is in its calendar.
            more = {name for name, cls in self.classes.items()
                    if cls._spec.get("parent") in below and name not in below
                    and not cls._spec.get("own")}
            if not more:
                return sorted(below)
            below |= more

    def _whole_ones(self, class_name: str, instances: list) -> list:
        """Links missing an end, kept out of every read at once instead of at each reader.

        A link with no subject joins nobody, and reading one raises from wherever it is touched:
        measured 2026-09-30, **20 of 898** links in one world had lost an end — fourteen of them
        bare `Related` — and each was able to end a whole pass. Two readers were mended one at a
        time (`relations._between`, `store._fill`) before it was clear that mending readers is
        endless; this is the one place they all come through.

        Not deleted and not repaired. What the link was made of is in the record, the row says
        nobody has read it, and a pass that can run is worth more than a row nobody can use. The
        world says how many it is holding back, once, so the number is not lost either.
        """
        cls = self.classes.get(class_name)
        if cls is None or "relation" not in getattr(cls, "_spec", {}):
            return instances
        whole = [one for one in instances
                 if getattr(one, "subject", None) is not None
                 and getattr(one, "object", None) is not None]
        left = len(instances) - len(whole)
        if left and class_name not in self._said_about_ends:
            self._said_about_ends.add(class_name)
            ontology.note_hint(
                f"{left} {class_name} link(s) have lost an end and are not in this answer. What "
                f"they were made of is still in the record; nothing can be read from a link that "
                f"joins one thing.")
        return whole

    def find(self, cls, history: bool = False, any_time: bool = False, **attrs):
        """Entities matching the given attributes, split into matches and resemblances.

        A lookup *by name* that isn't settled returns a NeedsResolution instead: several
        people answer to that name, or nothing matches it and only resemblances turned up.
        Handing back ranked candidates there would reopen the door this design closes —
        `Person.find(name="Annie")[0]` silently picks a fuzzy match, which is exactly the
        guess the user is supposed to make.
        """
        ontology.note_world_call("world_queries")
        class_name = self._name(cls)
        attrs = self._check_attrs(class_name, attrs)
        # Looking for something: the classes beneath this one count. `Thing.get(name="Canada")`
        # answered `NotInWorld` about a Canada the world had placed under `Country`, and a host
        # told that has one honest move left, which is to make a second Canada (`kinds_of`).
        scored = matching.score_candidates(
            self.all(cls, limit=None, history=history or any_time, kinds=True),
            class_name, attrs, filter_others=True)
        # Relevance first; between equally good matches, whoever was dealt with most recently.
        scored.sort(key=lambda pair: (-pair[1], -pair[0].accessed_at.timestamp()))
        ontology.note_looked_up([inst for inst, _ in scored])
        name_key = matching.NAME_KEYS.get(class_name)
        looked_up_by_name = name_key in attrs and not any(
            key in attrs for key in matching.STRONG_KEYS.get(class_name, [])
        )
        certain = [inst for inst, score in scored if score >= matching.CERTAIN]
        similar = [inst for inst, score in scored if score < matching.CERTAIN]

        if looked_up_by_name and scored and len(certain) != 1:
            chosen = self._remembered(class_name, attrs, certain or similar)
            if chosen is not None:
                return matching.FindResult([chosen], [inst for inst, _ in scored if inst is not chosen],
                                           class_name)
            only = self._only_match(class_name, attrs, scored)
            if only is not None:
                return matching.FindResult([only], [inst for inst, _ in scored if inst is not only],
                                           class_name)
            needs = ambiguous_identity(class_name, attrs, certain or similar, exact=bool(certain))
            self.pending = needs
            return needs
        if not scored:
            self._say_where_it_is_instead(class_name, attrs)
        return matching.FindResult(certain, similar, class_name)

    def _say_where_it_is_instead(self, class_name: str, attrs: dict) -> None:
        """Nothing of that name here — but the world has it under another class, so say which.

        Measured 2026-09-29, and it is most of the difference between a world that answers and one
        that does not. The reading makes classes and places into them only what it manages to read:
        one world ended with a `Country` holding Japan, Great Britain, Israel, India and France
        while Germany stayed a `Thing`. A host asked `Country.find(name="Germany")` — the sensible
        question, of a class the world itself had made — got "not found", and reported that the
        world did not know which continent Germany is on. The world knew: `LocatedIn Germany →
        Africa`, the right answer, one lookup away. Partial placing is worse than none unless the
        miss says where the thing actually is.
        """
        try:
            elsewhere = self._all_named_elsewhere(class_name, attrs)
        except Exception:  # noqa: BLE001 - a hint is never what stops a lookup
            return
        if not elsewhere:
            return
        said = ", ".join(f"a {other} called {one.display_name()}" for other, one in elsewhere[:4])
        key = matching.NAME_KEYS.get(elsewhere[0][0], "name")
        ontology.note_hint(
            f"no {class_name} of that name — what this world has of it: {said}. Which of them was "
            f"meant is yours to say: {elsewhere[0][0]}.identify({key}="
            f"{elsewhere[0][1].display_name()!r}). A class here holds what has been read into it, "
            f"not everything that belongs to the idea.")
        for other, one in elsewhere:
            self._looked_for_as(one, class_name, other)

    def _only_match(self, class_name: str, attrs: dict, scored: list):
        """One candidate, and nothing that disagrees with it, is not an ambiguity — it's them.

        "Darren" when the world holds one Darren Liu and no other Darren is far likelier to be
        him than a question worth the user's time. Asking cost hosts three to six turns and, on
        one run, produced a second Olga. So the rule: no contradiction, same one.

        Three things count as a contradiction, and any of them keeps the question:
        a second candidate; a value that disagrees with what's recorded; and a name that merely
        resembles instead of being one this entity answers to. That last one is what keeps
        "William Chen" from being quietly swallowed by "Wilma Chen" — a different first name is
        a different person, while "Darren" is simply part of "Darren Liu".
        """
        if len(scored) != 1:
            return None
        entity, score = scored[0]
        if score < matching.PART_CEILING:
            return None
        name_key = matching.NAME_KEYS.get(class_name)
        rest = {k: v for k, v in attrs.items() if k != name_key}
        if matching.contradictions(entity, rest):
            return None
        asked = attrs.get(name_key)
        if isinstance(asked, str) and matching.normalize(asked) != matching.normalize(
                getattr(entity, name_key, None) or ""):
            ontology.note_assumed(f"{asked} = {entity.display_name()} — the only one in the world "
                                  f"who answers to that, and nothing said disagrees with them")
        return self._determined(entity)

    def _named_elsewhere(self, class_name: str, attrs: dict):
        """Something of this name already exists, under another class.

        Identity is declared per class, so nothing looks across them: in one run "rugby" ended
        up recorded four times over — a Place, an Organization, a Work and a SportsTeam — and
        each was correct on its own terms. The world does not decide whether they are one thing;
        two things can share a name, and a town called after a sport is not the sport. It says
        that the name is taken elsewhere, which is the part nobody can see from inside one class.
        """
        name = attrs.get(matching.NAME_KEYS.get(class_name, ""))
        if not isinstance(name, str) or not name.strip():
            return
        wanted = matching.normalize(name)
        for other, cls in self.classes.items():
            if other == class_name or "relation" in cls._spec:
                continue
            key = matching.NAME_KEYS.get(other)
            if not key:
                continue
            for entity in self.all(other, limit=None, any_time=True):
                if matching.normalize(str(getattr(entity, key, "") or "")) == wanted:
                    return other, entity
        return None

    def _all_named_elsewhere(self, class_name: str, attrs: dict) -> list:
        """Everybody of that name, under whatever class, so the asker can choose.

        `_named_elsewhere` answers "is the name taken", which is one question and takes the first
        answer. This is the other one: a lookup that found nothing under the class it was told has
        to be given what the world does have, all of it. Prague is a city and a café and a cinema,
        and which of them was meant is the asker's to say — the world offers candidates and never
        picks, here as everywhere.
        """
        name = attrs.get(matching.NAME_KEYS.get(class_name, ""))
        if not isinstance(name, str) or not name.strip():
            return []
        wanted = matching.normalize(name)
        out = []
        for other, cls in self.classes.items():
            if other == class_name or "relation" in cls._spec:
                continue
            key = matching.NAME_KEYS.get(other)
            if not key:
                continue
            for entity in self.all(other, limit=None, any_time=True):
                if matching.normalize(str(getattr(entity, key, "") or "")) == wanted:
                    out.append((other, entity))
        return out

    def _looked_for_as(self, entity, class_name: str, was: str) -> None:
        """Hand the moment to the reading: somebody expected this to be a `class_name`.

        The world says nothing about whether it is. What it does is stop losing the question —
        a miss used to be answered and forgotten, and the placing that caused it stayed as it was.
        """
        try:
            from terraweaver import portraits

            portraits.looked_for(self, entity, class_name, was)
            portraits.comes_in(self, entity)        # back in the reading's queue, with a reason
        except Exception:  # noqa: BLE001 - never what stops a lookup
            return

    def _same_by_strong_key(self, class_name: str, attrs: dict, twins: list):
        """An address nobody else has is not a resemblance — it is them.

        `Person.new(name="Kate Johnson", email="KJohnson@NASA.gov")` next to a recorded
        Katherine Johnson at kjohnson@nasa.gov is one person written two ways, and asking about
        it spends the user's attention on something the data already answers. The rule is the
        same one identification uses everywhere here (`_only_match`): one candidate, nothing
        that disagrees, no question. What the host called them is kept as another name they
        answer to, so the next lookup by either finds them.

        Only on a strong key, though, and that limit is deliberate. A name alone is not enough
        here: `new()` carries the user's own claim that this one is new, and that claim is what
        disagrees with a namesake. Loosening it to any single match without a contradiction was
        tried and reverted — it made a second Robert Wolfe impossible to record, and four
        suites that build a question out of a name went red at once.
        """
        name_key = matching.NAME_KEYS.get(class_name)
        rest = {k: v for k, v in attrs.items() if k != name_key}
        same = [one for one in twins if matching.strong_key_match(one, class_name, attrs)]
        if len(same) != 1 or matching.contradictions(same[0], rest):
            return None
        entity = self._determined(same[0])
        asked = attrs.get(name_key)
        key = next(k for k in matching.STRONG_KEYS.get(class_name, []) if attrs.get(k))
        if isinstance(asked, str) and matching.normalize(asked) != matching.normalize(
                getattr(entity, name_key, None) or ""):
            forms = list(getattr(entity, matching.ALIAS_KEY, None) or [])
            if any(a["name"] == matching.ALIAS_KEY for a in type(entity)._spec["attributes"]) \
                    and not any(matching.normalize(a) == matching.normalize(asked) for a in forms):
                setattr(entity, matching.ALIAS_KEY, forms + [asked])
            ontology.note_assumed(
                f"{asked} is {entity.display_name()} — the same {key}, and nothing said "
                f"disagrees. Recorded as another name they answer to; say so if they are two people")
        return entity

    def resolve_reference(self, cls, **attrs):
        """Identify the entity a task refers to, before any code runs.

        Returns the instance only when the match is certain. A single *fuzzy* match is
        deliberately not good enough — "5 Annies" and "probably this one Annie" are the same
        problem, and both go to the user. Returns None when the world has no candidate.
        """
        ontology.note_world_call("world_queries")
        class_name = self._name(cls)
        # Identity is timeless: an ended or not-yet-started entity is still the same one.
        scored = matching.score_candidates(self._worth_loading(cls, attrs), class_name, attrs)
        certain = [inst for inst, score in scored if score >= matching.CERTAIN]
        if len(certain) == 1:
            return self._determined(certain[0])
        if scored:
            candidates = certain if len(certain) > 1 else [inst for inst, _ in scored]
            needs = ambiguous_identity(class_name, attrs, candidates)
            self.pending = needs
            return needs
        return None

    def identify(self, cls, **attrs) -> list:
        """Who in the world could this be — the candidates, best first, for you to read.

        A task settles who it is about before it records anything about them, and this is how.
        It does not choose: it hands back what resembles what the user said and you pick, because
        you have the conversation and the world does not. Two or five of them are read by eye;
        twenty means say more — `Person.identify(name="Anna", location="Berlin")` —
        and look again.

        **Nobody here of that name, and it makes them.** There is no second branch for the host
        to take: the user has just spoken about a city, and a city the world has never heard of
        is a city to record, not a refusal. Waiting for a second call to say so is ceremony, so
        the list comes back holding the new one and the run's [created] line says it was made.

        The one case that is not that: a search you narrowed yourself. If the name found people
        and your extra attributes ruled all of them out, the list is empty and nothing is made —
        you were choosing between the ones already here, and the narrowing was too tight.

        Recording does none of this. Matching in the middle of a write asks the same doubt again
        on every mention and settles none of them, and it stops a block half-written: "France"
        against a recorded "Acme" scored 0.6 on three letters they share, and the run ended on
        its fourteenth line. Writes take what they are given, and what they cannot tell apart is
        merged later, over the record, with the whole world in view.
        """
        if not attrs:
            raise ValueError(
                f"say who: {self._name(cls)}.identify(<what the user called them>). This "
                f"is where the task settles what it is about, so it needs something to go on.")
        ontology.note_world_call("world_queries")
        class_name = self._name(cls)
        attrs = self._check_attrs(class_name, attrs)
        everyone = self.all(cls, limit=None, history=True)
        scored = matching.score_candidates(everyone, class_name, attrs, filter_others=True)
        scored.sort(key=lambda pair: (-pair[1], -pair[0].accessed_at.timestamp()))
        found = [inst for inst, _ in scored]
        if found:
            ontology.note_looked_up(found)
            return found
        name_key = matching.NAME_KEYS.get(class_name)
        by_name = {name_key: attrs[name_key]} if name_key in attrs else dict(attrs)
        if matching.score_candidates(everyone, class_name, by_name, filter_others=True):
            return []          # the name is here; it was the narrowing that left nothing
        # Under another class, which is the world's answer and not a reason to make a second one.
        # `Country.identify(name="Germany")` on a world whose `Country` holds five countries and
        # not Germany used to *create* a Country called Germany — a duplicate of the Thing already
        # there, which is the one thing every other door here exists to prevent. The host wanted
        # the entity; it gets the entity, and hears which class it is under.
        elsewhere = self._all_named_elsewhere(class_name, attrs)
        if elsewhere:
            said = ", ".join(f"a {other} ({one.display_name()})" for other, one in elsewhere[:4])
            ontology.note_hint(
                f"nothing here is a {class_name} of that name, and the world has {said} — so "
                f"those are what you are given and nothing was made. Which of them was meant is "
                f"yours to say: Prague is a city and a café and a cinema, and the world does not "
                f"choose between them.")
            for other, one in elsewhere:
                self._looked_for_as(one, class_name, other)
            found = [one for _, one in elsewhere]
            ontology.note_looked_up(found)
            return found
        # The nature hint asks the same thing in the old door's words and guesses a variable
        # name out of the display name. What comes back from here is asked properly, after the
        # run, about the variable the host actually wrote — so it is not asked twice.
        self._reading_it_later = True
        try:
            made = self.create(class_name, attrs)
        finally:
            self._reading_it_later = False
        self._ask_what_it_is(made)
        return [made]

    def _ask_what_it_is(self, entity) -> None:
        """A thing that arrived as a bare name: say what it is, in words, and it is read later.

        The same division as the sentence door. The host has just heard of Rome from the user
        and knows what it is; choosing a class for it is a different job, done well by something
        whose whole attention is that. So the host says what it knows in the words it has, and
        the close reads them — picks a class or makes one, fills what the words fill.

        Only marked here. The question that asks for those words is put together after the
        script has run (`runtime._ask_about_bare_things`), because that is where the world can
        see what the host called the thing and ask about `rome` rather than about "Rome".
        """
        from terraweaver import portraits

        try:
            portraits.comes_in(self, entity)
        except Exception:  # noqa: BLE001 - never what stops a name being recorded
            return

    # --- writes ---

    def get(self, cls, **attrs):
        """The existing entity these attributes pick out. Never creates anything."""
        class_name = self._name(cls)
        if not attrs:
            raise ValueError(f"say which one: {class_name}.get(<what the user said about it>)")
        # Identity is timeless: the one meant may have ended or not started yet.
        result = self.find(cls, history=True, **attrs)
        if isinstance(result, NeedsResolution):
            return result
        if len(result.matches) == 1:
            entity = self._determined(result.matches[0])
            ontology.note_found(entity)
            return entity
        if result.matches or result.similar:
            only = self._only_match(class_name, attrs,
                                    matching.score_candidates(result.matches or result.similar, class_name, attrs))
            if only is not None:
                ontology.note_found(only)
                return only
            needs = ambiguous_identity(class_name, attrs, result.matches or result.similar, exact=bool(result.matches))
            self.pending = needs
            return needs
        described = ", ".join(f"{k}={v.display_name() if isinstance(v, ontology.Entity) else v}" for k, v in attrs.items())
        # The same three ways on that an empty search result names (matching.FindResult), in the
        # same words, because it is the same situation reached by a different door.
        raise NotInWorld(
            f"no {class_name} with {described} in the world. Either what you asked needs changing "
            f"— a fuller name, another attribute, any_time=True for something ended — or there is "
            f"no such {class_name} here yet: if the user is telling you about it, record it with "
            f"{class_name}.new(...); if they are asking about it, say it isn't there rather than "
            f"filling the gap. {class_name}.find(...) shows what merely resembles it."
        )

    def _worth_loading(self, cls, attrs: dict) -> list:
        """The entities a name could possibly match, chosen before any of them is built.

        Identifying one entity used to build every entity of its class to score it. At three
        hundred and fifty that was six tenths of a second a time, and a host writing twenty in one
        block ran past the ten-second limit — thirty-five of ninety-four refusals in one run. The
        same scoring decides here, on names read straight from the image table, and only what
        could match is built. Anything without a name to go on falls back to all of them, because
        then there is nothing to narrow by.
        """
        class_name = self._name(cls)
        name_key = matching.NAME_KEYS.get(class_name)
        incoming = attrs.get(name_key) if name_key else None
        if not isinstance(incoming, str) or not incoming.strip():
            return self.all(cls, limit=None, history=True)
        by_parts = class_name in matching.PART_MATCH_CLASSES
        strong = {k: attrs.get(k) for k in matching.STRONG_KEYS.get(class_name, []) if attrs.get(k)}
        wanted = {name_key, matching.ALIAS_KEY, *strong}
        held: dict = {}
        try:
            rows = self.store.conn.execute(
                f'SELECT instance_id, attr, value FROM "{self.store.values_table(class_name)}" '
                f'WHERE attr IN ({",".join("?" * len(wanted))})', tuple(wanted))
        except Exception:                      # noqa: BLE001 - no table yet is no candidates
            return []
        for instance_id, attr, value in rows:
            try:
                held.setdefault(instance_id, {})[attr] = json.loads(value)
            except Exception:                  # noqa: BLE001 - unreadable is not a match
                continue
        keep = []
        spec = self.classes[class_name]._spec
        # An address, a number, a website identifies as its kind compares it — "Ada@Example.com"
        # is "ada@example.com". Compared as raw strings here, the one candidate that decides the
        # question was thrown out before the comparison that would have found it ever ran, and a
        # second person was made for one address.
        wanted_keys = {k: values.canonical(spec, k, given) for k, given in strong.items()}
        for instance_id, row in held.items():
            names = [row.get(name_key)] + list(row.get(matching.ALIAS_KEY) or [])
            close = any(isinstance(n, str) and n
                        and matching.similarity(incoming, n, by_parts) >= matching.PLAUSIBLE
                        for n in names)
            same_key = any(k in row and values.canonical(spec, k, row[k]) == given
                           for k, given in wanted_keys.items())
            if close or same_key:
                keep.append(instance_id)
        return [self.store.load(instance_id, self.classes) for instance_id in keep]

    def new(self, cls, starts=None, until=None, ttl=None, permanent: bool = False, **attrs):
        """Create what the host says is new — asking first if its twin is already here."""
        ontology.note_world_call("world_writes")
        class_name = self._name(cls)
        if class_name not in self.classes:
            # `world.new("Kūkai")` — a name where a class belongs. It used to come back as a
            # bare `KeyError: 'Kūkai'` from somewhere inside, which says nothing about what was
            # wanted or what to write instead.
            known = ", ".join(sorted(n for n, c in self.classes.items()
                                     if not c._spec.get("relation"))[:12])
            raise ValueError(
                f"{class_name!r} is not a class in this world. The first thing you pass is what "
                f"kind of thing it is; its name is an attribute: "
                f"Thing.new(name={class_name!r}, nature=\"place\") — or one of {known}. "
                f"world.define(...) makes a class that is not there yet."
            )
        spec = self.classes[class_name]._spec
        if spec.get("relation") and not (attrs.get("subject") and attrs.get("object")):
            # A link with no ends is not a link. One recording run made two of these and lost
            # every capital it was given: both rows held a description ("Berlin is the capital
            # of Germany"), an orphan attribute named after the link's own kind, and neither a
            # subject nor an object. Nothing refused them, so the fact read as recorded while
            # the world held nothing that joined the two things — and reading either end raised,
            # which took every other link of that type down with it.
            kind = spec.get("relation", {}).get("kind", class_name)
            raise ValueError(
                f"{class_name} is a link, and a link is made from its ends, not on its own:\n"
                f"    a.relate(b, \"{kind}\")     # reads \"a is b's {kind.replace('_', ' ')}\"\n"
                f"`{class_name}.new(...)` with no subject and no object would put a row in the "
                f"world that joins nothing — it would carry your description and connect no two "
                f"things, and nothing later could tell it from a fact."
            )
        period = _period(starts, until, ttl, permanent)
        scored = matching.score_candidates(self._worth_loading(cls, attrs), class_name, attrs)
        # A twin (same email, same full name) — or someone whose name this is: "Darren" when
        # "Darren Liu" is recorded is far likelier to be him than a second Darren, and creating
        # one silently splits everything said about him in two. Only names identify, and only a
        # name they answer to: "Wilma Chen" must not stop "William Chen" from being recorded —
        # that once left the person out of the world entirely, with nothing said about it.
        resembling = ([inst for inst, score in scored if score >= matching.PART_CEILING]
                      if class_name in matching.PART_MATCH_CLASSES else [])
        twins = [inst for inst, score in scored if score >= matching.CERTAIN] or resembling
        if twins and (known := self._same_by_strong_key(class_name, attrs, twins)) is not None:
            outcome = self._apply_or_flag(known, {k: v for k, v in attrs.items()
                                                  if k != matching.NAME_KEYS.get(class_name)})
            if period and not isinstance(outcome, NeedsResolution):
                self.apply_period(outcome, period)
            return outcome
        elsewhere = self._named_elsewhere(class_name, attrs)
        created = self.create(class_name, attrs)
        if period:
            self.apply_period(created, period)
        if elsewhere:
            # This was a hint, and hints die with the run. The world noticed every one of
            # twenty-three duplicate names in a 455-fact run and said so where nobody was
            # reading: "University of California, Berkeley" ended up a Thing, a Place and an
            # Organization, so the fact that should have superseded an earlier one landed on a
            # different entity and superseded nothing. Identity is declared per class and
            # nothing looks across them, which makes this the one thing no class can see from
            # inside itself — and so the one worth holding a task open for.
            other, twin = elsewhere
            self.questions.raise_(
                created, "named_elsewhere",
                f"{created.display_name()} has the name of something already here: "
                f"{twin.display_name()}, a {other}. Two things can share a name, so this may be "
                f"right. If they are one thing, say so — everything said about the other one "
                f"will otherwise be about somebody else, and a later telling will supersede "
                f"nothing.",
                options=["one thing", "two things that share a name"],
                involves=[twin],
            )
        return created

    def ensure(self, cls, starts=None, until=None, ttl=None, permanent: bool = False, **attrs):
        """Return the entity these attributes describe, creating it if it's genuinely new.

        Returns a NeedsResolution instead when the case needs the user to settle it. A period
        (starts / until / ttl / permanent), if given, applies to whichever entity it turns out
        to be — also once the user has settled which one.
        """
        ontology.note_world_call("world_writes")
        class_name = self._name(cls)
        period = _period(starts, until, ttl, permanent)
        # Identity is timeless: matching sees every entity of the class, ended ones included,
        # and all of them — the 50 most recent aren't enough to rule out a duplicate.
        scored = matching.score_candidates(self._worth_loading(cls, attrs), class_name, attrs)

        certain = [inst for inst, score in scored if score >= matching.CERTAIN]
        if len(certain) == 1:
            outcome = self._apply_or_flag(self._determined(certain[0]), attrs)
        elif (chosen := self._remembered(class_name, attrs, certain or [inst for inst, _ in scored])) is not None:
            outcome = self._apply_or_flag(self._determined(chosen), attrs)
        elif scored and (only := self._only_match(class_name, attrs, scored)) is not None:
            outcome = self._apply_or_flag(only, attrs)
        else:
            outcome = self.create(class_name, attrs)
        if isinstance(outcome, NeedsResolution):
            outcome.context["period"] = period
        elif period:
            self.apply_period(outcome, period)
        return outcome

    def like(self, text: str, limit: int = 5, kind: str | None = None) -> list:
        """What in this world reads like that — by meaning, not by the words used.

        Candidates, not answers: it is an index over what was said (meaning.py), and it settles
        nothing. Useful where the world is deliberately unstructured — remarks, notes."""
        return self.meanings.like(self, text, limit, kind)

    def where(self, cls=None, **conditions) -> list:
        """Everything answering all the conditions at once, of any kind unless a class is
        named — attributes, a link, tags and meaning in one ask (selecting.py)."""
        from terraweaver import selecting

        return selecting.where(self, cls, **conditions)

    def texts(self, words: str | None = None, *, slot: str | None = None, at=None,
              any_time: bool = False, limit: int = 200) -> list[dict]:
        """Everything said in words, searched literally — every word must appear (texts.py)."""
        from terraweaver import texts as texts_module

        return texts_module.search(self, words, slot=slot, at=at, any_time=any_time, limit=limit)

    def happening(self, since=None, until=None, limit: int = 200) -> list[tuple]:
        """What falls between two moments — one-off and recurring alike (periods.py)."""
        from terraweaver import periods

        return periods.happening(self, since, until, limit)

    def retype(self, entity, class_name: str):
        """Read one entity under another class, without rebuilding the world to do it.

        Becoming is local: the statements about this one thing do not move, and nobody else's
        image changes. A full rebuild would give the same answer — the record holds `is_a` and
        says so — but it re-clusters every statement in the world to get there, which took a
        second and a half on a world of a hundred and thirty and ran a host's block past its
        time limit on anything larger.
        """
        was = type(entity)
        becomes = self.classes[class_name]
        keep = {a["name"] for a in becomes._spec["attributes"] if "derived" not in a}
        carried = {}
        for attr in was._spec["attributes"]:
            if "derived" in attr or attr["name"] not in keep:
                continue
            value = getattr(entity, attr["name"], None)
            if value is not None and value != []:
                carried[attr["name"]] = value
        # A link's ends are not declared attributes — the relation machinery puts them there,
        # so neither spec lists them and the loop above cannot see them. Left out, a free link
        # taken into a type became a row with a label, a description and nothing joined: two
        # `CapitalOf` rows in one run, and reading either end raised, which took every other
        # link of that type down with it. The record had both ends all along and a rebuild put
        # them back, so nothing was lost — but nothing was readable either, and the check that
        # asks whether a fact is in the world quite correctly said no.
        if becomes._spec.get("relation") or was._spec.get("relation"):
            for end in ("subject", "object"):
                at_end = getattr(entity, end, None)
                if at_end is not None:
                    carried[end] = at_end
        # Whatever it was called is what it is called: a Thing's `name` read as a Vacancy's
        # `title`, the one thing every entity has and the one most easily lost in becoming.
        named = matching.NAME_KEYS.get(was.__name__)
        calls_it = matching.NAME_KEYS.get(class_name)
        if named and calls_it and calls_it not in carried and getattr(entity, named, None):
            carried[calls_it] = getattr(entity, named)
        with ontology.trusted_writes(), ontology.not_recording():
            self.store.forget(entity.id)
            now = object.__new__(becomes)
            now.id = entity.id
            now.__dict__["_subject"] = entity.__dict__.get("_subject", entity.id)
            now.__dict__["_subjects"] = entity.__dict__.get("_subjects", [entity.id])
            for attr in becomes._spec["attributes"]:
                if "derived" in attr:
                    continue
                default = [] if attr.get("type", "").startswith("list[") else None
                setattr(now, attr["name"], carried.get(attr["name"], default))
            for end in ("subject", "object"):   # not declared, so set beside the declared ones
                if end in carried:
                    setattr(now, end, carried[end])
            now.created_at = getattr(entity, "created_at", None) or ontology.now_utc()
            now.accessed_at = ontology.now_utc()
            now.valid_from = getattr(entity, "valid_from", None)
            now.valid_until = getattr(entity, "valid_until", None)
            self._with_its_name(now)
            self.store.save(now)
        return now

    def wanted(self, least: int = 2) -> list[dict]:
        """The types this world keeps needing and hasn't got — counted from its own free links."""
        from terraweaver import relations

        return relations.free_shapes(self, least=least)

    def verify(self, least: int = 3) -> list[dict]:
        """What the world notices about its own links — nothing refused, everything named."""
        from terraweaver import relations

        return relations.verify(self, least)

    def take_in(self, kind, idea: str | None = None) -> list:
        """Move the free links that were waiting for a type into the one just defined."""
        from terraweaver import relations

        return relations.take_in(self, kind, idea)

    def repeats(self) -> list[str]:
        """Everything cyclic in this world, in words — one line per rule (periods.py)."""
        from terraweaver import periods, recurrence

        out = []
        for row in periods.cycles(self):
            said = recurrence.describe(row["starts"], row["every"], row["lasting"], row["until"])
            out.append(f"{self._named(row['subject'])}: "
                       + (f"{row['value']} — " if row["value"] else "") + said)
        return sorted(out)

    def _check_attrs(self, class_name: str, attrs: dict) -> None:
        """Looking something up by an attribute the class hasn't got is not a miss, it's a typo.

        Answering "nothing matched" to `Event.find(name="Dentist")` is true and
        useless: the host reads it as "CloudNine isn't in the world" and goes looking elsewhere,
        which is exactly what it did. Say what is wrong with the question instead, and name the
        word it probably wanted — the same answer `Class(...)` gives for the same mistake.
        """
        spec = self.specs.get(class_name) or self.classes[class_name]._spec
        known = {a["name"] for a in spec["attributes"]}
        unknown = [name for name in attrs if name not in known]
        if not unknown:
            return attrs
        calls_it = matching.NAME_KEYS.get(class_name)
        synonyms = {w: calls_it for w in ("name", "title", "label", "full_name")} if calls_it else {}
        for word, instead in (("limit", f"{class_name}.all(limit=...)"),
                              ("order_by", f"{class_name}.all(...)")):
            if word in attrs:
                raise TypeError(
                    f"{class_name}.find/.get(...) has no {word!r}: it identifies one thing rather "
                    f"than listing — {instead} is the listing, and world.where({class_name}, ...) "
                    f"narrows by several conditions at once.")
        left = []
        for given in unknown:
            meant = ontology.did_you_mean(given, sorted(known), synonyms)
            # Answering the question they meant, with the correction said, saves the turn a
            # refusal costs — and a read can be checked, so there is nothing to undo.
            if meant and meant not in attrs:
                attrs[ontology.take_as(f"{class_name}.find/.get", given, meant)] = attrs.pop(given)
            else:
                left.append(given)
        if left:
            raise TypeError(ontology._construction_problem(
                class_name, spec, [], dict.fromkeys(left), call=".find/.get(...)"))
        return attrs

    def _named(self, subject: str) -> str:
        """Whoever a statement is about, as a person would name them rather than as an id."""
        class_name = self.facts.class_of(subject)
        for entity in (self.all(class_name, limit=None, any_time=True) if class_name else []):
            if getattr(entity, "subject_id", None) == subject or entity.id == subject:
                return f"{class_name} «{entity.display_name()}»"
        return subject

    def tags(self) -> dict:
        """Every tag in this world, with how often it is used and how it has been written."""
        from terraweaver import tags as tagging

        return tagging.vocabulary(self)

    def tagged(self, tag: str, at=None, any_time: bool = False) -> list:
        """Everything carrying this tag now — or at a moment, or ever.

        `where` with one condition, and written as one so the two can never answer differently."""
        return self.where(tagged=tag, at=at, any_time=any_time, limit=None)

    def merge_tags(self, into: str, *others: str) -> int:
        """Make several tags one: everything carrying any of them ends up carrying the first."""
        from terraweaver import tags as tagging

        return tagging.merge(self, into, *others)

    def untag(self, tag: str, among: list | None = None) -> int:
        """Take a tag off everything, or off the ones given."""
        from terraweaver import tags as tagging

        return tagging.remove(self, tag, among=among)

    def tagged_all(self, *tags_wanted: str) -> list:
        """Everything carrying every one of these tags."""
        return self.where(tagged_all=list(tags_wanted), limit=None)

    def rebuild(self, rule=None, at=None) -> dict:
        """Build every entity again from what was said. See rebuild.py — it is always safe."""
        from terraweaver import rebuild as rebuilding

        return rebuilding.rebuild(self, rule, at)

    def _apply_deferred(self, instance) -> None:
        """Attributes given at construction that need the entity stored first."""
        deferred = instance.__dict__.pop("_deferred", {})
        for name, value in deferred.items():
            setattr(instance, name, value)

    def relate(self, a, b, kind: str, /, starts=None, until=None, ttl=None,
               permanent: bool = False, **attrs):
        """Record that `a` stands in relation `kind` to `b`."""
        from terraweaver import relations

        ontology.note_world_call("world_writes")
        return relations.relate(self, a, b, kind, _period(starts, until, ttl, permanent), attrs)

    def set_period(self, instance, starts=None, until=None, ttl=None, permanent: bool = False) -> None:
        period = _period(starts, until, ttl, permanent)
        if not period:
            raise ValueError("say when it holds: starts=..., until=... / ttl=..., or permanent=True")
        self.apply_period(instance, period)

    def apply_period(self, instance, period: dict) -> None:
        ontology.note_world_call("world_writes")
        with ontology.trusted_writes():
            for attr, value in period.items():
                setattr(instance, attr, value)
        self.store.save_graph(instance)
        if "valid_until" in period and "relation" in type(instance)._spec:
            from terraweaver import relations

            relations.note_gap_on_ending(self, instance)

    def create(self, class_name: str, attrs: dict, basis: list | None = None,
               period: dict | None = None):
        ontology.note_world_call("world_writes")
        instance = self.classes[class_name](**attrs)
        if period and basis:
            # Set here rather than applied afterwards: applying it would state the period as
            # something the agent said, and this is something the world worked out. It has to
            # carry the moment of the evidence it was drawn from, or a conclusion about what
            # held in March is recorded as holding from now — which flattens the timeline and
            # destroys the very supersession the reasoning was meant to restore.
            with ontology.trusted_writes(), ontology.not_recording():
                for attr, value in period.items():
                    setattr(instance, attr, value)
        first = len(self.store.made)
        self.store.save_graph(instance)
        # The far ends of a link made by hand arrive here too, and nothing else would state them.
        self.say_what_came_in(self.store.made[first:], but=instance)
        # Attributes given at construction are set before the entity has an id, so they can't
        # state themselves on the way in; they are stated here, once it has one.
        source, run_id = ontology.stated_by()
        for attr in type(instance)._spec["attributes"]:
            name = attr["name"]
            if "derived" in attr or name in ontology.MANAGED_VALUE_ATTRS or name == "tags":
                continue  # tags go through their own door below, so periods work from the start
            value = attrs.get(name, instance.__dict__.get(name))  # as given, not as tidied
            if value is None or value == []:
                continue
            if basis:
                # Something the world worked out, not something it was told. It goes where every
                # conclusion goes — the reasoning tables, weakest source, its basis recorded —
                # so a derived link can be told from a stated one, ranked below it, and dropped
                # as a guess rather than ended as if it had once been true. With the period of
                # the evidence on it, so it takes its place in time rather than at the end of it.
                self.facts.conclude(instance.id, name, ontology._as_statement(value),
                                    basis=basis, run_id=run_id, class_name=class_name,
                                    valid_from=(period or {}).get("valid_from"),
                                    valid_until=(period or {}).get("valid_until"))
            else:
                self.facts.state(instance.id, name, ontology._as_statement(value),
                                 source=source, run_id=run_id, class_name=class_name)
        # A bare string where a list was expected is taken as the one tag it plainly is. The
        # constructor tidies the image either way, so `Person(tags="vip")` looked right and then
        # lost the tag on the next rebuild, because nothing here stated it
        # (docs/code-review-2026-09-30.md 3.2.7).
        told = attrs.get("tags")
        if isinstance(told, str) and told.strip():
            told = [told]
        if isinstance(told, list) and told:
            instance._set_tags(told)
        if not getattr(self, "_reading_it_later", False):
            _ask_its_nature(instance, class_name, attrs)
        self._apply_deferred(instance)
        return instance  # brand new, so created_at and accessed_at already coincide

    def apply_attrs(self, instance, attrs: dict):
        """Set attributes that aren't set yet; conflicting ones are the caller's problem."""
        ontology.note_world_call("world_writes")
        with ontology.trusted_writes():
            for attr, value in attrs.items():
                if getattr(instance, attr, None) is None:
                    setattr(instance, attr, value)
        instance.touch()
        self.store.save_graph(instance)
        return instance

    def apply_resolved(self, instance, attr: str, value) -> None:
        """Write a value the user has explicitly settled on — the guard steps aside for this."""
        with ontology.trusted_writes():
            setattr(instance, attr, value)
        self.pending = None
        self.store.save_graph(instance)

    def save(self, instance) -> None:
        ontology.note_world_call("world_writes")
        instance.touch()
        self._with_its_name(instance)
        first = len(self.store.made)
        self.store.save_graph(instance)
        self.say_what_came_in(self.store.made[first:])

    def say_what_came_in(self, arrived: list, but=None) -> None:
        """A thing that got its id on the way to storage says what it holds, once.

        `Thing(name="Harvard University")` built by hand and passed as the far end of a link is
        given its id by the save that stores the link — and an attribute set before there is an id
        states nothing, so the image held a name the record had never heard. Measured 2026-10-03:
        three things in a 125-fact world existed only as images, six links pointing at them, and a
        rebuild from the record cut every one of those links off at the end. `create` states what
        it was given; this is the same for whatever came in beside it.
        """
        source, run_id = ontology.stated_by()
        for one in arrived:
            if one is but or getattr(one, "id", None) is None or one._spec.get("own"):
                continue
            try:
                if self.facts.about(one.subject_id):
                    continue
            except Exception:  # noqa: BLE001 - a record that cannot be read has nothing to compare
                continue
            for attr in type(one)._spec["attributes"]:
                name = attr["name"]
                if "derived" in attr or name in ontology.MANAGED_VALUE_ATTRS:
                    continue
                value = one.__dict__.get(name)
                if value is None or value == []:
                    continue
                self.facts.state(one.subject_id, name, ontology._as_statement(value),
                                 source=source, run_id=run_id, class_name=type(one).__name__)

    def _with_its_name(self, instance) -> None:
        """An image never goes to storage without the name its record holds.

        The record is what was said and the image is a reading of it. Measured on 2026-10-01, in
        two worlds: images holding `null` for the name while the record held it, unretracted —
        21 entities in a 455-fact world, 3 of 48 in a 25-fact gate. Such a thing displays as a raw
        id, `Thing.get(name=…)` says it is not there, and every fact about it reads as lost.

        One cause was found and closed (a failed load left a shell in the identity map). The other
        did not survive five faithful reproductions — the image came out right every time — so
        instead of guarding each path that might hand storage a nameless object, the one door
        they all come through is guarded: if the identifying attribute is empty here and the
        record has a value for it, the record's value is put back before anything is written. It
        is said in the log every time, with the class and the id, so the next run says where it
        comes from instead of leaving it to be found from what it broke.
        """
        if getattr(instance, "id", None) is None:
            return
        cls = type(instance)
        spec = getattr(cls, "_spec", {}) or {}
        if spec.get("relation") or spec.get("own"):
            return
        key = spec.get("identified_by") or matching.NAME_KEYS.get(cls.__name__)
        if not key or not any(a["name"] == key for a in spec.get("attributes", [])):
            return
        if getattr(instance, key, None):
            return
        try:
            said = [one for one in self.facts.about(getattr(instance, "subject_id", None) or instance.id, key)
                    if isinstance(one.value, str) and one.value.strip()]
        except Exception:  # noqa: BLE001 - a record that cannot be read has nothing to put back
            return
        if not said:
            return
        latest = max(said, key=lambda one: one.last_said)
        log.warning("%s %s was about to be written without its %s; the record says %r — put back",
                    cls.__name__, instance.id, key, latest.value)
        with ontology.trusted_writes(), ontology.not_recording():
            setattr(instance, key, latest.value)

    def _determined(self, instance):
        """Mark an entity as one we are now working with, and persist that.

        Only a *determined* identity counts — an entity picked out as unambiguously this
        one. Turning up among search candidates doesn't: a search is looking for someone,
        not working with them, and counting it would make "who we've been dealing with"
        mean nothing.
        """
        ontology.note_world_call("world_writes")
        instance.touch()
        if instance.id is not None:
            self._with_its_name(instance)
            self.store.save(instance)
        return instance

    def settle(self, needs: NeedsResolution, choice=None, *, new: bool = False):
        """Apply the user's answer to a NeedsResolution.

        `choice` is the entity the user meant — one of `needs.candidates` — or, for a
        contradiction, the value that is right. `new=True` says it's someone/something new.
        An option number still works, but naming the entity is what the user actually said,
        and it can't silently point at the wrong row. None means the user didn't settle it:
        the case stays unresolved and the world isn't touched.
        """
        needs = self._current_copies(needs)
        if isinstance(choice, ontology.Entity) and choice.id is not None:
            choice = self._current(choice)
        return resolution.run_skill(needs, lambda question, options: _option_index(needs, choice, new), self)

    def _current(self, entity):
        """The object that stands for this entity now. A question asked before a run was rolled
        back holds copies the rollback orphaned; applying the answer to one of those, and later
        saving another, is how a settled value quietly turned back into the old one."""
        try:
            return self.store.load(entity.id, self.classes)
        except KeyError:
            return entity

    def _current_copies(self, needs: NeedsResolution) -> NeedsResolution:
        fresh = lambda v: self._current(v) if isinstance(v, ontology.Entity) and v.id is not None else v
        needs.candidates = [fresh(c) for c in needs.candidates]
        for key in ("existing", "incoming"):
            if key in needs.context:
                needs.context[key] = fresh(needs.context[key])
        return needs

    def remember_choice(self, needs: NeedsResolution, entity) -> str | None:
        """The user said who they meant by that name; the next lookup by it will assume so.

        Returns the name it was stored under, so a caller can say what it now assumes."""
        class_name = needs.context.get("class_name")
        name = needs.context.get("incoming", {}).get(matching.NAME_KEYS.get(class_name, ""))
        if not isinstance(name, str):
            return None
        key = (class_name, matching.normalize(name))
        if entity is None:  # "someone new": the name is shared by one more now, so ask again next time
            self.store.conn.execute("DELETE FROM name_choices WHERE class_name = ? AND name = ?", key)
            return None
        self.store.conn.execute(
            "INSERT OR REPLACE INTO name_choices (class_name, name, entity_id, chosen_at) VALUES (?, ?, ?, ?)",
            key + (entity.id, timeutil.now().isoformat()),
        )
        return name

    def _remembered(self, class_name: str, attrs: dict, candidates: list):
        """The candidate the user chose for this name before, if they did and it's among these."""
        name = attrs.get(matching.NAME_KEYS.get(class_name, ""))
        if not isinstance(name, str):
            return None
        row = self.store.conn.execute(
            "SELECT entity_id, chosen_at FROM name_choices WHERE class_name = ? AND name = ?",
            (class_name, matching.normalize(name)),
        ).fetchone()
        if row is None:
            return None
        chosen = next((c for c in candidates if c.id == row[0]), None)
        if chosen is not None:
            ontology.note_assumed(
                f'"{name}" -> {chosen.display_name()}, as the user settled on {row[1][:10]}; '
                f"say so in your answer, and if they mean someone else, ask"
            )
        return chosen

    def log_resolution(self, needs: NeedsResolution, choice: int | None, status: str) -> None:
        self.resolutions.append({
            "skill": needs.skill,
            "kind": SKILL_KINDS.get(needs.skill, needs.skill),
            "status": status,
            "reason": needs.reason,
            "question": needs.question,
            "options": needs.options,
            "chosen": needs.options[choice] if choice is not None else None,
        })

    # --- internals ---

    def _apply_or_flag(self, instance, attrs: dict):
        original = attrs
        # The name it was identified by is how the user refers to it, not a new value for it:
        # "Annie" doesn't contradict "Anna Sullivan".
        name_key = matching.NAME_KEYS.get(type(instance).__name__)
        attrs = {k: v for k, v in attrs.items() if k != name_key}
        conflicts = matching.contradictions(instance, attrs)
        if conflicts:
            attr, existing, incoming = conflicts[0]
            needs = contradicting_value(instance, attr, existing, incoming)
            # What "a different one" would be created from, name included.
            needs.context["class_name"] = type(instance).__name__
            needs.context["incoming_attrs"] = dict(original)
            self.pending = needs
            return needs
        return self.apply_attrs(instance, attrs)

    def _name(self, cls) -> str:
        """The class name behind whatever was passed at a class door.

        Every door that takes a class comes through here, so this is where a wrong first
        argument is answered. `world.identify({"name": "Fatah"})` — attributes in a dict, the
        shape most APIs take — used to raise `'dict' object has no attribute '__name__'`: a
        Python internal that says nothing about what this world wanted. Measured on the
        FactConsolidation slice it cost the recorder seventeen lines of work in one turn and
        dropped it into untyped prose for the rest of the run. A door refuses in the world's
        own words, naming what to write instead, or it is not a refusal at all.
        """
        if isinstance(cls, str):
            return cls
        name = getattr(cls, "__name__", None)
        if name is not None:
            return name
        classes = ", ".join(sorted(self.classes))
        if isinstance(cls, dict):
            spread = ", ".join(f"{key}={value!r}" for key, value in list(cls.items())[:3])
            raise TypeError(f"the class comes first and the attributes are named after it, not "
                            f"gathered in a dict: Thing.identify({spread}) to look it up, "
                            f"Thing.new({spread}) to make it. The classes here are: {classes}.")
        raise TypeError(f"the class comes first, and this is a {type(cls).__name__}, not the "
                        f"class {type(cls).__name__}. Something you already hold answers for "
                        f"itself — it.describe(...), it.relate(...); a class is named as the "
                        f"class — {type(cls).__name__}.identify(...). The classes here are: "
                        f"{classes}.")


def _period(starts, until, ttl, permanent: bool) -> dict:
    """The validity attributes a caller asked for; empty if they said nothing about time."""
    period = {}
    bound, sure = timeutil.told(starts)
    begin = bound.moment if bound is not None else None
    if begin is not None:
        period["valid_from"] = begin
        if not bound.exact:
            period["from_is"] = bound.side
    low, high = getattr(starts, "low", None), getattr(starts, "high", None)
    if low is not None and high is not None and timeutil.as_datetime(low) != timeutil.as_datetime(high):
        # A start known only to a window is two facts, and a period keeps one date and a side.
        # The side that survives is the one that answers "had it started by then"; the other is
        # said out loud rather than dropped quietly, because a bound nobody mentions losing is
        # the same as a bound nobody had.
        ontology.note_hint(
            f"I kept that start as {bound.describe()} — by then it had certainly begun. That it "
            f"was also not before {timeutil.show(low)} is not something a period can hold "
            f"alongside; if that edge matters, record it as its own fact.")
    if bound is not None and not sure:
        ontology.note_hint(
            f"I took that as {bound.describe()} and noted you were not certain. If it matters "
            f"to the answer, ask; if it does not, it is recorded as said.")
    end = timeutil.period_end(until, ttl, permanent, base=begin)
    if end is not timeutil.NO_END_GIVEN:
        if isinstance(end, timeutil.Bound):
            if not end.exact:
                period["until_is"] = end.side
            end = end.moment
        period["valid_until"] = end
    return period


def _option_index(needs: NeedsResolution, choice, new: bool) -> int | None:
    """Turn what the user said into the option it stands for."""
    if new:
        return len(needs.options) - 1  # the last option is always "someone / something new"
    if choice is None or isinstance(choice, bool):
        return None
    if isinstance(choice, int):
        return choice
    if needs.skill == "resolve_ambiguity":
        for index, candidate in enumerate(needs.candidates):
            if candidate is choice or (isinstance(choice, ontology.Entity) and candidate == choice):
                return index
        raise ValueError(
            f"{matching.label(choice)} is not one of the candidates: "
            + "; ".join(matching.label(c) for c in needs.candidates) + ". Pass one of them, or new=True."
        )
    # A contradiction: the user names the value that is right.
    for index, value in enumerate((needs.context["incoming"], needs.context["existing"])):
        if choice is value or choice == value or matching.label(choice) == matching.label(value):
            return index
    raise ValueError(
        f"{matching.label(choice)} is neither the stored value ({matching.label(needs.context['existing'])}) "
        f"nor the new one ({matching.label(needs.context['incoming'])})"
    )

