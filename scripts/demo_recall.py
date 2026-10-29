"""A memory recalled: a talk from a month ago comes back beside today's message, and the agent acts on it.

A month ago the user chose a TV with the agent: the Sony was too dear, the LG would glare in the bright
living room, the Samsung was taken. Two weeks later they went with the LG after all, having put up
blinds. Today, in a new session, they ask Claude Code about a soundbar. Nobody asks the memory
anything: the plugin's hook passes the message to the memory, the memory puts beside it the topic the
message goes on with, and the agent answers knowing which TV is on the wall and why.

Run: set -a; . ./.env; set +a; .venv/bin/python scripts/demo_recall.py [--model sonnet] [--port 7130]
"""
import argparse
import json
import os
import subprocess
import sys
import time
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "adapters" / "claude_code" / "plugin"

# The old talks, as the hooks would have passed them: (days ago, who, what was said).
BEFORE = [
    (30, "user", "We need a new TV for the living room, around 55 inches. My wife Mila wants something good for films."),
    (30, "agent", "Three strong 55-inch options: the Sony Bravia 8 (about 1,600 €), the LG C4 OLED (about "
                  "1,300 €) and the Samsung S90D (about 1,200 €)."),
    (30, "user", "The Sony is too dear for us."),
    (30, "agent", "Understood. Between the LG C4 and the Samsung S90D: both are OLED; the LG has the better "
                  "processing, the Samsung gets a little brighter."),
    (30, "user", "Our living room is very bright, big windows facing south. The LG would glare."),
    (30, "user", "Ok, let's take the Samsung."),
    (16, "user", "Update on the TV: we went with the LG C4 after all. We put up blinds, so the glare is gone."),
]
TODAY = "I want to get a soundbar for the living room TV. What would you suggest?"


def call(port: int, path: str, body: dict | None = None, timeout: float = 600) -> str:
    request = urllib.request.Request(f"http://127.0.0.1:{port}{path}",
                                     data=json.dumps(body).encode() if body is not None else None,
                                     headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=timeout) as answer:
        return answer.read().decode()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--model", default="sonnet", help="the agent: Claude Code's model")
    parser.add_argument("--port", type=int, default=7130)
    args = parser.parse_args()
    if not os.environ.get("NEBIUS_API_KEY"):
        raise SystemExit("NEBIUS_API_KEY is not set: set -a; . ./.env; set +a")

    name = f"demo-recall-{datetime.now():%Y%m%d-%H%M%S}"
    where = ROOT / "var" / "memory" / name
    where.mkdir(parents=True)
    server = subprocess.Popen([sys.executable, "-m", "memory.server", "--name", name, "--port", str(args.port)],
                              cwd=ROOT, stdout=open(where / "server.log", "w"), stderr=subprocess.STDOUT)
    try:
        for _ in range(60):
            try:
                call(args.port, "/notes", timeout=2)
                break
            except OSError:
                time.sleep(1)

        print("== A month ago\n")
        for days, who, text in BEFORE:
            when = (datetime.now() - timedelta(days=days)).replace(hour=20, minute=0)
            call(args.port, "/say", {"messages": [{"role": who, "text": text}], "now": when.isoformat(timespec="minutes")})
            print(f"  [{when:%Y-%m-%d}] {who}: {text}")
        print("\n(the memory reads what it kept into its graph...)", flush=True)
        call(args.port, "/settle?wait=900", timeout=960)

        print(f"\n== Today, a new session of Claude Code ({args.model}), the plugin on\n\n  user: {TODAY}\n", flush=True)
        cwd = where / "cwd"
        cwd.mkdir()
        env = {**os.environ, "PERSONAL_WORLD": "on", "PERSONAL_MEMORY_URL": f"http://127.0.0.1:{args.port}"}
        run = subprocess.run(["claude", "-p", "--model", args.model, "--plugin-dir", str(PLUGIN),
                              "--allowedTools", "mcp__plugin_personal-world_memory__ask"],
                             input=TODAY, cwd=cwd, env=env, capture_output=True, text=True, timeout=900)
        heard = [json.loads(l) for l in (where / "heard.jsonl").read_text().splitlines() if l.strip()]
        beside = next((h["answered"] for h in reversed(heard)
                       if any(TODAY in (m.get("text") or "") for m in h["heard"])), "")
        print("  what the memory put beside the message:\n")
        print("\n".join(f"    | {line}" for line in (beside or "(nothing)").splitlines()))
        print(f"\n  agent:\n\n" + "\n".join(f"    {line}" for line in run.stdout.strip().splitlines()))
        print(f"\nThe memory: {where}")
    finally:
        server.terminate()
        server.wait(timeout=30)
    return 0


if __name__ == "__main__":
    sys.exit(main())
