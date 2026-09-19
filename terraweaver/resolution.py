"""Uncertainty/contradiction hand-off: what the world returns instead of guessing.

When a deterministic check can't settle a case on its own, the world layer doesn't
pick an answer and it doesn't ask an LLM — it returns a NeedsResolution naming the
skill the agent must run. That skill resolves the situation in dialogue with the
user, so an ambiguity is settled by the person who actually knows, not by inference.
"""
from dataclasses import dataclass, field
from typing import Any, Callable

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

    def __repr__(self):
        return f"NeedsResolution(skill={self.skill!r}, reason={self.reason!r}, options={self.options!r})"

    def __str__(self):
        return (
            f"NeedsResolution — {self.reason}. Ask the user: {self.question} "
            f"Options: {_numbered(self.options)}. Then call world.settle(<this object>, <the entity the "
            f"user meant>) — or new=True if it's someone new; for a contradiction, pass the value that is right."
        )


def _numbered(options: list[str]) -> str:
    return "; ".join(f"{i}) {option}" for i, option in enumerate(options))


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
        else:
            settled = world.create(needs.context["class_name"], needs.context["incoming"])
            world.remember_choice(needs, None)
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
