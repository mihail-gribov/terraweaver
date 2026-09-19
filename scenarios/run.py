"""Run host scenarios: a real agent (Claude Code) works on the user's world.

Each scenario is a module in this directory:

    DESCRIPTION  what it tests
    SETUP        code run against the world first, on top of the fixture — the starting state
    TURNS        what the user says: the task, then replies to the questions the host is
                 expected to ask (each sent in the same Claude Code conversation)
    CONVERSATIONS  instead of TURNS: several separate conversations, each a list of turns —
                 for what must carry over between conversations
    EXPECT       code with `assert`s run against the world afterwards (world mode only)
    ANSWER_MUST / ANSWER_MUST_NOT   phrases the last answer must / mustn't contain
    PROBES       questions asked afterwards, each in a fresh conversation, with phrases the answer
                 must / mustn't contain — the same in every mode

Two modes, so the world can be compared with what an agent does without it:

    world     Claude Code reaches the world through the TerraWeaver MCP server only.
    baseline  Claude Code with its ordinary tools (bash, files, python) and a folder holding the
              same starting data as JSON; it keeps and looks things up however it likes.

The runner starts its own world server (port 7010, its own database), so the working world is
never touched.

    .venv/bin/python scenarios/run.py                      # all scenarios, world mode
    .venv/bin/python scenarios/run.py --baseline s06 s08   # chosen scenarios, baseline mode
    .venv/bin/python scenarios/run.py --port 7015 s06      # own server port, to run several at once
    .venv/bin/python scenarios/run.py --model haiku s06    # another model as the host
    .venv/bin/python scenarios/run.py --level hard         # only the scenarios that tell modes apart
"""
import asyncio
import importlib.util
import json
import subprocess
import sys
import tempfile
import time
import urllib.request
from datetime import datetime
from pathlib import Path

from mcp.client.client import Client

ROOT = Path(__file__).resolve().parent.parent
HERE = Path(__file__).resolve().parent
PORT = 7010
URL = f"http://127.0.0.1:{PORT}"
RESULTS = ROOT / "experiments" / "results" / "scenarios"
MODEL: str | None = None  # the host's model; None = Claude Code's default

BASELINE_BRIEF = """\
# Michael's personal data

You are Michael's personal assistant. This folder is where his personal information lives:
`world.json` holds the people he knows, organizations, places, events, vacancies from his job
search, ideas, projects and facts about him, as they stood when this folder was set up.

Keep it up to date as he tells you things, and answer his questions from it. Organize the
folder however you find best — change formats, add files, use any tools you have.
"""


