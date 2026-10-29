"""Dialogues: a real agent with the memory, a history told over sessions, then a task talked through.

    .venv/bin/python experiments/13_dialogues/run.py colleagues            # one scenario, Haiku as host
    .venv/bin/python experiments/13_dialogues/run.py vacuum --model sonnet
    .venv/bin/python experiments/13_dialogues/run.py all --times 3         # pass^3

A Claude Code host with the personal-world plugin, against a fresh memory behind the two
doors (docs/decisions.md, 2026-10-27): the plugin's hooks pass every message to `say` — the user's
before the host sees it, the host's reply after — and the host has `ask` for what it needs. The
history is told first, session by session, as a user mentions their life in passing; then the
memory is left to read it — the world reads the journal in the quiet, as a mind consolidates — and
only then, in a new session, the task comes, with the user's follow-ups. The host has no search of
its own: what the web holds, the memory finds, through `ask`.

Judged on the answers: each turn of the task names what it must say and what it must not.
Everything is kept per turn (experiments/results/13_dialogues/<scenario>-<stamp>/run.json): the
messages, the host's calls with their inputs and results, what the memory heard and answered
through the hooks (`heard.jsonl`, which the host's own record does not show), the replies — the
record a replay of the dialogue is drawn from. The memory's journal, interests and what it heard
are copied beside it.
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PLUGIN = ROOT / "adapters" / "claude_code" / "plugin"
MEMORY_TOOLS = ["say", "ask"]
TOOLS = [f"mcp__plugin_personal-world_memory__{t}" for t in MEMORY_TOOLS] + ["Skill"]
# The host is a clean one: none of this machine's own user settings (their CLAUDE.md, language,
# name), a working directory outside the repository, and the user it serves named. Measured
# 2026-10-27: a host with the machine's settings answered in Russian and kept "Mike" in the memory.
PERSONA = ("You are the personal assistant of Alex, the user. Reply in English. You have the user's "
           "personal memory and no other source.")

SCENARIOS = {
    "vacuum": {
        "about": "a purchase from the web: hundreds of candidates, limits told in passing a session before",
        "history": [[
            "Ugh, the old Roomba finally died yesterday, after six years. RIP.",
            "Tom works from home three days a week and takes calls all morning, so anything loud in the "
            "flat drives him mad.",
            "We have two cats, Miso and Tofu, and they shed like crazy, especially Tofu.",
            "My dust allergy is acting up again, the doctor said to keep the air and floors as clean as "
            "possible.",
        ], [
            "Our flat in Berlin is about 70 square metres, mostly wooden floor, but the living room has a "
            "thick shaggy rug and the doorways have these 2 cm thresholds the old Roomba always got stuck on.",
            "Money is tight this month: anything for the flat has to stay under 400 euros.",
            "I don't want yet another device that only works through a cloud account and an app.",
        ]],
        "task": [
            {"say": "Can you pick me a robot vacuum to replace the old one? I'd like to order it this week.",
             "must": ["€"], "never": ["my own knowledge", "general knowledge", "couldn't"], "calls": ["ask"],
             "given": ["€", "400", "cloud", "threshold"]},
            {"say": "Why that one? What did you rule out, and why?", "must": [], "never": []},
            {"say": "And if I could stretch to 500 euros, would you pick something else?", "must": [], "never": []},
        ],
    },
    "colleagues": {
        "about": "the people around the user: links that change across sessions",
        "history": [[
            "I started at Brightwork in March 2026 as a data engineer. My manager there is Rachel.",
            "I sit next to Priya, she's on my team. Marco from sales keeps dropping by our desks.",
            "My sister Anna works at Brightwork too, but in the Porto office.",
            "Olga used to be my manager at Lumen, before I moved to Brightwork.",
            "Ben, my neighbour, is a nurse at the city hospital.",
        ], [
            "Big news at work: Rachel left Brightwork last week, so my manager is now Tom.",
        ]],
        "task": [
            {"say": "Who are my colleagues now?", "must": ["Priya", "Tom"], "never": ["Rachel is your manager"]},
            # Forget is left for later (docs/decisions.md, 2026-10-28): no forget step, so Olga, the
            # manager at Lumen, is part of the answer. A new session: what the host heard in this one
            # can't answer it, only the memory can.
            {"say": "Who have I worked with, at any job?", "must": ["Priya", "Olga"], "never": [], "new_session": True},
        ],
    },
    "concert": {
        "about": "a wish said in passing, found on the web: what it is, and when",
        "history": [[
            "My wife Mila and I live in Belgrade.",
            "Mila said she'd love to go to one of those candlelight concerts, where musicians play by "
            "candlelight.",
        ], [
            "I like evenings out on Friday or Saturday; Sunday evenings I prepare for work.",
            "Neither of us likes loud clubs.",
        ]],
        "task": [
            {"say": "My wife mentioned some concert she'd love to go to, and I have no idea what it is. "
                    "Can you find out what it is and when we could go, on a weekend in the next three months?",
             "must": ["Candlelight", "Madlenianum"], "never": [], "calls": ["ask"],
             "given": ["Candlelight", "Mila", "Sunday"]},
            {"say": "Which of those is on a Saturday?", "must": [], "never": []},
        ],
    },
}


def host(message: str, model: str, env: dict, where: Path, session: str | None) -> list[dict]:
    """One user message to Claude Code with the plugin; the stream of what it did."""
    args = ["claude", "-p", "--verbose", "--output-format", "stream-json", "--model", model,
            "--plugin-dir", str(PLUGIN), "--setting-sources", "project", "--append-system-prompt", PERSONA]
    if session:
        args += ["--resume", session]
    # The host's own web tools are off: in `-p` they only end in a permission refusal the host
    # then tells the user about (2026-10-28). Whether a host should search beside the memory is
    # open (docs/TODO.md).
    args += ["--allowedTools", *TOOLS, "--disallowedTools", "WebSearch", "WebFetch"]
    out = subprocess.run(args, input=message, cwd=where, env=env, capture_output=True, text=True,
                         timeout=3600)
    return [json.loads(line) for line in out.stdout.splitlines() if line.startswith("{")]


def turn(message: str, stream: list[dict], began: float) -> dict:
    """What one message came to: the host's calls, each with its result, and its reply."""
    said = [e["message"] for e in stream if isinstance(e.get("message"), dict)]
    parts = [c for m in said for c in m.get("content") or [] if isinstance(c, dict)]
    results = {c.get("tool_use_id"): c.get("content") for c in parts if c.get("type") == "tool_result"}
    calls = [{"tool": c["name"].split("__")[-1], "input": c.get("input"), "result": results.get(c.get("id"))}
             for c in parts if c.get("type") == "tool_use"]
    end = next((e for e in stream if e.get("type") == "result"), {})
    return {"say": message, "calls": calls, "reply": end.get("result", ""), "seconds": round(time.time() - began),
            "cost": end.get("total_cost_usd") or 0}


