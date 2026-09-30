"""Driving a host agent against one world, one instance at a time.

`scenarios/run.py` does something close to this and deliberately isn't shared: a scenario suite
keeps one world and resets it between scenarios, while a benchmark needs a world per question —
the history of instance 12 must not be visible when instance 13 is asked. So the lifecycle is
different, and what is common here is only the three small things every run needs: start a
server on its own port, spend one Claude Code turn, and tear the world down afterwards.

The host is Claude Code either way. In `world` mode its only tools are the world's; in
`baseline` mode it has its own — files, grep, bash — and an empty folder to organise as it
likes. Same model, same prompts, same questions: the comparison is the point.
"""
import json
import os
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from terraweaver import outside  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent

BASELINE_BRIEF = """\
# My personal data

You are my personal assistant. This folder is where everything you learn about me lives; it
starts empty. As I tell you things, keep them here, organised however you find best, so that
you can answer questions about my life later. Use any tools you have.
"""


class World:
    """Claude Code with the TerraWeaver MCP server as its only tool."""

    name = "world"

    def __init__(self, work: Path, tag: str, port: int):
        self.work, self.tag, self.port, self.count = work, tag, port, 0
        # A folder of its own, never the shared temp dir: Claude Code keeps per-folder memory
        # under ~/.claude/projects, and a run in /tmp inherits whatever earlier runs left there.
        # The first smoke run answered out of a scenario's leftovers, which is not a benchmark.
        self.here = work / f"host-{tag}"
        self.here.mkdir(parents=True, exist_ok=True)

    def conversation(self) -> list[str]:
        self.count += 1
        config = self.work / f"mcp-{self.tag}-{self.count}.json"
        config.write_text(json.dumps({"mcpServers": {"terraweaver": {
            "type": "http", "url": f"http://127.0.0.1:{self.port}/mcp",
            "headers": {"x-terraweaver-session": f"{self.tag}-{self.count}"}}}}))
        return ["--mcp-config", str(config), "--strict-mcp-config",
                "--allowedTools", "mcp__terraweaver__*",
                # Without this the host reads and writes files, and in the first smoke run it
                # answered out of Claude Code's own per-folder memory instead of the world.
                "--disallowedTools", "Read Write Edit Bash Glob Grep WebFetch WebSearch NotebookEdit"]

    cwd = property(lambda self: self.here)

    @staticmethod
    def phrase(message: str) -> str:
        return "Using my world (the terraweaver tools): " + message


class Baseline:
    """Claude Code with its own tools and an empty folder to keep the same material in."""

    name = "baseline"

    def __init__(self, work: Path, tag: str, port: int):
        self.folder = work / f"baseline-{tag}"
        self.folder.mkdir(parents=True, exist_ok=True)
        (self.folder / "README.md").write_text(BASELINE_BRIEF)

    def conversation(self) -> list[str]:
        return ["--strict-mcp-config", "--allowedTools", "Bash Read Write Edit Glob Grep"]

    cwd = property(lambda self: self.folder)

    @staticmethod
    def phrase(message: str) -> str:
        return "Using my personal data in this folder: " + message


