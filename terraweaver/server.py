"""The world served over MCP (streamable HTTP), with debug endpoints on the side.

One long-lived process owns the world: every connected host shares the same store and the
same identity map, so two hosts can't overwrite each other with stale copies.

    python -m terraweaver.server                  # the world kept as var/worlds/main/
    python -m terraweaver.server --db mike        # another one, by name or by path

Then connect a host to http://127.0.0.1:7000/mcp. Debug endpoints:

    GET  /health
    GET  /debug/runs?limit=20&session=...   what hosts ran, saw and changed
    GET  /debug/sessions                    namespaces per session, with their variables
    GET  /debug/export                      the whole world as plain JSON

Bound to anything but localhost, every request except /health needs the token:
`Authorization: Bearer <token>` (or `?token=<token>` for a browser). The token comes from
TERRAWEAVER_TOKEN, else from `.terraweaver-token`, generated on first use.

    python -m terraweaver.server --host 0.0.0.0 --allow-origin http://192.168.1.39:7001
"""
import argparse
import hmac
import ipaddress
import json
import logging
import os
import secrets
import socket
from pathlib import Path

import uvicorn
from mcp.server.mcpserver import Context, MCPServer
from mcp.server.transport_security import TransportSecuritySettings
from starlette.middleware.cors import CORSMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from terraweaver.describe import HOST_GUIDE
from terraweaver.runtime import WorldRuntime, format_result

log = logging.getLogger("terraweaver")

server = MCPServer(
    "terraweaver",
    instructions=(
        "The user's personal world as a Python object model, worked with over several `run` "
        "calls. It is meant for an agent sent here for one task — either to record something "
        "into the world or to answer something from it — and it talks back: it says what it "
        "assumed and asks what it needs, and expects those answered in the next call. Send an "
        "agent that can finish that exchange, not a single call. Call describe_world first. "
    ) + HOST_GUIDE,
)
runtime: WorldRuntime | None = None

# Which namespace a call belongs to. The current MCP protocol is stateless — no session id
# travels with a call — so the host names its namespace with this header (set once in its MCP
# connection config). Without it, calls are grouped by the client's name: every window of the
# same host app then shares one namespace.
SESSION_HEADER = "x-terraweaver-session"


def _session_key(ctx: Context) -> str:
    headers = ctx.headers or {}
    if headers.get(SESSION_HEADER):
        return headers[SESSION_HEADER]
    client = (ctx.request_context.meta or {}).get("io.modelcontextprotocol/clientInfo") or {}
    return client.get("name") or "default"


# Tools are async on purpose: they run on the event loop thread, one at a time. The world
# (its SQLite connection, identity map and access counters) is not thread-safe.

@server.tool()
async def describe_world(ctx: Context) -> str:
    """What exists in the user's world: classes, attributes, methods, and the variables already
    in this session. Call it before writing code."""
    return runtime.describe(_session_key(ctx))


@server.tool()
async def describe_classes(names: list[str] | str | None = None, ctx: Context = None,
                           class_names: list[str] | str | None = None) -> str:
    """What these classes are made of: attributes with their types, methods, and the relations
    they take part in. The world's prompt lists the class names; ask here for the few a task
    needs, e.g. ["Person", "Event"]."""
    return runtime.describe_classes(_names(names, class_names))


@server.tool()
async def classes(like: str | None = None, limit: int = 0, ctx: Context = None) -> str:
    """Every class this world has right now, most used first — including ones defined in this
    session. `like="a sport"` narrows it to what reads like that. The opening description carries
    the ones a task most often needs; this is the whole list."""
    return runtime.classes_here(like, limit)


@server.tool()
async def describe_methods(names: list[str] | str | None = None, ctx: Context = None,
                           method_names: list[str] | str | None = None) -> str:
    """What particular methods do, in full and with examples — for the few a task actually uses,
    e.g. ["tag", "repeat", "Event.reschedule"]. describe_classes lists them in one line each;
    this explains them."""
    return runtime.describe_methods(_names(names, method_names))


def _names(*given) -> list[str]:
    """Take the names however they arrive.

    A host writing `class_names='["Person", "Event"]'` gets a validation error and loses
    a turn to it — seen in a scenario. The tool is called by a language model, so the edge is
    the right place to be forgiving: either keyword, a list or a string, JSON or commas.
    """
    for value in given:
        if not value:
            continue
        if isinstance(value, list):
            return [str(one).strip() for one in value if str(one).strip()]
        text = str(value).strip()
        try:
            loaded = json.loads(text)
            if isinstance(loaded, list):
                return [str(one).strip() for one in loaded if str(one).strip()]
            text = str(loaded)
        except ValueError:
            pass
        return [part.strip(" '\"[]") for part in text.split(",") if part.strip(" '\"[]")]
    return []


@server.tool()
async def run(code: str, ctx: Context) -> str:
    """Execute Python against the user's world and return its stdout. Variables persist between
    calls in this session. A run that raises keeps nothing it wrote."""
    key = _session_key(ctx)
    result = runtime.run(code, key)
    first_line = code.strip().splitlines()[0] if code.strip() else ""
    log.info(
        "run session=%s ok=%s %dms access=%s created=%d updated=%d | %s",
        key, result["ok"], result["duration_ms"], result["access"], len(result["created"]), len(result["updated"]),
        first_line[:80],
    )
    if result["error"]:
        log.info("run error: %s", result["error"].splitlines()[-1])
    return format_result(result)


