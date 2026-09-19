"""Run host scenarios: a real agent (Claude Code) works on the world through MCP.

Each scenario is a module in this directory:

    DESCRIPTION  what it tests
    SETUP        code run against the world first, on top of the fixture — the starting state
    TURNS        what the user says: the task, then replies to the questions the host is
                 expected to ask (each sent in the same Claude Code conversation)
    CONVERSATIONS  instead of TURNS: several separate conversations, each a list of turns —
                 for what must carry over between conversations through the world alone
    EXPECT       code with `assert`s run against the world afterwards — the expected state
    ANSWER_MUST / ANSWER_MUST_NOT   optional phrases the host's last answer must / mustn't contain

The runner starts its own world server (port 7010, its own database), so the working world
is never touched. SETUP and EXPECT go through the same `run` tool the host uses.

    .venv/bin/python scenarios/run.py                # all scenarios
    .venv/bin/python scenarios/run.py reschedule     # names containing a substring
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


def host_config(work: Path, session: str) -> Path:
    """MCP config for one conversation. Each conversation gets its own namespace, so anything
    that carries over between conversations has to come from the world itself."""
    config = work / f"mcp-{session}.json"
    config.write_text(json.dumps({"mcpServers": {"terraweaver": {
        "type": "http", "url": f"{URL}/mcp", "headers": {"x-terraweaver-session": session}}}}))
    return config


def ask_host(prompt: str, config: Path, resume: str | None, log: Path) -> dict:
    """One Claude Code turn; returns its final text, session id, turns and cost."""
    cmd = ["claude", "-p", prompt, "--mcp-config", str(config), "--strict-mcp-config",
           "--allowedTools", "mcp__terraweaver__*", "--output-format", "stream-json", "--verbose"]
    if resume:
        cmd += ["--resume", resume]
    run = subprocess.run(cmd, cwd=tempfile.gettempdir(), capture_output=True, text=True,
                         stdin=subprocess.DEVNULL, timeout=900)
    with open(log, "a") as fh:
        fh.write(run.stdout)
    outcome = {"text": "", "session": resume, "turns": 0, "cost": 0.0}
    for line in run.stdout.splitlines():
        event = json.loads(line)
        if event.get("type") == "result":
            outcome.update(text=event.get("result") or "", session=event.get("session_id"),
                           turns=event.get("num_turns", 0), cost=event.get("total_cost_usd", 0.0))
    return outcome


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
    scenarios = load_scenarios(sys.argv[1:])
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    out_dir = RESULTS / stamp
    out_dir.mkdir(parents=True, exist_ok=True)
    work = Path(tempfile.mkdtemp(prefix="tw-scenarios-"))
    server = start_server(work / "world.db")
    rows = []
    try:
        for scenario in scenarios:
            urllib.request.urlopen(urllib.request.Request(f"{URL}/debug/reset", method="POST"))
            failure = None
            ok, text = asyncio.run(world_run(scenario.SETUP)) if getattr(scenario, "SETUP", "").strip() else (True, "")
            if not ok:
                failure = f"setup failed: {text}"
            turns, cost, answer = 0, 0.0, ""
            if failure is None:
                for number, conversation in enumerate(getattr(scenario, "CONVERSATIONS", None) or [scenario.TURNS]):
                    config = host_config(work, f"{scenario.NAME}-{number}")
                    session = None
                    for message in conversation:
                        outcome = ask_host(message, config, session, out_dir / f"{scenario.NAME}.jsonl")
                        session, answer = outcome["session"], outcome["text"]
                        turns += outcome["turns"]
                        cost += outcome["cost"]
                ok, text = asyncio.run(world_run(scenario.EXPECT))
                if not ok:
                    failure = "expected state not reached: " + text.strip().splitlines()[-1]
                lowered = answer.lower()
                for phrase in getattr(scenario, "ANSWER_MUST", []):
                    if phrase.lower() not in lowered and failure is None:
                        failure = f"answer doesn't mention {phrase!r}"
                for phrase in getattr(scenario, "ANSWER_MUST_NOT", []):
                    if phrase.lower() in lowered and failure is None:
                        failure = f"answer mentions {phrase!r}"
            (out_dir / f"{scenario.NAME}.answer.txt").write_text(answer)
            rows.append({"name": scenario.NAME, "passed": failure is None, "failure": failure,
                         "turns": turns, "cost": round(cost, 2)})
            print(f"{'PASS' if failure is None else 'FAIL'}  {scenario.NAME:32} turns={turns:<3} "
                  f"${cost:.2f}" + (f"  — {failure}" if failure else ""), flush=True)
    finally:
        server.kill()
    (out_dir / "summary.json").write_text(json.dumps(rows, indent=2, ensure_ascii=False))
    passed = sum(r["passed"] for r in rows)
    print(f"\n{passed}/{len(rows)} passed, ${sum(r['cost'] for r in rows):.2f}  — {out_dir.relative_to(ROOT)}")
    return 0 if passed == len(rows) else 1


if __name__ == "__main__":
    sys.exit(main())
