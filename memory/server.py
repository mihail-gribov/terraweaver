"""The memory of texts with one more door: `run`, where the agent names entities, events and links.

Every call of the baseline is here as it is (`memory/journal.py`) — the same journal, the same
`ask`, `context` and `search_memory` reading all of it — so whatever is measured through the
contract is the baseline's. What is added is `run(code)`: Python with `entity`, `event`, `link`
and `say` in it, whose sentences go to that journal and whose things go to an index beside it
(`memory/model.py`). The object model is small enough to live in the skill's text
(`memory/SKILL.md`). And `task(text)`: a task in the user's words, which the memory solves by a
program it writes or reuses (`memory/solve.py`) — from what it holds, and from the web when the
task needs it.

    .venv/bin/python -m memory.server                     # var/memory/main/, port 7110
    .venv/bin/python -m memory.server --name fc --port 7111
    .venv/bin/python -m memory.server --host 0.0.0.0      # the local network, behind a token

A run's variables last between runs of one session: the `x-terraweaver-session` header if the
host sends one, otherwise the client's name (the MCP protocol is stateless, 2026-07-28).
"""
import argparse
import asyncio
import contextlib
import io
import logging
import os
import traceback
from datetime import datetime

from mcp.server.mcpserver import Context

from memory import journal as base
from memory.model import Structure

SESSION_HEADER = "x-terraweaver-session"
structure: Structure
sessions: dict[str, dict] = {}
# The world the journal is said into and read by (memory/world.py), when there is one; and the
# search the readers are shown entries by (memory/search.py).
world = None
search = None
# The graph: the texts, the entities they mention and the links between them (memory/graph.py).
graph = None
# Which memory this is (var/memory/<name>), and the search engine tasks use.
name, engine = "main", "tavily"


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
    if graph is not None:
        # Derived from the journal: read again without what was forgotten.
        graph.rebuild()
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
    "not settle, call `ask`. For a task that needs gathering, comparing or choosing — pick me a "
    "product, find out what an event is and when, what we spent on something, who of my people … — "
    "call `task` with it in the user's words: the memory gathers the facts for it, from what it "
    "holds and from the web, in a few minutes; the decision is yours, with the user. `questions` lists what the memory wants to ask the user."
)


@base.server.tool()
async def run(code: str, ctx: Context, now: str | None = None) -> str:
    """Run Python against the user's memory: `entity`, `event`, `link`, `x.say(...)`,
    `x.about()`, `same`, `different`, `thing(id)`, as the skill describes. Variables persist
    between runs of this session. Every fact is a sentence that names what it is about. `now` is
    the current date and time as you know them (2026-10-15T14:30): when these facts were said."""
    async with base.writing:
        return run_code(code, session_of(ctx), now)


def confirm_forget(what: str, entry: str) -> bool:
    """Is this entry what the user asked to forget, or only something the request names to say
    which one? A closed question, for the decision model; kept when it can't be asked."""
    from memory.models import role
    try:
        p = role("judge").noul(f'The user asked the memory to forget: "{what}"\n\nAn entry of the memory:\n"{entry}"',
                               "Does this entry say anything about the person or thing the user wants forgotten?",
                               true="yes, it says something about it", false="no, it says nothing about it")["p"]["yes"]
    except Exception:  # noqa: BLE001 - not asked: the reader's choice stands
        return True
    # On the Olga request, entries about her read 0.68–0.75, the user's own at Lumen 0.36–0.47;
    # asked "is this entry about what is to be forgotten", it said yes to all five (2026-10-27).
    return p >= 0.55


@base.server.tool()
async def task(text: str, ctx: Context) -> str:
    """Gather the facts a task needs: candidates for a product, what an event is and when it is
    on, sums over what the user told — anything that needs gathering, checking and comparing.
    The memory gives facts and does not decide: choosing is yours, with the user. Give it in the
    user's words; what the memory knows about the user — limits, wishes,
    people, places — it adds itself, so don't restate it. It writes a program for the task, or
    reuses one it kept for a task of the same kind, and runs it: from the memory, and from the web
    when needed. Takes a few minutes. Returns what was found, how each candidate stands on the user's limits
    and wishes with the words each stands on, what was ruled out, and the user's limits and wishes
    as they said them."""
    from memory import solve

    out = base.ROOT / "var" / "solve" / f"{name}-{datetime.now():%Y%m%d-%H%M%S}"
    out.mkdir(parents=True, exist_ok=True)
    # In a thread: a task takes minutes, and the memory keeps answering meanwhile. And it says it
    # is alive: a client that hears nothing for five minutes gives up on the call (Claude Code did,
    # 2026-10-27), so a progress notification goes every twenty seconds until the answer.
    work = asyncio.ensure_future(asyncio.to_thread(solve.run, text, name, engine, 2, out))
    beat = 0
    while not work.done():
        await asyncio.wait({work}, timeout=20)
        if not work.done():
            beat += 1
            try:
                await ctx.report_progress(beat, None, f"working on the task: {beat * 20} s")
            except Exception:  # noqa: BLE001 - a client that takes no progress still gets the answer
                pass
    return work.result()


