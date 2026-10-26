"""The baseline world: the same four doors as the world, behind the plainest possible memory.

What every agent is told is one contract — `context`, `tell`, `ask`, `questions`, and the calls
every other memory has, `add_memory`, `search_memory`, `forget` — and this is that contract with
nothing behind it but a text file. `tell` (and `add_memory`, the same call) appends what was said,
numbered, dated and with its source, as it came. `ask`, `context` and `search_memory` hand the
whole file to the reading model with the question; `search_memory` gives back the entries themselves, not an
answer. `forget` moves entries to a bin, `forgotten.jsonl` beside the file, where no reader looks
and `forgotten` lists them; they are deleted for good a set time later. `questions` never has any: a text file has no
doubts. Whatever the world does better than this
is the world's effect; whatever it does worse, it has to answer for.

    .venv/bin/python -m baseline.server                 # var/baseline/main/facts.md, port 7100
    .venv/bin/python -m baseline.server --name mike --port 7101

Connect an agent to http://127.0.0.1:7100/mcp. Nothing here imports terraweaver.
"""
import argparse
import asyncio
import hmac
import json
import logging
import os
import re
import secrets
import tempfile
from datetime import datetime, timedelta
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
# Held by every call that writes. `forget` reads the file, asks the model, and writes it back
# without the forgotten entries; a `tell` landing in between would be written over.
writing = asyncio.Lock()

# The words of run_context.py's prompt, which scored 100 on FactConsolidation with every fact in it;
# each way this prompt departed from them cost about four of the 33 hardest questions (the entry's
# time and source on its line, a preamble about "the user", a rule to list every entry), so it
# departs only where the contract makes it: an ask says when the memory does not say.
ASK = """Below is a list of facts, numbered in the order they were stated. Some facts were later \
updated: when two facts conflict, the one with the larger number is newer and is the one that holds.

{memory}

Question: {question}

Answer with the value that holds now and nothing else. If no fact answers it, say that the \
memory does not say."""

CONTEXT = """Below is a list of facts, numbered in the order they were stated. Some facts were \
later updated: when two facts conflict, the one with the larger number is newer and is the one \
that holds.

{memory}

The user has just written:

<message>
{message}
</message>

List what the memory holds that bears on this message, as it stands now: one fact per line, \
one sentence each, most relevant first, at most {limit}. If nothing does, answer with the single \
word: nothing."""

SEARCH = """Below is a list of facts, numbered in the order they were stated.

{memory}

Find the facts that bear on this: {query}

Answer with the numbers of those facts only, most relevant first, at most {limit}, separated by \
commas — or with the single word: none."""

FORGET = """Below is a list of facts, numbered in the order they were stated.

{memory}

The user wants this forgotten: {what}

Answer with the numbers of the facts that say it, and only those, separated by commas — or with \
the single word: none."""


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


# How long a forgotten entry stays in the bin before it is deleted for good.
keep_forgotten = timedelta(days=30)


def _memory() -> str:
    _purge()
    return facts.read_text() if facts.exists() else ""


# What a reader is shown, if not the whole journal: question -> the entry numbers to show. None
# here, so the baseline reads everything; the proto sets its search (proto/search.py).
narrow = None


def _for(question: str) -> str:
    """The journal as a reader of this question gets it: all of it, or what `narrow` picks."""
    memory = _memory()
    if narrow is None or not memory.strip():
        return memory
    picked = set(narrow(question))
    return "".join(f"## #{heading}\n{text}\n\n" for n, heading, text in _entries(memory) if n in picked)


def _bin() -> Path:
    return facts.with_name("forgotten.jsonl")


def _binned() -> list[dict]:
    path = _bin()
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()] if path.exists() else []


def _purge() -> None:
    """Delete for good what has been in the bin longer than `keep_forgotten`. By this clock, not
    the agent's: how long the words stay on disk is the world's to keep, whatever date was told."""
    binned = _binned()
    due = datetime.now() - keep_forgotten
    left = [b for b in binned if datetime.fromisoformat(b["binned"]) > due]
    if len(left) < len(binned):
        _bin().write_text("".join(json.dumps(b, ensure_ascii=False) + "\n" for b in left))


def _entries(memory: str) -> list[tuple[int, str, str]]:
    """The file's entries: their number, their heading line, and what was said."""
    out = []
    for entry in memory.split("## #")[1:]:
        heading, _, text = entry.partition("\n")
        number = heading.partition(" · ")[0]
        if number.isdigit():
            out.append((int(number), heading, text.strip()))
    return out


def _as_entry(heading: str, text: str) -> str:
    """One entry as a list item: number, time, source and the words, on one line."""
    number, _, rest = heading.partition(" · ")
    return f"- #{number} · {rest}: {' '.join(text.split())}"