def heard_since(memory: Path, seen: int, agent_wait: int = 120) -> tuple[list[dict], int]:
    """What the memory heard since line `seen` of heard.jsonl, and the new count. The host's reply
    reaches it from an async Stop hook, after the host has answered: waited for, up to agent_wait
    seconds."""
    path = memory / "heard.jsonl"
    until = time.time() + agent_wait
    while True:
        lines = path.read_text().splitlines() if path.exists() else []
        new = [json.loads(line) for line in lines[seen:] if line.strip()]
        if any(m.get("role") == "agent" for line in new for m in line["heard"]) or time.time() > until:
            return new, len(lines)
        time.sleep(3)


def read_all(memory: Path, wait: int) -> bool:
    """Wait until the world has read every entry of the journal into the image."""
    facts, done = memory / "facts.md", memory / "world" / "read.json"
    until = time.time() + wait
    while time.time() < until:
        told = facts.read_text().count("\n## #") + facts.read_text().startswith("## #") if facts.exists() else 0
        try:
            read = len(json.loads(done.read_text()).get("entries", []))
        except (OSError, ValueError):
            read = 0
        if told and read >= told:
            return True
        time.sleep(15)
    return False


def judge(step: dict, got: dict) -> dict:
    """Two things, apart. What the world gave: the facts the agent needs to decide must be in what
    the memory told it — `ask`'s answers and what `say` put beside the user's message — — the candidates and the user's own limits and wishes (`given`). And what the
    agent made of them: what its reply must say and must not, and the calls it must make and see
    answered — a pick "from my own knowledge" after `task` timed out passed on words alone
    (2026-10-27). The world gives facts and the agent decides: a wrong decision from enough facts
    is the agent's, too few facts is the world's."""
    low = got["reply"].lower()
    missing = [w for w in step["must"] if w.lower() not in low]
    present = [w for w in step["never"] if w.lower() in low]
    answered = {c["tool"] for c in got["calls"] if c.get("result") and "error" not in str(c["result"]).lower()[:200]
                and "aborting" not in str(c["result"]).lower()}
    uncalled = [t for t in step.get("calls", []) if t not in answered]
    gave = " ".join([str(c.get("result")) for c in got["calls"] if c["tool"] == "ask"]
                    + [h["answered"] for h in got.get("heard", [])]).lower()
    not_given = [w for w in step.get("given", []) if w.lower() not in gave]
    return {"passed": not missing and not present and not uncalled and not not_given,
            "world": not not_given and not uncalled, "agent": not missing and not present,
            "missing": missing, "present": present, "uncalled": uncalled, "not_given": not_given}