@server.tool()
async def variables(ctx: Context) -> str:
    """The named values at hand: world variables (shared by every session, each with what it
    means) and this session's own variables (with how long ago they appeared)."""
    return runtime.list_variables(_session_key(ctx))


@server.tool()
async def set_variable(name: str, expression: str, description: str, ctx: Context) -> str:
    """Set a world variable, shared by every session, to the value of a Python expression over
    the world — e.g. `Person.find(full_name="Ann Lee").matches[0]`, `Event.find(title="Dentist").matches`
    or `42`. An entity is kept by id, so it always reads as it is now; other values are snapshots.
    The description must say what it is and why it is kept."""
    key = _session_key(ctx)
    result = runtime.set_variable(key, name, expression, description)
    log.info("set_variable %s ok=%s", name, result["ok"])
    return format_result(result)


@server.tool()
async def unset_variables(names: str, ctx: Context) -> str:
    """Remove world variables. `names` lists them separated by commas or spaces: "anna, stats".
    All or nothing: if one of them doesn't exist, none is removed."""
    result = runtime.unset_variables(_session_key(ctx), names)
    return format_result(result)


@server.tool()
async def start_task(stated: str, mode: str, ctx: Context) -> str:
    """Open a task before working. `stated` says what this piece of work is, in your own words,
    as a sentence. `mode` is "recording" — putting something into the world — or "answering" —
    finding something out of it.

    Call this first, every time the user moves on to something new. The world cannot see a
    conversation start or end, so this is the only boundary it has: what is still yours to use,
    what was left unanswered, and what the next task inherits all hang on it. Finish with
    finish_task."""
    key = _session_key(ctx)
    try:
        opened = runtime.start_task(key, stated, mode)
    except ValueError as wrong:
        return str(wrong)
    except Exception as broke:  # noqa: BLE001 - an opaque tool error tells the agent nothing
        # This exact case cost a whole run: a world built without the Task class answered
        # "Error executing tool start_task" twice, with no reason, and the agent — rightly —
        # carried on without a task. A tool that fails has to say what failed.
        log.exception("start_task failed in session %s", key)
        return (f"The task could not be opened: {type(broke).__name__}: {broke}. Carry on "
                f"without one if you must — what you record is still kept — but say so in what "
                f"you report back, because nothing will check it at the end.")
    log.info("task opened in session %s: %s (%s)", key, stated[:60], mode)
    return opened


@server.tool()
async def finish_task(ctx: Context, abandon: str = "") -> str:
    """Close the task. It will not close while anything it raised is still undecided.

    How it closed is worked out, not taken on your word. Every doubt the world raised about
    what you recorded has to be answered, handed to the user with `q.for_the_user(why)`, or
    dropped with a reason — `world.undecided()` reaches them. `abandon="why"` gives up on the
    task instead; what it did record stays, and the reason is kept with it."""
    key = _session_key(ctx)
    left_open = runtime.finish_task(key, abandon=abandon)
    log.info("task finished in session %s", key)
    if left_open is None:
        return ("There was no task open, so nothing was closed. What you recorded is in the "
                "world; nothing checked it. Open one with start_task before the work, not after.")
    done = "Task closed: the namespace is clean. The world itself keeps everything it was told."
    return f"{done}\n\n{left_open}" if left_open else done


@server.tool()
async def reset_session(ctx: Context) -> str:
    """Older name for finish_task. Prefer finish_task, which also records what the task was."""
    key = _session_key(ctx)
    left_open = runtime.finish_task(key)
    log.info("session %s reset by the host", key)
    done = "Session reset: the namespace is clean. The world itself is unchanged."
    return f"{done}\n\n{left_open}" if left_open else done


@server.custom_route("/health", ["GET"])
async def health(request: Request) -> JSONResponse:
    return JSONResponse({"ok": True, "db": runtime.db_path})


@server.custom_route("/debug/runs", ["GET"])
async def debug_runs(request: Request) -> JSONResponse:
    limit = int(request.query_params.get("limit", 20))
    session = request.query_params.get("session")
    return JSONResponse(runtime.runs(limit=limit, session=session))


@server.custom_route("/debug/sessions", ["GET"])
async def debug_sessions(request: Request) -> JSONResponse:
    return JSONResponse(runtime.sessions_summary())


@server.custom_route("/debug/export", ["GET"])
async def debug_export(request: Request) -> JSONResponse:
    return JSONResponse(runtime.export())


TOKEN_FILE = Path(__file__).resolve().parent.parent / ".terraweaver-token"


def _token() -> str:
    if os.environ.get("TERRAWEAVER_TOKEN"):
        return os.environ["TERRAWEAVER_TOKEN"]
    if not TOKEN_FILE.exists():
        TOKEN_FILE.write_text(secrets.token_hex(24))
        TOKEN_FILE.chmod(0o600)
    return TOKEN_FILE.read_text().strip()


