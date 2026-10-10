"""The baseline world: the same four doors as the world, behind the plainest possible memory.

What every agent is told is one contract — `context`, `tell`, `ask`, `questions` — and this is
that contract with nothing behind it but a text file. `tell` appends what was said, dated and
with its source, as it came. `ask` and `context` hand the whole file to Haiku with the question.
`questions` never has any: a text file has no doubts. Whatever the world does better than this
is the world's effect; whatever it does worse, it has to answer for.

    .venv/bin/python -m baseline.server                 # var/baseline/main/facts.md, port 7100
    .venv/bin/python -m baseline.server --name mike --port 7101

Connect an agent to http://127.0.0.1:7100/mcp. Nothing here imports terraweaver.
"""
import argparse
import asyncio
import json
import logging
import tempfile
from datetime import datetime
from pathlib import Path

import uvicorn
from mcp.server.mcpserver import MCPServer
from mcp.server.transport_security import TransportSecuritySettings
from starlette.requests import Request
from starlette.responses import JSONResponse, PlainTextResponse

ROOT = Path(__file__).resolve().parent.parent
log = logging.getLogger("baseline")

server = MCPServer(
    "personal-world",
    instructions=(
        "The user's personal memory. Before answering anything that may touch the user's life — "
        "people, plans, places, preferences, what happened — call `context` with the user's "
        "message. When the user says something about themselves or the people and things in "
        "their life, pass it on with `tell`, in your own words or as said. For a question the "
        "context did not settle, call `ask`. `questions` lists what the memory wants to ask "
        "the user."
    ),
)
facts: Path
model = "haiku"

ASK = """Below is everything the user's assistant has been told about the user, in the order it \
was told, each entry dated. When two entries disagree, the later one holds unless it says \
otherwise.

<memory>
{memory}
</memory>

Question: {question}

Answer from the memory only. If the memory does not say, answer that it does not say."""

CONTEXT = """Below is everything the user's assistant has been told about the user, in the order \
it was told, each entry dated. When two entries disagree, the later one holds unless it says \
otherwise.

<memory>
{memory}
</memory>

The user has just written:

<message>
{message}
</message>

List what the memory holds that bears on this message, as it stands now: one fact per line, \
one sentence each, most relevant first, at most {limit}. If nothing does, answer with the single \
word: nothing."""


def as_list(text: str, limit: int) -> list[str]:
    """The contract's list from whatever the model wrote: `- ` items, one line each, capped.

    The model numbers, stars or indents as it likes; the contract allows one form, which a hook
    can read by code (docs/contract.md, "Lists").
    """
    items = []
    for line in text.splitlines():
        item = line.strip().lstrip("-*•").strip()
        item = item.split(". ", 1)[1] if item[:1].isdigit() and ". " in item[:4] else item
        if item:
            items.append(item if len(item) < 300 else item[:296].rstrip() + "…")
    return [f"- {item}" for item in items[:max(limit, 0)]]


def _memory() -> str:
    return facts.read_text() if facts.exists() else ""


async def _haiku(prompt: str) -> str:
    """One call to the model with no tools, no settings and no memory of its own.

    Through the `claude` CLI, like every other model call in the repository, so it needs no key
    of its own. The prompt goes in on stdin: the whole file is in it, and an argument is capped.
    """
    with tempfile.TemporaryDirectory() as where:
        run = await asyncio.create_subprocess_exec(
            "claude", "-p", "--model", model, "--output-format", "json", "--tools", "",
            "--strict-mcp-config", "--setting-sources", "",
            "--system-prompt", "You answer questions about a person from their assistant's notes.",
            cwd=where, stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE)
        out, err = await asyncio.wait_for(run.communicate(prompt.encode()), timeout=300)
    try:
        result = json.loads(out)
    except json.JSONDecodeError:
        raise RuntimeError((err or out).decode()[:300])
    log.info("haiku %d chars in, $%.4f", len(prompt), result.get("total_cost_usd") or 0.0)
    return (result.get("result") or "").strip()


