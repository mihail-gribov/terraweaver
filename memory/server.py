"""The user's personal memory, served to an agent through two doors.

`say` takes the conversation as it goes: from a hook that passes every message, or from the agent.
`ask` answers the agent's questions from what the memory holds. Behind them: the journal of the
user's own words (`memory/journal.py`), the intake that keeps what is personal (`memory/intake/`),
the graph read from the journal — topics, portraits and the user's world (`memory/graph.py`) —
and the search the readers are shown entries by (`memory/search.py`).

    .venv/bin/python -m memory.server                     # var/memory/main/, port 7110
    .venv/bin/python -m memory.server --name demo --port 7111
    .venv/bin/python -m memory.server --host 0.0.0.0      # the local network, behind a token
    .venv/bin/python -m memory.server --dir /media/usb/my-memory   # the whole memory in one folder
"""
import argparse
import asyncio
import logging
import os
from pathlib import Path

from mcp.server.mcpserver import Context

from memory import journal as base

# The search the readers are shown entries by (memory/search.py), and the graph: the texts, the
# entities they mention and the links between them (memory/graph.py).
search = None
graph = None


async def forgot(taken: list[tuple[int, str]], request: int, to_bin) -> list[str]:
    """The journal's forget, carried to what is derived from it: the vectors go, and the graph is
    read again without what was forgotten."""
    if search is not None:
        search.drop([n for n, _ in taken])
    if graph is not None:
        graph.rebuild()
    return []


base.on_forget.append(forgot)


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



listener = None
# What every MCP client is told, when the agent passes the conversation itself (no hooks).
TWO_DOORS = (
    "The user's personal memory. Pass it the conversation as it goes with `say`: each message of "
    "the user's that touches their life — themselves, the people in it, home, health, work, plans, "
    "wishes, what happened, a question about any of it, a request to forget something — as written, with your reply before it ({\"role\": \"agent\"}). What you read "
    "(mail, files, pages) reaches it when you tell the user and they answer. It keeps "
    "what matters and answers with what it holds that bears on it. When you need something about "
    "the user, `ask` it. The memory gives facts, with the words they "
    "stand on; deciding is yours, with the user."
)


async def say(messages: list[dict], ctx: Context, now: str | None = None) -> str:
    """Pass the conversation to the user's memory as it goes: each message as written, with who
    said it — {"role": "user", "text": ...}, {"role": "agent", "text": ...} for your own reply
    before it. Every message that touches the user's life; what you read reaches the memory when
    the user answers it. The memory keeps what is worth keeping, and
    answers with what it holds that bears on it — facts, with the words they stand on; deciding
    is yours, with the user. A question of the user's is kept as their interest, not answered
    here: `ask` the memory for what you need. A request to forget is
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
    for the flat?", "what did we decide about the TV?". It answers with facts and the words they
    stand on, from what it holds; the decision is yours, with the user."""
    return await listener.ask(question, wait=True, progress=_beat(ctx))


def _beat(ctx: Context):
    async def beat(n: int) -> None:
        try:
            await ctx.report_progress(n, None, f"gathering: {n * 20} s")
        except Exception:  # noqa: BLE001 - a client that takes no progress still gets the answer
            pass
    return beat


# The journal's own routes go, every one: its /ask, registered first, took every call and this
# one was never reached (2026-10-29), and /tell, /add_memory, /forget, /debug/facts wrote, forgot and
# showed the journal past the gate, the secrets filter and the user's confirmation (review W0001,
# 2026-10-30). The memory's routes are registered below; only they are served.
base.server._custom_starlette_routes.clear()


@base.server.custom_route("/say", ["POST"])
async def http_say(request):
    """`say` for a hook: {"messages": [...]}, or {"message": ..., "role": ...}. Answers at once with
    what the memory holds that bears on it; nothing is searched for from here."""
    from starlette.responses import PlainTextResponse
    body = await request.json()
    messages = body.get("messages") or [{"role": body.get("role", "user"), "text": body.get("message", ""),
                                         "source": body.get("source", "")}]
    return PlainTextResponse(await listener.say(messages, body.get("now"), wait=bool(body.get("wait", False))))




@base.server.custom_route("/ask", ["POST"])
async def http_ask(request):
    """`ask` over HTTP, for runners outside an agent: {"question": ..., "gather": false, "now": ...}
    answers from what the memory holds only, as of `now`."""
    from starlette.responses import PlainTextResponse
    body = await request.json()
    if graph is not None and body.get("settle"):
        # A benchmark tells a whole history at once and asks at once: every entry read first.
        await asyncio.to_thread(graph.wait, 7200)
    return PlainTextResponse(await listener.ask(body.get("question", ""), wait=True,
                                                gather=bool(body.get("gather", True)), now=body.get("now")))


@base.server.custom_route("/interests", ["GET"])
async def http_interests(request):
    """What the user wanted to know, and whether an answer is ready: for a look, not for the agent."""
    from starlette.responses import JSONResponse
    return JSONResponse(listener.interests())


@base.server.custom_route("/world", ["GET"])
async def http_world(request):
    """The user's world as the memory has filled it so far: every person it knows of, each with every
    part a person has, filled or empty, what holds now and what was, with facts and days."""
    from starlette.responses import JSONResponse
    if graph is None:
        return JSONResponse({})
    def read():
        with graph.lock:
            return graph.world()
    return JSONResponse(await asyncio.to_thread(read))


