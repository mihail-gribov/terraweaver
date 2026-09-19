"""The world served over MCP (streamable HTTP), with debug endpoints on the side.

One long-lived process owns the world: every connected host shares the same store and the
same identity map, so two hosts can't overwrite each other with stale copies.

    python -m terraweaver.server --db worlds/job_search.db --fixture job_search

Then connect a host to http://127.0.0.1:7000/mcp. Debug endpoints:

    GET  /health
    GET  /debug/runs?limit=20&session=...   what hosts ran, saw and changed
    GET  /debug/sessions                    namespaces per session, with their variables
    GET  /debug/export                      the whole world as plain JSON
    POST /debug/reset                       rebuild the world from its fixture

Bound to anything but localhost, every request except /health needs the token:
`Authorization: Bearer <token>` (or `?token=<token>` for a browser). The token comes from
TERRAWEAVER_TOKEN, else from `.terraweaver-token`, generated on first use.

    python -m terraweaver.server --host 0.0.0.0 --allow-origin http://192.168.1.39:7001
"""
import argparse
import hmac
import ipaddress
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

from terraweaver.runtime import HOST_GUIDE, WorldRuntime, format_result

log = logging.getLogger("terraweaver")

server = MCPServer(
    "terraweaver",
    instructions="The user's personal world as a Python object model. Call describe_world first. " + HOST_GUIDE,
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
    the world — e.g. `Person.find(email="ann@x.org").main[0]`, `Vacancy.find(status="applied").main`
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
async def reset_session(ctx: Context) -> str:
    """Start a new task with a clean namespace: drops every variable of this session. Call it
    when the user moves on to something new, so nothing from the earlier task carries over."""
    key = _session_key(ctx)
    runtime.reset_session(key)
    log.info("session %s reset by the host", key)
    return "Session reset: the namespace is clean. The world itself is unchanged."


@server.custom_route("/health", ["GET"])
async def health(request: Request) -> JSONResponse:
    return JSONResponse({"ok": True, "db": runtime.db_path, "fixture": runtime.fixture})


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


@server.custom_route("/debug/reset", ["POST"])
async def debug_reset(request: Request) -> JSONResponse:
    runtime.reset()
    log.info("world reset from fixture %s", runtime.fixture)
    return JSONResponse({"ok": True})


TOKEN_FILE = Path(__file__).resolve().parent.parent / ".terraweaver-token"


def _token() -> str:
    if os.environ.get("TERRAWEAVER_TOKEN"):
        return os.environ["TERRAWEAVER_TOKEN"]
    if not TOKEN_FILE.exists():
        TOKEN_FILE.write_text(secrets.token_hex(24))
        TOKEN_FILE.chmod(0o600)
    return TOKEN_FILE.read_text().strip()


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
    parser.add_argument("--db", default="worlds/job_search.db")
    parser.add_argument("--fixture", default="job_search", help="world to build when the db is empty")
    parser.add_argument("--rebuild", action="store_true", help="rebuild from the fixture on start")
    parser.add_argument("--host", default="127.0.0.1", help="0.0.0.0 to serve the local network (token required)")
    parser.add_argument("--port", type=int, default=7000)
    parser.add_argument("--allow-origin", action="append", default=[],
                        help="browser origin allowed to call the server, e.g. an MCP Inspector UI")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
    runtime = WorldRuntime(args.db, fixture=args.fixture, rebuild=args.rebuild)

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
        log.info("world %s (fixture %s) on http://%s:%d/mcp", args.db, args.fixture, name, args.port)
    if not _is_loopback(args.host):
        log.info("token required (see %s)", TOKEN_FILE.name if not os.environ.get("TERRAWEAVER_TOKEN") else "TERRAWEAVER_TOKEN")
    uvicorn.run(app, host=args.host, port=args.port, log_level="info")


if __name__ == "__main__":
    main()
