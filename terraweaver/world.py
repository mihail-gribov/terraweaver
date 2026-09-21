"""The world as the agent sees it: query and write entities without touching storage.

`ensure()` is the important one — it's the single entry point for "record this
entity", and it never silently guesses. If the incoming data plausibly refers to
something already in the world but isn't certain, or contradicts what's stored, it
returns a NeedsResolution naming the skill the agent must run instead of picking.
"""
from typing import Any

from terraweaver import matching, ontology, resolution, timeutil
from terraweaver.comments import Comments
from terraweaver.history import ValueHistory
from terraweaver.facts import Facts
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
    looks_existing,
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


class NotInWorld(LookupError):
    """get() found nothing: the entity the host meant isn't in the world."""


class World:
    def __init__(self, store, classes: dict[str, type], specs: dict | None = None):
        self.store = store
        self.classes = classes
        # What each class declares — how many of a thing a slot holds, and so on. Assembly needs
        # it to build images; without it every slot is treated as holding one thing.
        self.specs = specs or {name: cls._spec for name, cls in classes.items()}
        self.resolutions: list[dict] = []
        self.pending: NeedsResolution | None = None
        self.comments = Comments(store, classes)
        # Who the user meant by a name, once they said so. The next "Annie" is that Annie —
        # announced, never silent, so the user can correct it.
        store.conn.executescript(CHOICES_SCHEMA)
        # Every overwrite of a known entity's attribute leaves the old value in history.
        self.history = ValueHistory(store, classes)
        self.facts = Facts(store.conn)
        self.usage = Usage(store)
        self.procedures = Procedures(store)
        self.meanings = Meanings(store)
        self.questions = Questions(store, classes, self.usage)
        ontology.set_write_guard(self._keep_old_value)
        # Lets `Person.find(...)` reach this world without each class carrying a store.
        ontology.set_world(self)
        self.ensure_selves()

    # Fixed ids, so the two of them are the same rows in every world and can be found without
    # searching by name — and so nothing else can quietly take their place.
    USER_ID, AGENT_ID = "person:user", "agent:self"

    def ensure_selves(self) -> None:
        """Every world is between two parties, so every world holds both — the person it is
        about and the assistant keeping it. A world without them has no "me" and no "you" to
        anchor a relationship to, and every fixture had to remember to invent them."""
        if "Person" not in self.classes or "Agent" not in self.classes:
            return
        with ontology.not_recording():
            try:
                agent = self.store.load(self.AGENT_ID, self.classes)
            except KeyError:
                agent = None
            if agent is None and self.store.load_all("Agent", self.classes):
                return  # a fixture made its own pair; leave them be
            if agent is None:
                person = self.classes["Person"](full_name="you")
                person.id = self.USER_ID
                self.store.save(person)
                agent = self.classes["Agent"](name="assistant", owner=person)
                agent.id = self.AGENT_ID
                self.store.save(agent)

    def is_protected(self, entity) -> bool:
        """The two parties are not the host's to remove or replace."""
        return getattr(entity, "id", None) in (self.USER_ID, self.AGENT_ID)

    def _keep_old_value(self, instance, attr: str, existing, incoming) -> None:
        """An assignment is the host's statement and isn't questioned; what it replaces is kept.

        Questions belong to identification — ensure, get, find — where a disagreement can mean
        a different entity. An assignment says which entity and what is now true.
        """
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
        agents = self.store.load_all("Agent", self.classes)
        return agents[0] if agents else None

    @property
    def owner(self):
        """The person whose world this is."""
        me = self.me
        return me.owner if me is not None else None

    # --- queries ---

    DEFAULT_LIMIT = 50

    def all(self, cls, limit: int | None = DEFAULT_LIMIT, history: bool = False, any_time: bool = False) -> list:
        """Entities of a class, most recently worked with first.

        Limited by default: a personal world grows without bound, and an unbounded dump is
        both useless to read and a way to flood whatever consumes it. Note that `all` does
        not count as working with anything — it's a sweep, not attention, so it leaves the
        access times alone. Otherwise one listing would flatten the very signal the ordering
        is built on.

        Only what holds now — any_time=True gives everything, ended and not yet started too.
        """
        ontology.note_world_call("world_queries")
        instances = self.store.load_all(self._name(cls), self.classes)
        if not (history or any_time):
            moment = timeutil.now()
            instances = [e for e in instances if timeutil.in_period(
                getattr(e, "valid_from", None), getattr(e, "valid_until", None), moment)]
        instances.sort(key=lambda e: e.accessed_at, reverse=True)
        return instances[:limit] if limit else instances

    def find(self, cls, history: bool = False, any_time: bool = False, **attrs):
        """Entities matching the given attributes, split into matches and resemblances.

        A lookup *by name* that isn't settled returns a NeedsResolution instead: several
        people answer to that name, or nothing matches it and only resemblances turned up.
        Handing back ranked candidates there would reopen the door this design closes —
        `Person.find(full_name="Annie")[0]` silently picks a fuzzy match, which is exactly the
        guess the user is supposed to make.
        """
        ontology.note_world_call("world_queries")
        class_name = self._name(cls)
        attrs = self._check_attrs(class_name, attrs)
        scored = matching.score_candidates(self.all(cls, limit=None, history=history or any_time),
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
        return matching.FindResult(certain, similar, class_name)

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

    def _same_by_strong_key(self, class_name: str, attrs: dict, twins: list):
        """An address nobody else has is not a resemblance — it is them.

        `Person.new(full_name="Kate Johnson", email="KJohnson@NASA.gov")` next to a recorded
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
        scored = matching.score_candidates(self.all(cls, limit=None, history=True), class_name, attrs)
        certain = [inst for inst, score in scored if score >= matching.CERTAIN]
        if len(certain) == 1:
            return self._determined(certain[0])
        if scored:
            candidates = certain if len(certain) > 1 else [inst for inst, _ in scored]
            needs = ambiguous_identity(class_name, attrs, candidates)
            self.pending = needs
            return needs
        return None

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
        raise NotInWorld(
            f"no {class_name} with {described} in the world. If the user is telling you about a new "
            f"one, record it with {class_name}.new(...); if you meant an existing one, look it up differently."
        )

    def new(self, cls, starts=None, until=None, ttl=None, permanent: bool = False, **attrs):
        """Create what the host says is new — asking first if its twin is already here."""
        ontology.note_world_call("world_writes")
        class_name = self._name(cls)
        period = _period(starts, until, ttl, permanent)
        scored = matching.score_candidates(self.all(cls, limit=None, history=True), class_name, attrs)
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
        if twins:
            needs = looks_existing(class_name, attrs, twins)
            needs.context["period"] = period
            self.pending = needs
            return needs
        created = self.create(class_name, attrs)
        if period:
            self.apply_period(created, period)
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
        scored = matching.score_candidates(self.all(cls, limit=None, history=True), class_name, attrs)

        certain = [inst for inst, score in scored if score >= matching.CERTAIN]
        if len(certain) == 1:
            outcome = self._apply_or_flag(self._determined(certain[0]), attrs)
        elif (chosen := self._remembered(class_name, attrs, certain or [inst for inst, _ in scored])) is not None:
            outcome = self._apply_or_flag(self._determined(chosen), attrs)
        elif len(certain) > 1:
            outcome = ambiguous_identity(class_name, attrs, certain)
        elif scored and (only := self._only_match(class_name, attrs, scored)) is not None:
            outcome = self._apply_or_flag(only, attrs)
        elif scored:
            outcome = ambiguous_identity(class_name, attrs, [inst for inst, _ in scored])
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

        Answering "nothing matched" to `Organization.find(full_name="CloudNine")` is true and
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
        """Attributes given at construction that live in relations (Person(organization=...)):
        they need the entity stored first."""
        from terraweaver import relations

        deferred = instance.__dict__.pop("_deferred", {})
        for name in sorted(deferred, key=lambda n: relations.APPLY_ORDER.index(n) if n in relations.APPLY_ORDER else 99):
            setattr(instance, name, deferred[name])

    def relate(self, a, b, kind: str, /, starts=None, until=None, ttl=None, permanent: bool = False, **attrs):
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

    def create(self, class_name: str, attrs: dict):
        ontology.note_world_call("world_writes")
        instance = self.classes[class_name](**attrs)
        self.store.save_graph(instance)
        # Attributes given at construction are set before the entity has an id, so they can't
        # state themselves on the way in; they are stated here, once it has one.
        source, run_id = ontology.stated_by()
        for attr in type(instance)._spec["attributes"]:
            name = attr["name"]
            if "derived" in attr or name in ontology.MANAGED_VALUE_ATTRS or name == "tags":
                continue  # tags go through their own door below, so periods work from the start
            value = attrs.get(name, instance.__dict__.get(name))  # as given, not as tidied
            if value is not None and value != []:
                self.facts.state(instance.id, name, ontology._as_statement(value),
                                 source=source, run_id=run_id, class_name=class_name)
        if isinstance(attrs.get("tags"), list) and attrs["tags"]:
            instance._set_tags(attrs["tags"])
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
        self.store.save_graph(instance)

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

    @staticmethod
    def _name(cls) -> str:
        return cls if isinstance(cls, str) else cls.__name__


def _period(starts, until, ttl, permanent: bool) -> dict:
    """The validity attributes a caller asked for; empty if they said nothing about time."""
    period = {}
    begin = timeutil.check_start(starts)
    if begin is not None:
        period["valid_from"] = begin
    end = timeutil.period_end(until, ttl, permanent, base=begin)
    if end is not timeutil.NO_END_GIVEN:
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


def describe_world_api() -> str:
    """The part of the prompt that tells the agent how to touch the world."""
    return """\
Before you answer anything or change anything, be certain WHICH entities are involved.
An answer built on the wrong Annie is worse than no answer, and it's not yours to guess:
- If this conversation has already settled who is meant, use that entity — don't look it
  up again and don't ask again.
- Otherwise look it up. If what comes back is a NeedsResolution — several people match, or
  one matches only loosely — stop and settle it with the user before doing anything else:

      result = Person.find(full_name="Annie")
      if isinstance(result, NeedsResolution):
          anna = run_skill(result)          # asks the user, returns the settled entity

- Only once every entity is unambiguous and nothing contradicts what's stored do you carry
  out the task. Never do half the work and ask afterwards.

World access (the object `world` is in your namespace; it hides all storage details):
- Record anything the user tells you with Class.ensure(...) — never construct Person(...)
  directly for it, or you'll create a second copy of someone who already exists.
  Pass the user's own wording verbatim: do not transliterate, translate, correct or otherwise
  normalize a name before passing it in ("Ada Lovelase" stays "Ada Lovelase"). Deciding that two
  spellings mean the same person is not yours to make — matching is done for you, and anything
  it can't settle goes to the user. Rewriting the name first hides the ambiguity and risks
  silently merging two different people.
- When the user says something changed ("now works at X"), pass the NEW value to
  world.ensure(...) — that's what surfaces the contradiction with what's stored.
- Assigning straight to an attribute of an entity the world already knows (person.organization
  = other) raises ResolutionRequired whenever the new value contradicts what's stored. That is
  not an error to work around — settle it and continue:

      person = run_skill(world.pending)   # runs the named skill, asks the user, applies the answer
- world.ensure(...) may return a NeedsResolution instead of an entity. That means the situation
  is genuinely ambiguous or contradicts what's stored, and it is NOT yours to guess: it names
  the skill that must run to settle it with the user. Handle it exactly like this:

      result = world.ensure(Person, full_name="Ada")
      if isinstance(result, NeedsResolution):
          result = run_skill(result)   # asks the user, returns the settled entity
      report(result)
"""
