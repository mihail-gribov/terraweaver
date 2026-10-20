"""The memory of texts with one more door: `run`, where the agent names entities, events and links.

Every call of the baseline is here as it is (`baseline/server.py`) — the same journal, the same
`ask`, `context` and `search_memory` reading all of it — so whatever is measured through the
contract is the baseline's. What is added is `run(code)`: Python with `entity`, `event`, `link`
and `say` in it, whose sentences go to that journal and whose things go to an index beside it
(`proto/model.py`). The object model is small enough to live in the skill's text
(`proto/SKILL.md`), so MCP gains one tool and nothing else.

    .venv/bin/python -m proto.server                     # var/proto/main/, port 7110
    .venv/bin/python -m proto.server --name fc --port 7111

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
    candidates = structure.heard_candidates(taken)
    if not candidates:
        return []
    said = await base._haiku(HEARD.format(
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
    parts = [out.getvalue().rstrip()]
    if failed:
        parts.append(f"Error:\n{failed.rstrip()}")
    if structure.kept:
        # Writes are not undone by an error after them: each was a `tell`, and it was kept.
        parts.append("Kept: " + ", ".join(structure.kept) + ".")
    if structure.asked:
        parts.append("The memory asks:\n" + "\n".join(f"- {q}" for q in structure.asked))
    return "\n\n".join(p for p in parts if p) or "Done."


@base.server.tool()
async def run(code: str, ctx: Context, now: str | None = None) -> str:
    """Run Python against the user's memory: `entity`, `event`, `link`, `x.say(...)`,
    `x.about()`, `same`, `different`, `thing(id)`, as the skill describes. Variables persist
    between runs of this session. Every fact is a sentence that names what it is about. `now` is
    the current date and time as you know them (2026-10-15T14:30): when these facts were said."""
    async with base.writing:
        return run_code(code, session_of(ctx), now)


def main() -> None:
    global structure
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--name", default="main", help="var/proto/<name>/: facts.md and structure.jsonl")
    parser.add_argument("--model", default="haiku", help="the model that reads the journal")
    parser.add_argument("--port", type=int, default=7110)
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
    where = base.ROOT / "var" / "proto" / args.name
    base.facts, base.model = where / "facts.md", args.model
    structure = Structure(where / "structure.jsonl", base._keep, held)
    base.serve(args.port)


if __name__ == "__main__":
    main()