@base.server.custom_route("/settle", ["GET"])
async def http_settle(request):
    """Until every kept entry is read into the graph, up to `wait` seconds: for a demo or a run that
    tells a history and then wants it read before the next message."""
    from starlette.responses import PlainTextResponse
    done = graph is None or await asyncio.to_thread(graph.wait, float(request.query_params.get("wait", 600)))
    return PlainTextResponse("read" if done else "still reading")


@base.server.custom_route("/notes", ["GET"])
async def http_notes(request):
    """What the memory came to since it last answered, waiting up to `wait` seconds for it."""
    from starlette.responses import PlainTextResponse
    until = asyncio.get_running_loop().time() + float(request.query_params.get("wait", 0))
    while not listener.notes and asyncio.get_running_loop().time() < until:
        await asyncio.sleep(2)
    return PlainTextResponse("\n\n".join(listener.take_notes()) or "nothing")


def _journal_changed() -> None:
    if graph is not None:
        graph.wake()


def main() -> None:
    global graph, search, listener
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--name", default="main", help="var/memory/<name>/: facts.md and what is read from it")
    parser.add_argument("--dir", default=None, help="the memory's folder anywhere, a USB stick included: the user's "
                        "whole memory is this one folder of plain files (overrides --name)")
    parser.add_argument("--engine", default="tavily", help="tavily: topics are extended from the web; off: no "
                        "web at all (a benchmark measures the memory, not the web)")
    parser.add_argument("--model", default="nvidia/Nemotron-3.5-Super-VL",
                        help="the model that reads the journal: Token Factory, or `haiku` via the claude CLI")
    parser.add_argument("--port", type=int, default=7110)
    parser.add_argument("--host", default="127.0.0.1",
                        help="0.0.0.0 to serve the local network, behind a bearer token")
    parser.add_argument("--no-graph", action="store_true",
                        help="keep the journal and the search only: nothing read into a graph")
    args = parser.parse_args()
    if not os.environ.get("NEBIUS_API_KEY"):
        # Without it every read fails and the memory only keeps words as said: a run that looks
        # alive and answers nothing (2026-10-29, a vacuum run started without .env).
        raise SystemExit("NEBIUS_API_KEY is not set: the memory's models are on Nebius Token Factory. "
                         "set -a; . ./.env; set +a")

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
    where = Path(args.dir).expanduser().resolve() if args.dir else base.ROOT / "var" / "memory" / args.name
    base.facts, base.model = where / "facts.md", args.model
    # Readers are shown what the search finds, not the whole journal: every entry by words and
    # meaning, twelve of them (docs/decisions.md, 2026-10-20).
    from memory.search import Search
    search = Search(lambda: {n: t for n, _, t in base._entries(base._memory())}, where / "vectors.jsonl")
    base.narrow = lambda question: search.find(question, limit=12)
    if not args.no_graph:
        from memory.graph import Graph
        # Topics found by meaning, with the encoder the search already holds.
        graph = Graph(where / "graph", lambda: base._entries(base._memory()),
                      embed=lambda texts: search._encoder().embed(texts))
        base.graph_facts = graph.facts_for
        base.graph_recall = graph.recall

    base.confirm_forget = confirm_forget
    from memory.listen import Listener
    from memory import trace
    trace.to(where / "trace.jsonl")
    listener = Listener(base, base._keep, base.context, base.ask, None, _journal_changed,
                        interests_path=where / "interests.jsonl", heard_path=where / "heard.jsonl",
                        embed=lambda texts: search._encoder().embed(texts))
    listener.load_interests()
    if graph is not None and args.engine != "off":
        # Topics kept current from the web (memory/refresh.py): a sweep over the stale ones, offered
        # by the server's timer; what is found is the web's entry in the journal, read into the topic.
        from memory import jobs
        from memory.refresh import Refresher

        def keep_web(text: str, topic: int, when=None) -> int:
            n = base.keep_web(text, topic, when)
            _journal_changed()
            return n

        def topics() -> list[dict]:
            with graph.lock:
                return list(graph.latest.values())
        from memory.graph import USER

        def names() -> set[str]:
            # Every person the graph knows of, by the whole name and by each part of it.
            with graph.lock:
                people = [e for e, kind in graph.kinds.items() if kind == "person" and e != USER]
            return set(people) | {w for e in people for w in e.split() if len(w) > 2}
        refresher = Refresher(keep_web, questions_of=listener.questions_of, extended=listener.extended,
                              last_web=base.last_web, last_said=base.last_said, where=where / "graph", names=names)
        refresher.tell = listener.note
        jobs.add(lambda: refresher.sweep(topics()))
        jobs.start()
    # Two doors (docs/decisions.md, 2026-10-27): the conversation goes in by `say` — from a hook,
    # where the agent has hooks, or from the agent — and the agent asks by `ask`. The journal's own
    # calls stay in it for its tests, not for the agent.
    for tool in [t.name for t in asyncio.run(base.server.list_tools())]:
        base.server.remove_tool(tool)
    base.server._lowlevel_server.instructions = TWO_DOORS
    base.server.add_tool(say, name="say")
    base.server.add_tool(ask, name="ask")
    base.serve(args.port, args.host)


if __name__ == "__main__":
    main()