listener = None
# What every MCP client is told, when the agent passes the conversation itself (no hooks).
TWO_DOORS = (
    "The user's personal memory. Pass it the conversation as it goes with `say`: each message of "
    "the user's that touches their life — themselves, the people in it, home, health, work, plans, "
    "wishes, what happened, a question about any of it, a request to find, pick or forget "
    "something — as written, with your reply before it ({\"role\": \"agent\"}). What you read "
    "(mail, files, pages) reaches it when you tell the user and they answer. It keeps "
    "what matters and answers with what it holds that bears on it. When you need something about "
    "the user, or something found for them, `ask` it. The memory gives facts, with the words they "
    "stand on; deciding is yours, with the user."
)


def _solve(text: str) -> str:
    from memory import solve
    out = base.ROOT / "var" / "solve" / f"{name}-{datetime.now():%Y%m%d-%H%M%S}"
    out.mkdir(parents=True, exist_ok=True)
    return solve.run(text, name, engine, 2, out)


def _journal_changed() -> None:
    if graph is not None:
        graph.wake()
    if world is not None:
        world.send("sync", structure, held())


async def say(messages: list[dict], ctx: Context, now: str | None = None) -> str:
    """Pass the conversation to the user's memory as it goes: each message as written, with who
    said it — {"role": "user", "text": ...}, {"role": "agent", "text": ...} for your own reply
    before it. Every message that touches the user's life; what you read reaches the memory when
    the user answers it. The memory keeps what is worth keeping, and
    answers with what it holds that bears on it — facts, with the words they stand on; deciding
    is yours, with the user. A question of the user's is kept as their interest, not answered
    here: `ask` the memory for what you need, and for anything to be found. A request to forget is
    done once the user confirms. `now`: the current date and time."""
    if hooked(ctx):
        return HOOKED
    return await listener.say(messages, now, wait=True, progress=_beat(ctx))


# A client whose hooks pass every message (the Claude Code plugin says so in its .mcp.json) is not
# heard through `say` as well: the same message would be kept twice. The header is the client's
# word, not an identity — enough to stop a duplicate, nothing is opened by it.
HOOKS_HEADER = "x-personal-hooks"
HOOKED = ("Not taken: your client's hooks already pass every message of this conversation to the "
          "memory. Pass nothing yourself; `ask` it for what you need.")


def hooked(ctx: Context) -> bool:
    try:
        headers = ctx.headers or {}
    except ValueError:  # outside a request
        return False
    return str(headers.get(HOOKS_HEADER, "")).lower() == "on"


async def ask(question: str, ctx: Context) -> str:
    """Ask the user's memory something you need: "what is Tom's surname?", "what limits a purchase
    for the flat?", or ask it to find something — "candlelight concerts in Belgrade this winter" —
    which takes a few minutes. It answers with facts and the words they stand on, from what it
    holds and, for a search, from the web; the decision is yours, with the user."""
    return await listener.ask(question, wait=True, progress=_beat(ctx))


def _beat(ctx: Context):
    async def beat(n: int) -> None:
        try:
            await ctx.report_progress(n, None, f"gathering: {n * 20} s")
        except Exception:  # noqa: BLE001 - a client that takes no progress still gets the answer
            pass
    return beat


@base.server.custom_route("/say", ["POST"])
async def http_say(request):
    """`say` for a hook: {"messages": [...]}, or {"message": ..., "role": ...}. Answers at once with
    what the memory holds that bears on it; nothing is searched for from here."""
    from starlette.responses import PlainTextResponse
    body = await request.json()
    messages = body.get("messages") or [{"role": body.get("role", "user"), "text": body.get("message", ""),
                                         "source": body.get("source", "")}]
    return PlainTextResponse(await listener.say(messages, body.get("now"), wait=bool(body.get("wait", False))))


# The journal has an /ask of its own, the question alone; registered first, it took every call and
# this one was never reached — `now` and `gather` were lost, so LongMemEval's memory answered as of
# the machine's day (found 2026-10-29). The journal's goes; this one is the memory's.
base.server._custom_starlette_routes[:] = [r for r in base.server._custom_starlette_routes
                                           if getattr(r, "path", None) != "/ask"]