def load_scenarios(filters: list[str]) -> list:
    found = []
    for path in sorted(HERE.glob("s*.py")):
        if filters and not any(f in path.stem for f in filters):
            continue
        spec = importlib.util.spec_from_file_location(path.stem, path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        module.NAME = path.stem
        found.append(module)
    return found


async def world_run(code: str) -> tuple[bool, str]:
    """Run code against the world as a fresh session; (ok, text the host would see)."""
    async with Client(server=f"{URL}/mcp") as client:
        await client.call_tool("reset_session", {})
        result = await client.call_tool("run", {"code": code})
        text = result.content[0].text
    return "[error" not in text, text


class WorldHost:
    """Claude Code with the TerraWeaver MCP server as its only tool."""

    name = "world"

    def __init__(self, work: Path, scenario: str):
        self.work = work
        self.scenario = scenario
        self.count = 0

    def conversation(self) -> list[str]:
        self.count += 1
        config = self.work / f"mcp-{self.scenario}-{self.count}.json"
        config.write_text(json.dumps({"mcpServers": {"terraweaver": {
            "type": "http", "url": f"{URL}/mcp",
            "headers": {"x-terraweaver-session": f"{self.scenario}-{self.count}"}}}}))
        return ["--mcp-config", str(config), "--strict-mcp-config", "--allowedTools", "mcp__terraweaver__*"]

    cwd = property(lambda self: Path(tempfile.gettempdir()))

    @staticmethod
    def phrase(message: str) -> str:
        return message


class BaselineHost:
    """Claude Code with its own tools and a folder holding the same starting data."""

    name = "baseline"

    def __init__(self, work: Path, scenario: str):
        self.folder = work / f"baseline-{scenario}"
        self.folder.mkdir()
        export = json.loads(urllib.request.urlopen(f"{URL}/debug/export").read())
        (self.folder / "world.json").write_text(json.dumps(export, indent=2, ensure_ascii=False))
        (self.folder / "README.md").write_text(BASELINE_BRIEF)

    def conversation(self) -> list[str]:
        return ["--strict-mcp-config", "--allowedTools", "Bash Read Write Edit Glob Grep"]

    cwd = property(lambda self: self.folder)

    @staticmethod
    def phrase(message: str) -> str:
        return message.replace("Using my world (terraweaver):", "Using my personal data in this folder:")


def ask(host, prompt: str, flags: list[str], resume: str | None, log: Path) -> dict:
    """One Claude Code turn; returns its final text, session id, turns and cost."""
    cmd = ["claude", "-p", host.phrase(prompt), *flags, "--output-format", "stream-json", "--verbose"]
    if MODEL:
        cmd += ["--model", MODEL]
    if resume:
        cmd += ["--resume", resume]
    started = time.monotonic()
    run = subprocess.run(cmd, cwd=host.cwd, capture_output=True, text=True, stdin=subprocess.DEVNULL, timeout=1200)
    with open(log, "a") as fh:
        fh.write(run.stdout)
    outcome = {"text": "", "session": resume, "turns": 0, "cost": 0.0, "seconds": time.monotonic() - started}
    for line in run.stdout.splitlines():
        event = json.loads(line)
        if event.get("type") == "result":
            outcome.update(text=event.get("result") or "", session=event.get("session_id"),
                           turns=event.get("num_turns", 0), cost=event.get("total_cost_usd", 0.0))
    return outcome


def check_answer(answer: str, must: list[str], must_not: list[str]) -> str | None:
    lowered = answer.lower()
    for phrase in must:  # "a|b" accepts either spelling ("2,100|2100")
        if not any(option.lower() in lowered for option in phrase.split("|")):
            return f"doesn't mention {phrase!r}"
    for phrase in must_not:
        if phrase.lower() in lowered:
            return f"mentions {phrase!r}"
    return None


def run_scenario(scenario, mode: str, work: Path, out_dir: Path) -> dict:
    urllib.request.urlopen(urllib.request.Request(f"{URL}/debug/reset", method="POST"))
    if getattr(scenario, "SETUP", "").strip():
        ok, text = asyncio.run(world_run(scenario.SETUP))
        if not ok:
            return {"name": scenario.NAME, "mode": mode, "passed": False, "failure": f"setup failed: {text}"}
    host = (WorldHost if mode == "world" else BaselineHost)(work, scenario.NAME)
    log = out_dir / f"{scenario.NAME}.{mode}.jsonl"
    totals = {"turns": 0, "cost": 0.0, "seconds": 0.0}
    failures = []

    def converse(messages: list[str]) -> str:
        flags, session, answer = host.conversation(), None, ""
        for message in messages:
            outcome = ask(host, message, flags, session, log)
            session, answer = outcome["session"], outcome["text"]
            for key in totals:
                totals[key] += outcome[key]
        return answer

    answer = ""
    for conversation in getattr(scenario, "CONVERSATIONS", None) or [scenario.TURNS]:
        answer = converse(conversation)
    problem = check_answer(answer, getattr(scenario, "ANSWER_MUST", []), getattr(scenario, "ANSWER_MUST_NOT", []))
    if problem:
        failures.append(f"answer {problem}")
    for number, (question, must, must_not) in enumerate(getattr(scenario, "PROBES", []), 1):
        reply = converse([question])
        (out_dir / f"{scenario.NAME}.{mode}.probe{number}.txt").write_text(reply)
        problem = check_answer(reply, must, must_not)
        if problem:
            failures.append(f"probe {number} {problem}")
    if mode == "world":
        ok, text = asyncio.run(world_run(scenario.EXPECT))
        if not ok:
            failures.append("expected state not reached: " + text.strip().splitlines()[-1])
    (out_dir / f"{scenario.NAME}.{mode}.answer.txt").write_text(answer)
    return {"name": scenario.NAME, "mode": mode, "passed": not failures, "failure": "; ".join(failures) or None,
            "turns": totals["turns"], "cost": round(totals["cost"], 2), "seconds": round(totals["seconds"])}


def start_server(db: Path) -> subprocess.Popen:
    server = subprocess.Popen(
        [sys.executable, "-m", "terraweaver.server", "--db", str(db), "--port", str(PORT), "--rebuild"],
        cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(40):
        try:
            urllib.request.urlopen(f"{URL}/health", timeout=1)
            return server
        except OSError:
            time.sleep(0.25)
    server.kill()
    raise RuntimeError("the scenario world server didn't start")


def main() -> int:
    global PORT, URL, MODEL
    args = sys.argv[1:]
    if "--model" in args:
        MODEL = args.pop(args.index("--model") + 1)
        args.remove("--model")
    if "--port" in args:
        PORT = int(args.pop(args.index("--port") + 1))
        args.remove("--port")
        URL = f"http://127.0.0.1:{PORT}"
    level = None
    if "--level" in args:
        level = args.pop(args.index("--level") + 1)
        args.remove("--level")
    mode = "baseline" if "--baseline" in args else "world"
    scenarios = [s for s in load_scenarios([a for a in args if not a.startswith("--")])
                 if level is None or getattr(s, "LEVEL", "basic") == level]
    out_dir = RESULTS / f"{datetime.now().strftime('%Y%m%d-%H%M%S')}-{mode}-{MODEL or 'default'}-{PORT}"
    out_dir.mkdir(parents=True, exist_ok=True)
    work = Path(tempfile.mkdtemp(prefix="tw-scenarios-"))
    server = start_server(work / "world.db")
    rows = []
    try:
        for scenario in scenarios:
            row = run_scenario(scenario, mode, work, out_dir)
            rows.append(row)
            print(f"{'PASS' if row['passed'] else 'FAIL'}  {row['name']:28} {mode:8} {MODEL or 'default':7} turns={row.get('turns', 0):<3} "
                  f"${row.get('cost', 0):.2f} {row.get('seconds', 0)}s"
                  + (f"  — {row['failure']}" if row["failure"] else ""), flush=True)
    finally:
        server.kill()
        # Claude Code keeps per-folder memory under ~/.claude/projects; the baseline folders of
        # this run left theirs there. They're throwaway, like the folders.
        import shutil
        for leftover in (Path.home() / ".claude" / "projects").glob(f"-tmp-{work.name}-*"):
            shutil.rmtree(leftover, ignore_errors=True)
    (out_dir / "summary.json").write_text(json.dumps(rows, indent=2, ensure_ascii=False))
    passed = sum(r["passed"] for r in rows)
    print(f"\n{passed}/{len(rows)} passed [{mode}], ${sum(r.get('cost', 0) for r in rows):.2f} "
          f"— {out_dir.relative_to(ROOT)}")
    return 0 if passed == len(rows) else 1


if __name__ == "__main__":
    sys.exit(main())
