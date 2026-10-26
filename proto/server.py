"""The memory of texts with one more door: `run`, where the agent names entities, events and links.

Every call of the baseline is here as it is (`baseline/server.py`) — the same journal, the same
`ask`, `context` and `search_memory` reading all of it — so whatever is measured through the
contract is the baseline's. What is added is `run(code)`: Python with `entity`, `event`, `link`
and `say` in it, whose sentences go to that journal and whose things go to an index beside it
(`proto/model.py`). The object model is small enough to live in the skill's text
(`proto/SKILL.md`), so MCP gains one tool and nothing else.

    .venv/bin/python -m proto.server                     # var/proto/main/, port 7110
    .venv/bin/python -m proto.server --name fc --port 7111
    .venv/bin/python -m proto.server --host 0.0.0.0      # the local network, behind a token

A run's variables last between runs of one session: the `x-terraweaver-session` header if the
host sends one, otherwise the client's name (the MCP protocol is stateless, 2026-07-28).
"""
import argparse
import contextlib
import io
import logging
import traceback
from datetime import datetime

from mcp.server.mcpserver import Context

from baseline import server as base
from proto.model import Structure

SESSION_HEADER = "x-terraweaver-session"
structure: Structure
sessions: dict[str, dict] = {}
# The world the journal is said into and read by (proto/world.py), when there is one; and the
# search the readers are shown entries by (proto/search.py).
world = None
search = None


HEARD = """Below are sentences the user said, numbered.

{sentences}

At the user's request, these entries were just forgotten:

{entries}

Which sentences say any of what those entries said? Answer with their numbers, comma-separated, \
or the single word: none."""


async def forgot(taken: list[tuple[int, str]], request: int, to_bin) -> list[str]:
    """The journal's forget, carried to the structure: the kept request is tied to the same
    things, and what was heard is taken out where it says what was forgotten — or the words the
    user asked to be rid of stay on disk for good, in the message they came in."""
    structure.forgot([n for n, _ in taken], request)
    if search is not None:
        search.drop([n for n, _ in taken])
    if world is not None:
        # Waited for: the words are out of the world before the user is told they are gone.
        world.send("forget", taken, wait=True)
    candidates = structure.heard_candidates(taken)
    if not candidates:
        return []
    said = await base._read(HEARD.format(
        sentences="\n".join(f"{i}. {sentence}" for i, (_, sentence) in enumerate(candidates, 1)),
        entries="\n".join(f"- {text}" for _, text in taken)))
    chosen = [candidates[i - 1] for i in base._numbers(said, set(range(1, len(candidates) + 1)), len(candidates))]
    if not chosen:
        return []
    # Into the bin first, then out of heard.md: never nowhere.
    to_bin([{"heard": k, "text": sentence} for k, sentence in chosen])
    taken_heard = structure.forget_heard(chosen)
    return ["- heard #%d: %s" % (k, sentence) for k, sentence in taken_heard]


base.on_forget.append(forgot)


def session_of(ctx: Context | None) -> str:
    if ctx is None:
        return "default"
    headers = ctx.headers or {}
    if headers.get(SESSION_HEADER):
        return headers[SESSION_HEADER]
    client = (ctx.request_context.meta or {}).get("io.modelcontextprotocol/clientInfo") or {}
    return client.get("name") or "default"


def held() -> dict[int, str]:
    """The journal's entries as a reader gets them, by number."""
    return {n: base._as_entry(heading, text) for n, heading, text in base._entries(base._memory())}


def when(now: str | None) -> tuple[datetime | None, str]:
    """The agent's now, read; and what to ask if it could not be read."""
    if not (now or "").strip():
        return None, ("Pass `now`, the current date and time as you know them, with every run: it "
                      "is when these facts were said. This run took the memory's own clock.")
    try:
        return datetime.fromisoformat(now.strip()), ""
    except ValueError:
        return None, (f"`now` = {now!r} could not be read; pass it as 2026-10-15 or "
                      f"2026-10-15T14:30. This run took the memory's own clock.")