def _numbers(said: str, held: set[int], limit: int) -> list[int]:
    """The entry numbers the model named, in its order, only those the file holds."""
    out = []
    for n in map(int, re.findall(r"\d+", said)):
        if n in held and n not in out:
            out.append(n)
    return out[:max(limit, 0)]


def _for_the_model(memory: str) -> str:
    """The file as the model reads it: one line an entry, its number first, then what was said.

    The file keeps each entry under a heading of its own, with its time and source; handed over
    like that, the model took the first of two entries that disagree far more often. On the 33
    hardest FactConsolidation questions: 30 right as `n. fact` lines, 26 with the time and source
    on each line, fewer still under the headings (docs/decisions.md). Time and source stay in the
    file; giving them back to the model is a step of its own, measured.
    """
    return "\n".join(f"{n}. {' '.join(text.split())}" for n, _, text in _entries(memory))


async def _read(prompt: str) -> str:
    """One call to the model that reads the memory, with no tools and no memory of its own.

    A model with a slash in its name is served by Nebius Token Factory (NEBIUS_API_KEY): Nemotron
    by default in the product, so the memory runs on nothing but its own server and one key. A
    bare name (`haiku`) goes through the `claude` CLI, as every measured run before 2026-10-26 did.
    """
    return await (_token_factory(prompt) if "/" in model else _claude(prompt))


async def _token_factory(prompt: str) -> str:
    """The prompt as one user turn, thinking off: the reader picks entries, it doesn't plan."""
    global _nebius
    if _nebius is None:
        from openai import AsyncOpenAI
        _nebius = AsyncOpenAI(base_url="https://api.tokenfactory.nebius.com/v1/",
                              api_key=os.environ["NEBIUS_API_KEY"], timeout=300)
    answer = await _nebius.chat.completions.create(
        model=model, temperature=0, max_tokens=4000,
        messages=[{"role": "user", "content": prompt}],
        extra_body={"chat_template_kwargs": {"enable_thinking": False}})
    usage = answer.usage
    log.info("%s %d chars in, %d tokens in, %d out", model, len(prompt),
             usage.prompt_tokens if usage else 0, usage.completion_tokens if usage else 0)
    return (answer.choices[0].message.content or "").strip()


_nebius = None


