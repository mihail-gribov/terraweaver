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
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

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
    outcome = {"text": "", "session": resume, "turns": 0, "cost": 0.0,
               "seconds": time.monotonic() - started}
    for line in run.stdout.splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if event.get("type") == "result":
            outcome.update(text=event.get("result") or "", session=event.get("session_id"),
                           turns=event.get("num_turns", 0), cost=event.get("total_cost_usd", 0.0))
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


def start_server(db: Path, port: int) -> subprocess.Popen:
    """An empty world of its own: no fixture, so nothing is in it but `user` and `agent`."""
    server = subprocess.Popen(
        [sys.executable, "-m", "terraweaver.server", "--db", str(db), "--port", str(port),
         "--fixture", ""],
        cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
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
