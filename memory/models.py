"""The models the world works with, by the role each plays — never by a model's name in the code.

    from memory.models import role
    role("reader").say(...)          # an LLM in that role
    role("judge").noul(...)          # the decision model

A role is bound to a model here, and any binding is changed by the environment —
TERRAWEAVER_PROGRAMMER=nvidia/… — so a stronger or cheaper model takes a role without a line of
code changing. Every client is `terraweaver/nemotron.py`, which reads a model as an LLM and as a
decision model, calibrated for the models it was fitted on.
"""
import os

from terraweaver.nemotron import Nemotron

ROLES = {
    # Writes the program that solves a task, and sorts the user's limits from wishes: one call
    # each, the hardest writing the world does — the strongest Nemotron.
    "programmer": "nvidia/Nemotron-3-Ultra-550b-a55b",
    # Reads texts into things, values and links, and answers from the memory: hundreds of calls.
    "reader": "nvidia/nemotron-3-super-120b-a12b",
    # Closed questions as probabilities — does this quote say that claim? One token, calibrated.
    "judge": "nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B",
    # Sorts what the memory hears (memory/listen.py): personal or not, a question, a request, a
    # forget, a repeat, a faithful retelling. The decision model on the middle Nemotron for now —
    # the user's call (2026-10-27) — until the questions are measured and a smaller one may do.
    "sorter": "nvidia/nemotron-3-super-120b-a12b",
    # Resolves what the user's message points to in the agent's message before it, and takes its
    # questions out (memory/intake/). Tried on the small Nemotron first, the user's call: on 2026-10-28 it
    # copied the prompt's examples into the answer and made questions of statements; on Super.
    "resolver": "nvidia/nemotron-3-super-120b-a12b",
}

_held: dict[str, Nemotron] = {}


def model_of(name: str) -> str:
    if name not in ROLES:
        raise ValueError(f"No role {name!r}; the roles are {sorted(ROLES)}.")
    return os.environ.get(f"TERRAWEAVER_{name.upper()}", ROLES[name])


def role(name: str) -> Nemotron:
    """The client for a role, made once."""
    if name not in _held:
        _held[name] = Nemotron(model=model_of(name), timeout=600 if name == "programmer" else 300)
    return _held[name]