def ask(host, prompt: str, flags: list[str], resume: str | None, log: Path,
        model: str | None, timeout: int = 1200) -> dict:
    """One Claude Code turn. Returns its final text, session id, turns and cost."""
    cmd = ["claude", "-p", host.phrase(prompt), *flags, "--output-format", "stream-json", "--verbose"]
    if model:
        cmd += ["--model", model]
    if resume:
        cmd += ["--resume", resume]
    started = time.monotonic()
    run = subprocess.run(cmd, cwd=host.cwd, capture_output=True, text=True,
                         stdin=subprocess.DEVNULL, timeout=timeout)
    with open(log, "a") as fh:
        fh.write(run.stdout)
    if not run.stdout.strip():
        # A host that produced nothing is not a host that answered nothing: the process failed,
        # and until now the only sign of it was a run costing $0.00 with an empty transcript.
        raise RuntimeError(
            f"the host produced nothing (exit {run.returncode}). stderr: "
            f"{(run.stderr or '').strip()[:800] or '(empty)'}")
    outcome = {"text": "", "session": resume, "turns": 0, "cost": 0.0,
               "seconds": time.monotonic() - started, "unreachable": [], "limited": None,
               "tool_errors": []}
    for line in run.stdout.splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if event.get("subtype") == "init":
            # The one failure that used to pass for a result. A session whose world server did not
            # answer has no tools at all: it says so in words, the batch is reported "recorded",
            # and the number is of a run that never reached the world. Measured 2026-09-27 — five
            # facts of six lost this way, because the session before had just closed a task and the
            # reading it ran at the close held the server past the 30-second handshake.
            outcome["unreachable"] = [one.get("name") for one in event.get("mcp_servers") or []
                                      if one.get("status") not in ("connected", "ok", None)]
        for block in (event.get("message") or event).get("content") or []:
            # A tool the world could not complete — a timeout, a raise inside the server. Not the
            # same thing as the world refusing something, which comes back as an ordinary result
            # and is the world working. Measured 2026-09-28: a `json.dumps` on a method poisoned
            # every write in one world, and from there the host got "The operation timed out." for
            # the rest of the batch while the run recorded the batch as done.
            if isinstance(block, dict) and block.get("type") == "tool_result" and block.get("is_error"):
                outcome["tool_errors"].append(str(block.get("content"))[:200])
        if event.get("type") == "rate_limit_event":
            about = (event.get("rate_limit_info") or {})
            outcome["limited"] = {k: about.get(k) for k in ("status", "rateLimitType",
                                                            "utilization", "isUsingOverage")}
        if event.get("type") == "result":
            outcome.update(text=event.get("result") or "", session=event.get("session_id"),
                           turns=event.get("num_turns", 0), cost=event.get("total_cost_usd", 0.0))
            if event.get("is_error") or event.get("subtype") not in (None, "success"):
                outcome["trouble"] = f"{event.get('subtype')}: {str(event.get('result'))[:300]}"
    return outcome


def plain(prompt: str, model: str = "haiku", timeout: int = 300) -> str:
    """One model call with no tools and no world — for extracting and for judging.

    Goes through the same `claude` CLI as everything else, so a benchmark run needs no API key
    of its own and is billed the way scenario runs already are.
    """
    run = subprocess.run(["claude", "-p", prompt, "--model", model, "--strict-mcp-config",
                          "--allowedTools", ""], capture_output=True, text=True,
                         stdin=subprocess.DEVNULL, timeout=timeout)
    return (run.stdout or "").strip()


def keys() -> dict:
    """The repository's own `.env`, for the world server this starts.

    Nothing in `terraweaver` reads `.env` — a key reaches it from the shell that started it. Run
    from a shell that never exported one, the server finds no `NEBIUS_API_KEY`, gets no engineer,
    and `_read_what_was_said` returns at once: every link the host said in words stays untyped
    for good. That run still finishes and still prints a number, and the number is of a world
    that cannot type — which is why it is read here and reported by `engineer()` rather than
    left to whoever remembered to export it.
    """
    found = dict(os.environ)
    env = ROOT / ".env"
    if env.exists():
        for line in env.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            name, value = line.split("=", 1)
            if value.strip() and not found.get(name.strip()):
                found[name.strip()] = value.strip()
    return found


def engineer() -> str | None:
    """Which engineer a world started here will have, or None — for a run to record."""
    return outside.NEMOTRON if keys().get("NEBIUS_API_KEY") else None


def start_server(db: Path, port: int, blank: bool = False, reading: float = 0,
                 specs: Path | None = None) -> subprocess.Popen:
    """An empty world of its own: the base, so nothing is in it but `user` and `agent`.

    `blank=True` goes further and takes the classes away too — the host defines the ontology
    (`docs/open-ontology.md`). `specs` opens a world whose classes are all grown, from the files it
    wrote them into: without it the server has no class for anything the world holds, so nothing
    in it can be loaded — `--specs` was accepted by `reask.py` and never reached the server
    (docs/code-review-2026-09-30.md 3.4.9).

    `reading=0` by default: during a measured ingestion the world does not read at the close, and
    the reading is a phase of its own afterwards. The budget bounds when a reading may *start*, so
    one slow reading still overruns the host's tool timeout — measured 2026-09-28, twice, a batch
    lost to `finish_task` timing out. A run that types nothing during the write phase and everything
    in one pass after it has neither problem, and says so in its own log."""
    server = subprocess.Popen(
        [sys.executable, "-m", "terraweaver.server", "--db", str(db), "--port", str(port),
         "--reading-at-close", str(reading),
         *(["--specs", str(specs)] if specs else []),
         *(["--blank"] if blank and not specs else [])],
        cwd=ROOT, env=keys(), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(120):
        if server.poll() is not None:
            raise RuntimeError(f"world server on {port} died on startup (exit {server.returncode})")
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=1)
            return server
        except OSError:
            time.sleep(0.5)
    server.kill()
    raise RuntimeError(f"world server on {port} didn't answer in a minute")


