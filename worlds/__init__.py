"""Named world fixtures.

A world is a prepared situation: who the user is, who they know, what they're in the
middle of. Keeping several lets the same agent be played against different situations
instead of one fixture quietly becoming the definition of "the world".
"""
from importlib import import_module

DEFAULT_WORLD = "job_search"


def load_world(name: str = DEFAULT_WORLD):
    """Return the builder for a named world: build(classes, store) -> None."""
    return import_module(f"worlds.{name}").build