def run_code(code: str, session: str, now: str | None = None) -> str:
    """Run the agent's code in its session's namespace; answer with what it printed, what it
    kept, and what the memory asks back."""
    namespace = sessions.setdefault(session, {"__builtins__": __builtins__})
    namespace.update(structure.namespace(session))
    structure.asked, structure.kept = [], []
    told, unread = when(now)
    if told:
        structure.now[session] = told
    else:
        structure.now.pop(session, None)
        structure.asked.append(unread)
    out = io.StringIO()
    try:
        with contextlib.redirect_stdout(out):
            exec(compile(code, "<run>", "exec"), namespace)
        failed = ""
    except Exception:  # noqa: BLE001 - the agent's error is the agent's to read
        failed = "".join(traceback.format_exc().splitlines(keepends=True)[-3:])
    structure.check_heard(session)
    if world is not None:
        world.send("sync", structure, held())
    parts = [out.getvalue().rstrip()]
    if failed:
        parts.append(f"Error:\n{failed.rstrip()}")
    if structure.kept:
        # Writes are not undone by an error after them: each was a `tell`, and it was kept.
        parts.append("Kept: " + ", ".join(structure.kept) + ".")
    if structure.asked:
        parts.append("The memory asks:\n" + "\n".join(f"- {q}" for q in structure.asked))
    return "\n\n".join(p for p in parts if p) or "Done."


# The baseline tells the agent to keep facts with `tell`; here they are kept with `run`, which
# says whom each fact is about. Measured 2026-10-26: under the baseline's words a host with the
# plugin read with `context` and kept nothing.
base.server._lowlevel_server.instructions = (
    "The user's personal memory. Before answering anything that may touch the user's life — "
    "people, plans, places, preferences, what happened — call `context` with the user's message. "
    "When the user says something about themselves or the people and things in their life, keep "
    "it at once, before the task they asked for, with `run`: Python where `entity`, `event` and "
    "`link` name what the fact is about and `x.say(text)` states it — "
    "`anna = entity(\"Anna\", \"Anna is the user's sister.\", kind=\"person\")`, then "
    "`anna.say(\"Anna moved from Lisbon to Porto in September 2026.\")`. Every text stands alone, "
    "with names and absolute dates; pass `now` with every run. For a question the context did "
    "not settle, call `ask`. `questions` lists what the memory wants to ask the user."
)


@base.server.tool()
async def run(code: str, ctx: Context, now: str | None = None) -> str:
    """Run Python against the user's memory: `entity`, `event`, `link`, `x.say(...)`,
    `x.about()`, `same`, `different`, `thing(id)`, as the skill describes. Variables persist
    between runs of this session. Every fact is a sentence that names what it is about. `now` is
    the current date and time as you know them (2026-10-15T14:30): when these facts were said."""
    async with base.writing:
        return run_code(code, session_of(ctx), now)


def main() -> None:
    global structure, world, search
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--name", default="main", help="var/proto/<name>/: facts.md and structure.jsonl")
    parser.add_argument("--model", default="nvidia/nemotron-3-super-120b-a12b",
                        help="the model that reads the journal: Token Factory, or `haiku` via the claude CLI")
    parser.add_argument("--port", type=int, default=7110)
    parser.add_argument("--host", default="127.0.0.1",
                        help="0.0.0.0 to serve the local network, behind a bearer token")
    parser.add_argument("--no-world", action="store_true",
                        help="keep the journal and the index only: no world said into, nothing read")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
    where = base.ROOT / "var" / "proto" / args.name
    base.facts, base.model = where / "facts.md", args.model
    structure = Structure(where / "structure.jsonl", base._keep, held)
    if not args.no_world:
        from proto.world import Worker
        world = Worker(where / "world")
    # Readers are shown what the search finds, not the whole journal: every entry about a thing
    # the question names, and twelve more by words and meaning (docs/decisions.md, 2026-10-20).
    from proto.search import Search
    search = Search(structure, lambda: {n: t for n, _, t in base._entries(base._memory())},
                    where / "vectors.jsonl", image=(lambda: world.image) if world else None)
    base.narrow = lambda question: search.find(question, limit=12)
    base.serve(args.port, args.host)


if __name__ == "__main__":
    main()