@server.tool()
async def context(message: str, limit: int = 10) -> str:
    """What the memory holds that bears on the user's message, most relevant first, at most
    `limit` items. Call it before answering."""
    memory = _memory()
    if not memory.strip() or limit < 1:
        return "nothing"
    found = await _haiku(CONTEXT.format(memory=memory, message=message, limit=limit))
    # The contract's "nothing" is exact, so a hook can test for it; the model may dress it up.
    if found.lower().strip(" .") in ("", "nothing"):
        return "nothing"
    return "\n".join(as_list(found, limit)) or "nothing"


@server.tool()
async def tell(text: str, source: str = "conversation") -> str:
    """Keep what was said about the user's life. `text` is the statement, in your words or
    theirs; `source` is where it came from — the conversation, a file, a page."""
    text = text.strip()
    if not text:
        return "Nothing was said, so nothing was kept."
    # One line, never blank (docs/contract.md): it is the entry's heading.
    source = " ".join((source or "").split())[:200] or "conversation"
    facts.parent.mkdir(parents=True, exist_ok=True)
    with facts.open("a") as file:
        file.write(f"## {datetime.now():%Y-%m-%d %H:%M} · {source}\n{text}\n\n")
    return "Kept."


@server.tool()
async def ask(question: str) -> str:
    """Answer a question about the user's life from everything the memory holds."""
    memory = _memory()
    if not memory.strip():
        return "The memory is empty."
    return await _haiku(ASK.format(memory=memory, question=question))


@server.tool()
async def questions(limit: int = 5) -> str:
    """What the memory would like to ask the user, most pressing first, at most `limit`. A text
    file never has anything to ask."""
    return "Nothing to ask."


@server.custom_route("/context", ["POST"])
async def http_context(request: Request) -> PlainTextResponse:
    """The same four calls over plain HTTP, for what can't speak MCP — an agent's hooks."""
    body = await request.json()
    return PlainTextResponse(await context(body.get("message", ""), int(body.get("limit", 10))))


@server.custom_route("/tell", ["POST"])
async def http_tell(request: Request) -> PlainTextResponse:
    body = await request.json()
    return PlainTextResponse(await tell(body.get("text", ""), body.get("source", "conversation")))


@server.custom_route("/ask", ["POST"])
async def http_ask(request: Request) -> PlainTextResponse:
    return PlainTextResponse(await ask((await request.json()).get("question", "")))


@server.custom_route("/questions", ["GET"])
async def http_questions(request: Request) -> PlainTextResponse:
    return PlainTextResponse(await questions(int(request.query_params.get("limit", 5))))


@server.custom_route("/health", ["GET"])
async def health(request: Request) -> JSONResponse:
    return JSONResponse({"ok": True, "facts": str(facts)})


@server.custom_route("/debug/facts", ["GET"])
async def debug_facts(request: Request) -> PlainTextResponse:
    return PlainTextResponse(_memory())


def main() -> None:
    global facts, model
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--name", default="main", help="the memory's name: var/baseline/<name>/facts.md")
    parser.add_argument("--model", default="haiku", help="the model that reads the file")
    parser.add_argument("--port", type=int, default=7100)
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
    facts, model = ROOT / "var" / "baseline" / args.name / "facts.md", args.model
    names = ["127.0.0.1", "localhost"]
    security = TransportSecuritySettings(
        allowed_hosts=[f"{name}:{args.port}" for name in names],
        allowed_origins=[f"http://{name}:{args.port}" for name in names],
    )
    app = server.streamable_http_app(host="127.0.0.1", transport_security=security)
    log.info("baseline memory %s on http://127.0.0.1:%d/mcp", facts, args.port)
    uvicorn.run(app, host="127.0.0.1", port=args.port, log_level="info")


if __name__ == "__main__":
    main()
