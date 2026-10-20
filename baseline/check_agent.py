"""Does an agent use the four calls? Claude Code against the baseline memory, bare or with a skill and hooks.

    .venv/bin/python -m baseline.check_agent                  # 3 runs, host on haiku
    .venv/bin/python -m baseline.check_agent --model sonnet --runs 1
    .venv/bin/python -m baseline.check_agent --plugin            # the personal-world plugin, mode on
    .venv/bin/python -m baseline.check_agent --skill other/SKILL.md --scenario buried

Each run starts an empty memory and two fresh sessions (see SCENARIOS). Judged
on what reached the file and on the second answer, and on which calls the agent made. Bare, the
only thing pushing it to call anything is the server's `instructions`; `--skill` adds the skill
alone, `--plugin` the whole personal-world plugin (skill, hooks) with its mode on from the start.
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Two sessions per scenario. In the first, personal facts come up while the user asks for something
# else; `kept` is what the file must hold after it. In the second an answer depends on them; `said`
# is what that answer must say. `still` asks the memory afterwards, and must still be answered.
SCENARIOS = {
    # The facts are an aside after an everyday request.
    "aside": {
        "first": ("Help me write a two-line message to my landlord asking him to fix the heating this "
                  "week. Keep it polite. By the way, I'm allergic to cats, and my daughter Mia starts "
                  "school on September 1st, so mornings are busy for me."),
        "second": ("A friend invited me to stay at her flat next weekend — she has two cats. Should I "
                   "go? Also, remind me when Mia starts school."),
        "kept": [("cat allergy", ("allerg",)), ("Mia's school", ("mia",))],
        "said": [("allergy brought up", ("allerg",)),
                 ("school date", ("september 1", "1 september", "sept. 1", "sep 1", "-09-01"))],
        "still": ("When does Mia start school?", ("september 1", "1 september", "sept. 1", "sep 1", "-09-01")),
    },
    # The facts are an apology in the middle of a coding task, the kind an agent works past.
    "buried": {
        "first": ("This function is slow on big inputs — can you make it faster and add type hints?\n\n"
                  "```python\ndef dedupe(items):\n    out = []\n    for x in items:\n"
                  "        if x not in out:\n            out.append(x)\n    return out\n```\n\n"
                  "Sorry if I'm slow to reply, I'm at the hospital — my dad Ivan is having knee surgery "
                  "today and I'm in the waiting room. Keep the order of items stable, please."),
        "second": ("I'm visiting my dad tomorrow. What would be a thoughtful thing to bring him, given "
                   "what he's recovering from? Two or three ideas."),
        "kept": [("father Ivan", ("ivan",)), ("knee surgery", ("knee",))],
        "said": [("knee brought up", ("knee",))],
        "still": ("What surgery did the user's father have?", ("knee",)),
    },
}


PLUGIN = ROOT / "adapters" / "claude_code" / "plugin"
SKILL = PLUGIN / "skills" / "personal-memory" / "SKILL.md"


def session(prompt: str, model: str, port: int, where: Path, skill: Path | None, plugin: bool) -> dict:
    config = {"mcpServers": {"memory": {"type": "http", "url": f"http://127.0.0.1:{port}/mcp"}}}
    flags = ["--setting-sources", ""]
    if skill:
        (where / ".claude" / "skills" / "personal-memory").mkdir(parents=True)
        shutil.copy(skill, where / ".claude" / "skills" / "personal-memory" / "SKILL.md")
        flags = ["--setting-sources", "project"]
    if plugin:
        # The plugin's own MCP entry is skipped by --strict-mcp-config; the one above, on this
        # run's port, stands in for it.
        flags += ["--plugin-dir", str(PLUGIN)]
    run = subprocess.run(
        ["claude", "-p", prompt, "--model", model, "--output-format", "stream-json", "--verbose",
         "--strict-mcp-config", "--mcp-config", json.dumps(config), *flags,
         "--allowedTools", "Skill mcp__memory__context mcp__memory__tell mcp__memory__ask mcp__memory__questions mcp__memory__add_memory mcp__memory__search_memory mcp__memory__forget mcp__memory__forgotten"],
        cwd=where, capture_output=True, text=True, stdin=subprocess.DEVNULL, timeout=600,
        env={**os.environ, "PERSONAL_MEMORY_URL": f"http://127.0.0.1:{port}",
             "PERSONAL_WORLD": "on" if plugin else "off"})
    calls, said, cost = [], [], 0.0
    for line in run.stdout.splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if event.get("type") == "assistant":
            for part in event["message"].get("content", []):
                if part.get("type") == "text":
                    said.append(part["text"])
                if part.get("type") == "tool_use":
                    calls.append((part["name"].removeprefix("mcp__memory__"), part.get("input", {})))
        if event.get("type") == "result":
            cost = event.get("total_cost_usd") or 0.0
    # Everything the agent said, not only the last message: the reply the user saw is not always last.
    return {"calls": calls, "text": "\n".join(said), "cost": cost}


def found(text: str, words: tuple) -> bool:
    return any(word in text.lower() for word in words)


def one_run(number: int, model: str, port: int, skill: Path | None, plugin: bool, scenario: dict) -> bool:
    name = f"check-{int(time.time())}-{port}-{number}"
    facts = ROOT / "var" / "baseline" / name / "facts.md"
    server = subprocess.Popen([sys.executable, "-m", "baseline.server", "--name", name, "--port", str(port)],
                              cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        for _ in range(30):
            try:
                urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=1)
                break
            except OSError:
                time.sleep(0.5)
        with tempfile.TemporaryDirectory() as where:
            first = session(scenario["first"], model, port, Path(where), skill, plugin)
        held = facts.read_text() if facts.exists() else ""
        with tempfile.TemporaryDirectory() as where:
            second = session(scenario["second"], model, port, Path(where), skill, plugin)
        # The second session must not have spoilt the first: asking about a fact is not a fact.
        request = urllib.request.Request(f"http://127.0.0.1:{port}/ask", headers={"Content-Type": "application/json"},
                                         data=json.dumps({"question": scenario["still"][0]}).encode())
        still = urllib.request.urlopen(request, timeout=300).read().decode()
    finally:
        server.terminate()
        server.wait()

    print(f"\n=== run {number}  (${first['cost'] + second['cost']:.3f})")
    for label, result in (("first", first), ("second", second)):
        print(f"  {label} calls: " + (", ".join(call for call, _ in result["calls"]) or "none"))
    for call, given in first["calls"]:
        if call == "tell":
            print(f"    tell: {given.get('text', '')[:140]}")
    print("  file: " + held.replace("\n", " | ")[:400])
    checks = [(f"kept: {label}", found(held, words)) for label, words in scenario["kept"]]
    checks += [(f"said: {label}", found(second["text"], words)) for label, words in scenario["said"]]
    checks += [("still knows it afterwards", found(still, scenario["still"][1]))]
    for label, ok in checks:
        print(f"  {'PASS' if ok else 'FAIL'}  {label}")
    if not checks[-1][1]:
        print("  memory now says: " + still.replace("\n", " ")[:300])
        print("  file after: " + (facts.read_text() if facts.exists() else "").replace("\n", " | ")[-500:])
    print("  answer: " + second["text"].replace("\n", " ")[:400])
    return all(ok for _, ok in checks)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--model", default="haiku", help="the host agent's model")
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--port", type=int, default=7150)
    parser.add_argument("--skill", nargs="?", const=str(SKILL), default=None,
                        help="give the agent the personal-memory skill, or another SKILL.md given here")
    parser.add_argument("--scenario", choices=sorted(SCENARIOS), default="aside")
    parser.add_argument("--plugin", action="store_true", help="give the agent the personal-world plugin, mode on")
    args = parser.parse_args()
    skill = Path(args.skill) if args.skill else None
    passed = sum(one_run(n + 1, args.model, args.port, skill, args.plugin, SCENARIOS[args.scenario])
                 for n in range(args.runs))
    print(f"\n{passed}/{args.runs} runs passed (pass^{args.runs}: {'yes' if passed == args.runs else 'no'})")
    return 0 if passed == args.runs else 1


if __name__ == "__main__":
    sys.exit(main())