def answering(port: int, seconds: float = 60) -> bool:
    """Whether the world server answers now — asked before a turn, not after it went wrong.

    The close of a task runs the reading, which takes tens of seconds per link, and the server is
    busy for all of it. The next batch is a new session with a 30-second handshake, so it can arrive
    while the world is still reading and get no tools at all. Waiting here costs nothing when the
    world is free and saves the batch when it is not.
    """
    for _ in range(int(seconds * 2)):
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=1)
            return True
        except OSError:
            time.sleep(0.5)
    return False


def went_wrong(got: dict) -> dict | None:
    """The technical failures of one turn, told apart from anything the host decided.

    A host that could not reach the world, or a turn the CLI itself ended with an error, is not the
    host answering badly — it is our side failing, and the two were indistinguishable in the numbers.
    A call that failed because the host asked for a tool that is not there is the host's own doing
    (`mcp__tensorweaver__run`, the world's name misspelt) and is left to it. Shared by every runner
    here, because the one that lacked it recorded a world nobody could reach as 1% accuracy.
    """
    if got.get("unreachable"):
        return {"what": f"the world was unreachable: {', '.join(got['unreachable'])}",
                "kind": "technical", "turns": got.get("turns"), "said": got.get("text", "")[:300]}
    if got.get("trouble"):
        said = str(got["trouble"])
        if any(one in said for one in NO_USAGE_LEFT):
            return {"what": said[:200], "kind": "no usage left", "turns": got.get("turns")}
        return {"what": said, "kind": "technical", "turns": got.get("turns")}
    ours = [one for one in got.get("tool_errors") or [] if not _the_hosts_own(one)]
    if ours:
        return {"what": f"the world failed {len(ours)} call(s): {ours[0]}", "kind": "technical",
                "turns": got.get("turns"), "all": ours[:5]}
    return None


# A failed call the host brought on itself. Measured over one hundred questions: eighteen
# `validation error for start_task` (it wrote `task=` for `stated=`, or called it with nothing),
# four `Cannot create agent worktree` from a tool that has no business here, two `Unknown skill`
# for a tool of ours called as one, one misspelling of the world's own name. None of it is our
# plumbing failing, so none of it is kept out of the number — a host that cannot work the world's
# door is answering badly, and that is the thing being measured. It is counted and reported.
HOSTS_OWN = ("No such tool available", "Invalid tool name", "validation error",
             "Unknown skill", "Cannot create agent worktree")

# Not a failure of the world and not of the host either: the account simply has no usage left.
# Measured 2026-09-30, it took 95 of 100 questions in one run — "You're out of extra usage · resets
# 4:10am" — and was reported as "the world was unreachable", which sent me looking at the server.
# A run that hits this has not measured anything and should say so in those words.
NO_USAGE_LEFT = ("out of extra usage", "usage limit reached", "rate limit exceeded")


def _the_hosts_own(said: str) -> bool:
    return any(one in said for one in HOSTS_OWN)


def hosts_own(got: dict) -> list[str]:
    """The calls this turn failed on its own account, for a run to report beside its number."""
    return [one for one in got.get("tool_errors") or [] if _the_hosts_own(one)]


def forget_folder_memory(folder: Path) -> None:
    """Drop the per-folder memory Claude Code kept for a run's working directory.

    Without this the next run starts with the last one's notes about somebody else's life, and
    the benchmark measures contamination.
    """
    import shutil

    slug = "-" + str(folder).strip("/").replace("/", "-")
    for leftover in (Path.home() / ".claude" / "projects").glob(f"{slug}*"):
        shutil.rmtree(leftover, ignore_errors=True)


def stop(server: subprocess.Popen) -> None:
    server.terminate()
    try:
        server.wait(timeout=10)
    except subprocess.TimeoutExpired:
        server.kill()
