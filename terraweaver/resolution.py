"""Uncertainty/contradiction hand-off: what the world returns instead of guessing.

When a deterministic check can't settle a case on its own, the world layer doesn't
pick an answer and it doesn't ask an LLM — it returns a NeedsResolution naming the
skill the agent must run. That skill resolves the situation in dialogue with the
user, so an ambiguity is settled by the person who actually knows, not by inference.
"""
from dataclasses import dataclass, field
from typing import Any, Callable

from terraweaver import ontology
from terraweaver.ontology import Entity

# What kind of episode each skill represents, for tagging the transcript.
SKILL_KINDS = {
    "resolve_ambiguity": "uncertainty_resolution",
    "resolve_contradiction": "contradiction_resolution",
}

RESOLVED = "resolved"
UNRESOLVED = "unresolved"


class ResolutionRequired(Exception):
    """Raised when a write is refused because it needs the user to settle it first."""

    def __init__(self, needs: "NeedsResolution"):
        self.needs = needs
        super().__init__(
            f"{needs.reason}. This is not yours to decide — settle it with the user by calling "
            f"run_skill(world.pending), which runs the '{needs.skill}' skill, then continue. "
            f"Where run_skill isn't available, put this question to the user: {needs.question} "
            f"Options: {_numbered(needs.options)}. Then call world.settle(world.pending, <the value that is right>)."
        )


@dataclass
class NeedsResolution:
    """Returned by world operations that hit an uncertainty or a contradiction."""

    skill: str  # name of the agent skill that must be run to settle this
    reason: str
    question: str
    options: list[str] = field(default_factory=list)
    candidates: list = field(default_factory=list)
    context: dict = field(default_factory=dict)

    # A question comes back where a result was asked for, and host code checks a result the same
    # way every time. Without these it raises AttributeError, the run is rolled back, and the
    # question is asked again from scratch — seen four times in one scenario. So it answers like
    # an unsettled result: nothing matched, here is what it could be, and here is the question.
    @property
    def matched(self) -> bool:
        return False

    @property
    def matches(self) -> list:
        """None of them: that is what an unsettled search is. `.main` says so in words."""
        from terraweaver.matching import Matches

        return Matches([], "matches")

    @property
    def similar(self) -> list:
        from terraweaver.matching import Matches

        # A list that says what it is when it is mistaken for an entity: the same courtesy a
        # search result gives, since a question is what a search returns when it can't settle.
        return Matches(list(self.candidates), "similar")

    def __len__(self) -> int:
        return 0

    def __iter__(self):
        return iter(())

    def __bool__(self) -> bool:
        return True  # it is something, and it must not read as "nothing came back"

    # Writing to something that is still a question: held, not refused. Refusing raised, and a
    # raise discards the whole run — so one unanswerable person in a list of four took the other
    # three down with her, including the ones nothing was wrong with. Reads still raise: there
    # is no honest value to give back for "what is this one's email".
    HELD = ("relate", "tag", "untag", "add", "drop", "describe", "keep", "repeat", "expire",
            "save", "forget", "question")

    # Every word this world has for a link is a call of its own on the class — `set_kin`,
    # `set_membership` — and those are held too. They were not, for a while, and the whole point
    # of holding was lost the moment the typed door moved onto the class: a link written against
    # a name the world could not settle raised instead of waiting, and took the rest of the
    # block with it.
    HELD_PREFIX = "set_"

    def _hold(self, name: str):
        def held(*args, **kwargs):
            self.context.setdefault("held", []).append((name, args, kwargs))
            ontology.note_hint(
                f"{self.reason}: this {name} is held until that is settled — "
                f"world.settle(<this question>, <the one they meant>) applies it, or new=True "
                f"does. Nothing else in this run is affected."
            )
            return None

        return held

    def __getattr__(self, name: str):
        if name.startswith(self.HELD_PREFIX) and not name.startswith("__"):
            return self._hold(name)
        # Reached only for attributes this object doesn't have — usually an entity's, because
        # the host is treating the question as the answer. Say what it is and what settles it,
        # so the next run is the right one rather than the same mistake.
        if name.startswith("_"):
            raise AttributeError(name)
        if name in NeedsResolution.HELD:
            return self._hold(name)
        if name == "main":
            raise AttributeError(
                f"this search didn't settle: {self.reason}. The candidates are in .similar; "
                f"which one is meant is the user's to say — ask, then "
                f"world.settle(<this>, <the one they meant>), or new=True if it is a new one.")
        raise AttributeError(
            f"a question has no {name!r}: this is {self.reason}, not the entity. Print it to see "
            f"the candidates (.similar), ask the user, then world.settle(<this>, <the one they "
            f"meant>) — or new=True if it's a new one."
        )

    def __repr__(self):
        return f"NeedsResolution(skill={self.skill!r}, reason={self.reason!r}, options={self.options!r})"

    def __str__(self):
        return (
            f"NeedsResolution — {self.reason}. Ask the user: {self.question} "
            f"Options: {_numbered(self.options)}. Then call world.settle(<this object>, <the entity the "
            f"user meant>) — or new=True if it's someone new; for a contradiction, pass the value that is right."
        )


def _numbered(options: list[str]) -> str:
    """Numbered from one. These are read out to a person, and nobody offers a nought'th option."""
    return "; ".join(f"{i}) {option}" for i, option in enumerate(options, start=1))


def _is_model(value) -> bool:
    return isinstance(value, Entity)