@base.server.custom_route("/ask", ["POST"])
async def http_ask(request):
    """`ask` over HTTP, for runners outside an agent: {"question": ..., "gather": false, "now": ...}
    answers from what the memory holds only, as of `now`."""
    from starlette.responses import PlainTextResponse
    body = await request.json()
    return PlainTextResponse(await listener.ask(body.get("question", ""), wait=True,
                                                gather=bool(body.get("gather", True)), now=body.get("now")))


@base.server.custom_route("/interests", ["GET"])
async def http_interests(request):
    """What the user wanted to know, and whether an answer is ready: for a look, not for the agent."""
    from starlette.responses import JSONResponse
    return JSONResponse(listener.interests())


@base.server.custom_route("/notes", ["GET"])
async def http_notes(request):
    """What the memory came to since it last answered, waiting up to `wait` seconds for it."""
    from starlette.responses import PlainTextResponse
    until = asyncio.get_running_loop().time() + float(request.query_params.get("wait", 0))
    while not listener.notes and asyncio.get_running_loop().time() < until:
        await asyncio.sleep(2)
    return PlainTextResponse("\n\n".join(listener.take_notes()) or "nothing")


def main() -> None:
    global structure, world, graph, search, name, engine, listener
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--name", default="main", help="var/memory/<name>/: facts.md and structure.jsonl")
    parser.add_argument("--model", default="nvidia/nemotron-3-super-120b-a12b",
                        help="the model that reads the journal: Token Factory, or `haiku` via the claude CLI")
    parser.add_argument("--port", type=int, default=7110)
    parser.add_argument("--host", default="127.0.0.1",
                        help="0.0.0.0 to serve the local network, behind a bearer token")
    parser.add_argument("--engine", default="tavily", help="the search engine `task` uses: tavily, keenable")
    parser.add_argument("--tools", choices=["two", "all"], default="two",
                        help="two: the agent sees `say` and `ask` only; all: every call, for experiments")
    parser.add_argument("--no-world", action="store_true",
                        help="keep the journal and the index only: nothing read into a graph or a world")
    parser.add_argument("--world", action="store_true",
                        help="the older world (memory/world.py, the ontology engine) instead of the graph")
    args = parser.parse_args()
    if not os.environ.get("NEBIUS_API_KEY"):
        # Without it every read fails and the memory only keeps words as said: a run that looks
        # alive and answers nothing (2026-10-29, a vacuum run started without .env).
        raise SystemExit("NEBIUS_API_KEY is not set: the memory's models are on Nebius Token Factory. "
                         "set -a; . ./.env; set +a")

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
    where = base.ROOT / "var" / "memory" / args.name
    name, engine = args.name, args.engine
    base.facts, base.model = where / "facts.md", args.model
    structure = Structure(where / "structure.jsonl", base._keep, held)
    if args.world:
        from memory.world import Worker
        world = Worker(where / "world")
    elif not args.no_world:
        from memory.graph import Graph
        graph = Graph(where / "graph", lambda: base._entries(base._memory()))
        base.graph_facts = graph.facts_for
    # Readers are shown what the search finds, not the whole journal: every entry about a thing
    # the question names, and twelve more by words and meaning (docs/decisions.md, 2026-10-20).
    from memory.search import Search
    search = Search(structure, lambda: {n: t for n, _, t in base._entries(base._memory())},
                    where / "vectors.jsonl", image=(lambda: world.image) if world else None)
    base.narrow = lambda question: search.find(question, limit=12)
    base.confirm_forget = confirm_forget
    from memory.listen import Listener
    listener = Listener(base, base._keep, base.context, base.ask, _solve, _journal_changed,
                        interests_path=where / "interests.jsonl", heard_path=where / "heard.jsonl",
                        embed=lambda texts: search._encoder().embed(texts))
    listener.load_interests()
    # Two doors (docs/decisions.md, 2026-10-27): the conversation goes in by `say` — from a hook,
    # where the agent has hooks, or from the agent — and the agent asks by `ask`. The rest stays
    # for experiments and tests, behind --tools all.
    if args.tools == "two":
        for tool in [t.name for t in asyncio.run(base.server.list_tools())]:
            base.server.remove_tool(tool)
        base.server._lowlevel_server.instructions = TWO_DOORS
    else:
        base.server.remove_tool("ask")
    base.server.add_tool(say, name="say")
    base.server.add_tool(ask, name="ask")
    base.serve(args.port, args.host)


if __name__ == "__main__":
    main()