def _give_it_an_engineer(world) -> None:
    """The engineer, if this machine has the key for one. Optional, always.

    Without it `world.say` still works and still joins the two things — the link is made at
    once and stays untyped, which is a poor link and a real one. With it, the untyped links are
    read at the close of each task and become what they are.
    """
    import os

    if not os.environ.get("NEBIUS_API_KEY"):
        return
    try:
        from terraweaver import outside

        world.engineer = outside.Nemotron(ttl=25)
    except Exception:  # noqa: BLE001 - a world with no engineer is a world that does not read
        pass


def _lan_address() -> str | None:
    """The address other machines on the local network reach this one by."""
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
        try:
            probe.connect(("192.0.2.1", 9))  # no packet is sent; this only picks a route
            return probe.getsockname()[0]
        except OSError:
            return None


def _is_loopback(host: str) -> bool:
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return host == "localhost"


class TokenAuth:
    """Every request but /health and CORS preflights must carry the token."""

    def __init__(self, app, token: str):
        self.app = app
        self.token = token

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope["method"] == "OPTIONS" or scope["path"] == "/health":
            return await self.app(scope, receive, send)
        request = Request(scope)
        given = request.headers.get("authorization", "").removeprefix("Bearer ").strip()
        given = given or request.query_params.get("token", "")
        if not hmac.compare_digest(given, self.token):
            response = JSONResponse({"error": "missing or wrong token"}, status_code=401)
            return await response(scope, receive, send)
        return await self.app(scope, receive, send)


def main() -> None:
    global runtime
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--db", default="main",
                        help="a world by name (var/worlds/<name>/) or a path to its database")
    parser.add_argument("--one-door", action="store_true",
                        help="hide define_relation: the host says facts in words and the world "
                             "works out the types (an experiment; see authoring.install)")
    parser.add_argument("--blank", action="store_true",
                        help="no classes at all: the host defines the ontology (docs/open-ontology.md)")
    parser.add_argument("--specs", default=None,
                        help="a directory of class specs to open a host-built world with")
    parser.add_argument("--reading-at-close", type=float, default=None,
                        help="seconds the close may spend reading what was said in words "
                             "(0 to leave it all for experiments/catch_up.py). A reading is a "
                             "handful of calls to an engineer and a batch of them is minutes, "
                             "while the close happens inside the host's own finish_task.")
    parser.add_argument("--host", default="127.0.0.1", help="0.0.0.0 to serve the local network (token required)")
    parser.add_argument("--port", type=int, default=7000)
    parser.add_argument("--allow-origin", action="append", default=[],
                        help="browser origin allowed to call the server, e.g. an MCP Inspector UI")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
    if args.reading_at_close is not None:
        import terraweaver.runtime as runtime_module

        runtime_module.READING_AT_THE_CLOSE = args.reading_at_close
    if args.specs:
        # A world somebody already built: its classes come from the files it wrote them into.
        from terraweaver import authoring

        specs = {json.loads(path.read_text())["name"]: json.loads(path.read_text())
                 for path in sorted(Path(args.specs).glob("*.json"))}
        runtime = WorldRuntime(args.db, specs=specs, selves=False)
        authoring.install(runtime.world, Path(args.specs))
    elif args.blank:
        # A world with the mechanism and no vocabulary. The host defines the classes; the world
        # keeps them uniform and answers "is there already something for this?".
        from terraweaver import authoring

        runtime = WorldRuntime(args.db, specs={}, selves=False)
        authoring.install(runtime.world, Path(args.db).with_suffix("").parent / "grown")
    else:
        # The world as every world opens: the base, what it has grown, the calls that define more
        # — one recipe, `open_world` — and the engineer, if this machine has a key for one.
        from terraweaver import open_world

        runtime = open_world(args.db, one_door=args.one_door)
        _give_it_an_engineer(runtime.world)

    names = ["127.0.0.1", "localhost"]
    lan = _lan_address()
    if not _is_loopback(args.host):
        names += [n for n in (lan, args.host) if n and n != "0.0.0.0"]
    security = TransportSecuritySettings(
        allowed_hosts=[f"{name}:{args.port}" for name in names],
        allowed_origins=[f"http://{name}:{args.port}" for name in names] + args.allow_origin,
    )
    app = server.streamable_http_app(host=args.host, transport_security=security)
    if not _is_loopback(args.host):
        app = TokenAuth(app, _token())
    app = CORSMiddleware(
        app,
        allow_origins=args.allow_origin,
        allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
        allow_headers=["*"],
        expose_headers=["mcp-session-id", "mcp-protocol-version"],
    )

    for name in names:
        log.info("world %s on http://%s:%d/mcp", runtime.db_path, name, args.port)
    if not _is_loopback(args.host):
        log.info("token required (see %s)", TOKEN_FILE.name if not os.environ.get("TERRAWEAVER_TOKEN") else "TERRAWEAVER_TOKEN")
    uvicorn.run(app, host=args.host, port=args.port, log_level="info")


if __name__ == "__main__":
    main()