def scenario(name: str, model: str, port: int, engine: str, wait: int) -> dict:
    plan = SCENARIOS[name]
    out = ROOT / "experiments" / "results" / "13_dialogues" / f"{name}-{datetime.now():%Y%m%d-%H%M%S}"
    out.mkdir(parents=True)
    memory = f"dialogue-{out.name}"
    server = subprocess.Popen([sys.executable, "-m", "memory.server", "--name", memory, "--port", str(port),
                               "--engine", engine], cwd=ROOT, stdout=open(out / "server.log", "w"),
                              stderr=subprocess.STDOUT)
    time.sleep(10)
    env = {**os.environ, "PERSONAL_WORLD": "on", "PERSONAL_MEMORY_URL": f"http://127.0.0.1:{port}",
           "MCP_TOOL_TIMEOUT": "1800000", "CLAUDE_CODE_MCP_TOOL_IDLE_TIMEOUT": "0",
           # Claude Code's own auto-memory kept the user's facts in its files (2026-10-29): off.
           "CLAUDE_CODE_DISABLE_AUTO_MEMORY": "1"}
    where = Path(tempfile.mkdtemp(prefix=f"host-{name}-"))
    record = {"scenario": name, "about": plan["about"], "model": model, "memory": memory, "engine": engine,
              "history": [], "task": []}
    memory_dir, seen = ROOT / "var" / "memory" / memory, 0
    try:
        for told in plan["history"]:
            session, sitting = None, []
            for message in told:
                began = time.time()
                stream = host(message, model, env, where, session)
                session = next((e["session_id"] for e in stream if e.get("session_id")), session)
                sitting.append(turn(message, stream, began))
                sitting[-1]["heard"], seen = heard_since(memory_dir, seen)
                print(f"[history] {message[:70]}  -> {[c['tool'] for c in sitting[-1]['calls']]}, "
                      f"heard: {[m['role'] for h in sitting[-1]['heard'] for m in h['heard']]}", flush=True)
            record["history"].append(sitting)
        began = time.time()
        record["read"] = {"done": read_all(memory_dir, wait), "seconds": round(time.time() - began)}
        print(f"[quiet] the world read the journal: {record['read']}", flush=True)
        session = None
        for step in plan["task"]:
            if step.get("new_session"):
                session = None
            began = time.time()
            stream = host(step["say"], model, env, where, session)
            session = next((e["session_id"] for e in stream if e.get("session_id")), session)
            got = turn(step["say"], stream, began)
            got["heard"], seen = heard_since(memory_dir, seen)
            got["judged"] = judge(step, got)
            record["task"].append(got)
            print(f"[task] {step['say'][:70]}\n  calls: {[c['tool'] for c in got['calls']]}, "
                  f"heard: {[m['role'] for h in got['heard'] for m in h['heard']]}\n  "
                  f"{'PASS' if got['judged']['passed'] else 'FAIL ' + json.dumps(got['judged'])}\n"
                  f"  reply: {got['reply'][:600]}", flush=True)
    finally:
        server.terminate()
        for kept in ("facts.md", "heard.jsonl", "interests.jsonl"):
            if (memory_dir / kept).exists():
                shutil.copy(memory_dir / kept, out / kept)
    record["passed"] = all(t["judged"]["passed"] for t in record["task"])
    record["cost"] = round(sum(t["cost"] for s in record["history"] for t in s) + sum(t["cost"] for t in record["task"]), 3)
    (out / "run.json").write_text(json.dumps(record, indent=1, ensure_ascii=False))
    print(f"{name}: {'PASSED' if record['passed'] else 'FAILED'}  ({out})", flush=True)
    return record


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("scenario", choices=[*SCENARIOS, "all"])
    parser.add_argument("--model", default="haiku", help="the host")
    parser.add_argument("--port", type=int, default=7131)
    parser.add_argument("--engine", default="tavily")
    parser.add_argument("--times", type=int, default=1)
    parser.add_argument("--wait", type=int, default=1200, help="seconds to let the world read the history")
    args = parser.parse_args()
    names = list(SCENARIOS) if args.scenario == "all" else [args.scenario]
    passed = {n: [scenario(n, args.model, args.port, args.engine, args.wait)["passed"] for _ in range(args.times)]
              for n in names}
    for n, runs in passed.items():
        print(f"{n}: {sum(runs)}/{len(runs)}")


if __name__ == "__main__":
    main()