async def _claude(prompt: str) -> str:
    """One call to the model with no tools, no settings and no memory of its own.

    Through the `claude` CLI, like every other model call in the repository, so it needs no key
    of its own. The prompt goes in on stdin: the whole file is in it, and an argument is capped.
    """
    with tempfile.TemporaryDirectory() as where:
        run = await asyncio.create_subprocess_exec(
            "claude", "-p", "--model", model, "--output-format", "json", "--tools", "",
            # No system prompt of our own. Measured on the 33 questions the first run lost, with
            # run_context's prompt word for word: 19 right under a one-line system prompt, 30
            # under Claude Code's own — the model holds to the entries over what it knows far
            # better with it (docs/decisions.md).
            "--strict-mcp-config", "--setting-sources", "",
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
    memory = _for(message)
    if not memory.strip() or limit < 1:
        return "nothing"
    found = await _read(CONTEXT.format(memory=_for_the_model(memory), message=message, limit=limit))
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
    # Numbered, because order is what decides between two entries that disagree, and a time does
    # not carry it: a batch told in one minute had one time on every entry, and the model, left
    # to find the later one by position in a long file, took the one it already believed — 67 of
    # 100 on FactConsolidation, against 100 for the same facts numbered (docs/decisions.md).
    # One more than the largest, not than how many: a forgotten entry leaves a gap, and its number
    # is never given to another.
    async with writing:
        _keep(text, source)
    return "Kept."


def _told(now: str | None) -> datetime | None:
    """The agent's now, if it gave one that reads; otherwise None, and `_keep` takes this clock."""
    try:
        return datetime.fromisoformat((now or "").strip())
    except ValueError:
        return None


def _keep(text: str, source: str, told: datetime | None = None) -> int:
    """Append one entry and return its number. Nothing in it awaits, so on the event loop no other
    call can land between the read and the write; `forget` holds `writing` across its await.

    `told` is when it was said, as the teller knows it; without it, this clock's now."""
    facts.parent.mkdir(parents=True, exist_ok=True)
    number = max((n for n, _, _ in _entries(_memory())), default=0) + 1
    with facts.open("a") as file:
        file.write(f"## #{number} · {told or datetime.now():%Y-%m-%d %H:%M:%S} · {source}\n{text}\n\n")
    return number


server.add_tool(tell, name="add_memory", description=(
    "Keep what was said about the user's life — the same call as `tell`, under the name other "
    "memories use. `text` is the statement, in your words or theirs; `source` is where it came "
    "from — the conversation, a file, a page."))


@server.tool()
async def ask(question: str) -> str:
    """Answer a question about the user's life from everything the memory holds."""
    if not _memory().strip():
        return "The memory is empty."
    memory = _for(question)
    return await _read(ASK.format(memory=_for_the_model(memory), question=question))


@server.tool()
async def search_memory(query: str, limit: int = 10) -> str:
    """The entries the memory holds that bear on `query`, as they were told — number, time,
    source and the words — most relevant first, at most `limit`. Not an answer: where two
    entries disagree, both come back, and the larger number is the later one."""
    memory = _for(query)
    entries = {n: (heading, text) for n, heading, text in _entries(memory)}
    if not entries or limit < 1:
        return "nothing"
    said = await _read(SEARCH.format(memory=_for_the_model(memory), query=query, limit=limit))
    found = _numbers(said, set(entries), limit)
    return "\n".join(_as_entry(*entries[n]) for n in found) or "nothing"


# What else holds the entries' words is told what was taken and where the request went:
# hook([(number, text) taken out], request's number, to_bin). A hook may be async; what more it
# takes out it puts in the bin first, with `to_bin([{...}])`, beside the entries, and returns
# the lines to add to the answer. The journal knows nothing of what holds them.
on_forget: list = []


@server.tool()
async def forget(what: str, now: str | None = None) -> str:
    """Take out of the memory what the user wants forgotten: `what` in words ("Anna's old phone
    number"), or entry numbers from `search_memory` ("#12, #14"). Returns the entries taken out,
    so a wrong one can be told again. They wait in a bin, seen only by `forgotten`, and are
    deleted for good after a set time (30 days by default). The request itself is kept, dated, in `what`'s words — so
    name what to forget by what it is, not by the detail to be dropped. `now` is the current date
    and time as you know them (2026-10-15T14:30): when the user asked."""
    what = what.strip()
    held = {n for n, _, _ in _entries(_memory())}
    if not what or not held:
        return "Nothing was forgotten."
    # Numbers are taken as numbers, by code: the agent that read them from `search_memory`
    # knows exactly which entries it means, and a model has nothing to add to that.
    if re.fullmatch(r"(#\d+[\s,;]*(and\s+)?)+", what):
        gone = _numbers(what, held, len(held))
    else:
        # Not the requests to forget: asked twice about the storage move, the second `forget` in
        # words took the first one's request with it, and what the user had asked was lost. A
        # request goes only when named by its number.
        requests = {n for n, heading, _ in _entries(_memory()) if heading.endswith(" · forget")}
        memory = "".join(f"## #{heading}\n{text}\n\n" for n, heading, text in _entries(_memory())
                         if n not in requests)
        said = await _read(FORGET.format(memory=_for_the_model(memory), what=what))
        gone = _numbers(said, held - requests, len(held))
    if not gone:
        return "Nothing was forgotten."
    async with writing:
        # Read again under the lock: a `tell` may have landed while the model was reading.
        kept, taken = [], []
        for n, heading, text in _entries(_memory()):
            (taken if n in gone else kept).append((n, heading, text))
        if not taken:
            return "Nothing was forgotten."
        # Into the bin first, then out of the file: a crash between leaves an entry twice, never
        # nowhere. In the bin no reader sees it, and `forgotten` lists it until it is purged.
        request_said = (f"The user asked for this to be forgotten, and {len(taken)} "
                        f"{'entry was' if len(taken) == 1 else 'entries were'} taken out: {what}")
        binned, asked = datetime.now(), _told(now)
        _to_bin([{"entry": n, "heading": heading, "text": text} for n, heading, text in taken], what, asked, binned)
        facts.write_text("".join(f"## #{heading}\n{text}\n\n" for _, heading, text in kept))
        # That the user asked is a fact of its own, and once the bin is purged the only one left
        # of what was dropped: "which detail did I ask you to drop?" had nothing to answer from
        # (MemOps, forget).
        request = _keep(request_said, "forget", asked)
        said = [_as_entry(heading, text) for _, heading, text in taken]
        for hook in on_forget:
            got = hook([(n, text) for n, _, text in taken], request,
                       lambda items: _to_bin(items, what, asked, binned))
            said += (await got if asyncio.iscoroutine(got) else got) or []
    return "\n".join(said)


def _to_bin(items: list[dict], what: str, asked: datetime | None, binned: datetime) -> None:
    """Into the bin, each with the request's words, when it was asked and when it was binned."""
    if not items:
        return
    with _bin().open("a") as file:
        for item in items:
            file.write(json.dumps({**item, "what": what, "asked": f"{asked or binned:%Y-%m-%d %H:%M:%S}",
                                   "binned": binned.isoformat(timespec="seconds")}, ensure_ascii=False) + "\n")


@server.tool()
async def forgotten() -> str:
    """What the user asked to be forgotten and is still in the bin: each entry as it was, when it
    was forgotten, and when it will be deleted for good. Nothing a reader of the memory sees."""
    _purge()
    items = []
    for b in _binned():
        where = (f"#{b['entry']} · {b['heading'].partition(' · ')[2]}" if "entry" in b
                 else f"heard #{b['heard']}")
        items.append(f"- {where}: {' '.join(b['text'].split())} (forgotten {b['asked']}, at "
                     f"\"{b['what']}\"; deleted for good after "
                     f"{datetime.fromisoformat(b['binned']) + keep_forgotten:%Y-%m-%d})")
    return "\n".join(items) or f"Nothing was forgotten in the last {keep_forgotten.days} days."


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


@server.custom_route("/add_memory", ["POST"])
async def http_add_memory(request: Request) -> PlainTextResponse:
    body = await request.json()
    return PlainTextResponse(await tell(body.get("text", ""), body.get("source", "conversation")))


@server.custom_route("/search_memory", ["POST"])
async def http_search_memory(request: Request) -> PlainTextResponse:
    body = await request.json()
    return PlainTextResponse(await search_memory(body.get("query", ""), int(body.get("limit", 10))))


@server.custom_route("/forget", ["POST"])
async def http_forget(request: Request) -> PlainTextResponse:
    body = await request.json()
    return PlainTextResponse(await forget(body.get("what", ""), body.get("now")))


@server.custom_route("/forgotten", ["GET"])
async def http_forgotten(request: Request) -> PlainTextResponse:
    return PlainTextResponse(await forgotten())


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
    global facts, model, keep_forgotten
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--name", default="main", help="the memory's name: var/baseline/<name>/facts.md")
    parser.add_argument("--model", default="haiku", help="the model that reads the file")
    parser.add_argument("--port", type=int, default=7100)
    parser.add_argument("--host", default="127.0.0.1",
                        help="0.0.0.0 to serve the local network, behind a bearer token")
    parser.add_argument("--keep-forgotten", type=int, default=30, metavar="DAYS",
                        help="days a forgotten entry stays in the bin before it is deleted")
    args = parser.parse_args()
    keep_forgotten = timedelta(days=args.keep_forgotten)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
    facts, model = ROOT / "var" / "baseline" / args.name / "facts.md", args.model
    serve(args.port, args.host)


def serve(port: int, host: str = "127.0.0.1") -> None:
    """Serve MCP on /mcp and the plain HTTP routes: on localhost, or on the network with a token.

    On localhost the host and origin checks keep a web page from reaching the memory. Off it they
    can't, since the names a LAN client uses aren't known here, so every request must carry
    `Authorization: Bearer <token>` instead: TERRAWEAVER_TOKEN, or one made once and kept beside
    the journal (`token`, readable by its owner only). The token itself is never logged.
    """
    if host in ("127.0.0.1", "localhost"):
        names = ["127.0.0.1", "localhost"]
        security = TransportSecuritySettings(
            allowed_hosts=[f"{name}:{port}" for name in names],
            allowed_origins=[f"http://{name}:{port}" for name in names],
        )
        app = server.streamable_http_app(host="127.0.0.1", transport_security=security)
        log.info("memory %s on http://127.0.0.1:%d/mcp", facts, port)
    else:
        token, kept = _token(facts.parent / "token")
        app = _guarded(server.streamable_http_app(
            host=host, transport_security=TransportSecuritySettings(enable_dns_rebinding_protection=False)),
            token)
        log.info("memory %s on http://%s:%d/mcp, bearer token %s", facts, host, port, kept)
    uvicorn.run(app, host=host, port=port, log_level="info")


def _token(path: Path) -> tuple[str, str]:
    """The network token, and where it comes from (for the log, without the token)."""
    if token := os.environ.get("TERRAWEAVER_TOKEN", "").strip():
        return token, "from TERRAWEAVER_TOKEN"
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.touch(mode=0o600)
        path.write_text(secrets.token_urlsafe(32) + "\n")
    return path.read_text().strip(), f"in {path}"


def _guarded(app, token: str):
    """Pass on only the requests that carry the token; answer 401 to the rest."""
    expected = f"Bearer {token}".encode()

    async def guarded(scope, receive, send):
        if scope["type"] == "http":
            given = dict(scope["headers"]).get(b"authorization", b"")
            if not hmac.compare_digest(given, expected):
                await PlainTextResponse("unauthorized", status_code=401)(scope, receive, send)
                return
        await app(scope, receive, send)
    return guarded

if __name__ == "__main__":
    main()