def _describe(instance) -> str:
    label = _short(instance)
    extras = []
    for attr in ("email", "organization", "city", "status"):
        value = getattr(instance, attr, None)
        if value is not None:
            extras.append(f"{attr}={_short(value)}")
    return label + (f" ({', '.join(extras)})" if extras else "")


def _short(value) -> str:
    # Only model instances get the label treatment — a plain str has a .title *method*,
    # which is exactly how this reads back as "<built-in method title>" if not guarded.
    if _is_model(value):
        for attr in ("full_name", "name", "title"):
            label = getattr(value, attr, None)
            if isinstance(label, str):
                return label
    return str(value)


def ambiguous_identity(class_name: str, incoming: dict, candidates: list, exact: bool = True) -> NeedsResolution:
    options = [_describe(c) for c in candidates] + ["someone new"]
    described = ", ".join(f"{k}={_short(v)}" for k, v in incoming.items() if v is not None)
    # Two different situations, and both the agent and the user should be told which:
    # several entities match equally well, or nothing matches and these merely resemble it.
    reason = (
        f"{len(candidates)} existing {class_name} instance(s) match equally well"
        if exact
        else f"nothing matches exactly; {len(candidates)} {class_name} instance(s) merely resemble it"
    )
    question = (
        f"Which one do you mean ({described})?"
        if exact
        else f"No exact match ({described}). Is it one of these?"
    )
    return NeedsResolution(
        skill="resolve_ambiguity",
        reason=reason,
        question=question,
        options=options,
        candidates=list(candidates),
        context={"class_name": class_name, "incoming": incoming},
    )


def looks_existing(class_name: str, incoming: dict, candidates: list) -> NeedsResolution:
    """The host says it's new, but something just like it is already in the world."""
    needs = ambiguous_identity(class_name, incoming, candidates)
    needs.reason = f"said to be new, but {len(candidates)} {class_name} just like it already exist(s)"
    described = ", ".join(f"{k}={_short(v)}" for k, v in incoming.items() if v is not None)
    needs.question = f"This looks like something already recorded ({described}). The same one, or a new one?"
    return needs


def contradicting_value(instance, attr: str, existing_value, incoming_value) -> NeedsResolution:
    return NeedsResolution(
        skill="resolve_contradiction",
        reason=f"stored {attr} disagrees with the new information",
        question=(
            f"For {_describe(instance)} the record says {attr} = {_short(existing_value)}, "
            f"but now it's {_short(incoming_value)}. Did it change, is the record right, or is "
            f"this a different {type(instance).__name__}?"
        ),
        options=[f"{_short(incoming_value)} (it changed)", f"{_short(existing_value)} (as recorded)",
                 f"a different {type(instance).__name__}"],
        candidates=[instance],
        context={"attr": attr, "existing": existing_value, "incoming": incoming_value},
    )


def _apply_held(world, needs: NeedsResolution, entity) -> None:
    """Everything that was waiting on this answer, done now that there is one to do it to."""
    for name, args, kwargs in needs.context.pop("held", []):
        if name == "relate_to":                 # the link runs towards this one, not from it
            starts_at, kind = args
            world.relate(starts_at, entity, kind, **kwargs)
            continue
        getattr(entity, name)(*args, **kwargs)


def run_skill(needs: NeedsResolution, ask_user: Callable[[str, list[str]], int], world) -> Any:
    """Run the named skill: put the question to the user and apply their answer.

    If the user doesn't settle it (ask_user returns None or a negative index), the case
    stays UNRESOLVED and the NeedsResolution comes back unchanged — nothing is guessed.
    """
    if needs.skill not in SKILL_KINDS:
        raise ValueError(f"unknown resolution skill: {needs.skill!r}")

    choice = ask_user(needs.question, needs.options)
    settled = choice is not None and 0 <= choice < len(needs.options)
    world.log_resolution(needs, choice if settled else None, RESOLVED if settled else UNRESOLVED)
    if not settled:
        return needs

    if needs.skill == "resolve_ambiguity":
        if choice < len(needs.candidates):
            settled = world.apply_attrs(needs.candidates[choice], needs.context["incoming"])
            world.remember_choice(needs, settled)
            _apply_held(world, needs, settled)
        else:
            settled = world.create(needs.context["class_name"], needs.context["incoming"])
            world.remember_choice(needs, None)
            _apply_held(world, needs, settled)
            # "Someone new" next to someone who answers to the same name is the answer the world
            # can't check: it never sees the conversation, and a host that skipped asking leaves
            # a second Olga behind. The record stands; the doubt is kept (questions.py).
            world.questions.raise_(
                settled, "maybe_the_same",
                f"recorded as new, though {', '.join(c.display_name() for c in needs.candidates[:3])} "
                f"{'was' if len(needs.candidates) == 1 else 'were'} already there — the same one?",
                options=["the same one", "different ones"],
                involves=needs.candidates[:3],
                touches=["identity"],
            )
        if needs.context.get("period"):
            world.apply_period(settled, needs.context["period"])
        return settled

    instance = needs.candidates[0]
    if choice == 0:  # the incoming value wins; the old one goes to history
        world.apply_resolved(instance, needs.context["attr"], needs.context["incoming"])
    elif choice == 2 and needs.context.get("incoming_attrs") is not None:  # not the same one at all
        class_name = needs.context["class_name"]
        try:
            return world.create(class_name, needs.context["incoming_attrs"])
        except TypeError as missing:
            raise ValueError(
                f"to record a different {class_name}, more is needed than was given ({missing}); "
                f"record it with {class_name}.new(...)"
            ) from None
    else:
        world.save(instance)
    return instance
