"""Looking something up outside: what may be asked, and what may never leave.

A query is a sentence handed to a stranger. Whatever goes into one has left this world for good,
so the world does not decide for itself when to ask. Two cases, and nothing else:

- **a check we named in advance.** What a kind of thing is, how a kind of link behaves, the
  registered name behind a trading name. Questions about the world, not about the person; the
  answers are checkable and reveal nothing by being asked.
- **something the person asked about.** "I'm interested in a BMW X5, 2026" — then looking it up
  is doing as told, and the words of the query are theirs.

Everything else is refused here rather than judged. In particular, a query for one of our own
checks may not carry anything the person told us — no name from this world, no address, no
number. The guard is mechanical: the query is read against what the world holds, and if any of
it turns up, the lookup doesn't happen.

Nothing in this module reaches the network. It decides what may be asked; the asking is work for
the agenda, one ticket at a time, on a budget.
"""
import re

from terraweaver import matching

# What the world is allowed to ask on its own account, and what each one is for. A purpose that
# isn't here is not a purpose — adding one is a deliberate change, reviewed like any other.
ALLOWED = {
    "what_is": "a kind of thing this world has no concept for — a doula, a tontine",
    "link_properties": "how a kind of link behaves: one at a time, both ways round, cycles",
    "public_name": "the registered name behind a trading name, for a company already named",
    "place": "a place: how it is spelled, what country it is in",
    "asked_for": "something the person asked us to look into — their words, their call",
}

_CONTACT = re.compile(r"[\w.+-]+@[\w-]+\.\w+|\+?\d[\d\s()-]{6,}")


class NotAllowed(Exception):
    """The lookup doesn't happen, and the reason names what would have leaked."""


def check(world, purpose: str, query: str) -> str:
    """The query as it may be sent, or NotAllowed. Nothing is sent from here."""
    if purpose not in ALLOWED:
        raise NotAllowed(
            f"{purpose!r} isn't something the world looks up on its own. It may ask about "
            f"{', '.join(sorted(ALLOWED))} — anything else is the person's to ask for."
        )
    if purpose == "asked_for":
        return query  # their words, their call
    if _CONTACT.search(query):
        raise NotAllowed("a query may not carry an address or a number: it would leave this world")
    intruder = _personal(world, query)
    if intruder:
        raise NotAllowed(
            f"{intruder!r} is someone in this world, and a search would hand their name to a "
            f"stranger. Ask about the kind of thing instead, or let the person ask for it."
        )
    return query


def _personal(world, query: str) -> str | None:
    """Anything in the query that this world knows as a person — their name, in any of its forms."""
    words = set(matching.normalize(query).split())
    for class_name in ("Person", "AIAgent"):
        if class_name not in world.classes:
            continue
        name_key = matching.NAME_KEYS.get(class_name)
        for entity in world.all(class_name, limit=None, history=True):
            for name in matching.known_names(entity, name_key):
                parts = matching.normalize(name).split()
                if len(parts) > 1 and all(part in words for part in parts):
                    return name  # their full name, however it was written
                if len(parts) == 1 and parts[0] in words and len(parts[0]) > 3:
                    return name
    return None
