"""The user's world filled from conversations: four talks about the family over a month, through the
memory's own door (`say`: the gate, the rewrite, the graph), and the world as it stands after each.

Nobody tells the memory what to keep. "My wife" gives the user a wife whose name is not known yet;
"Mila, my wife" names her; a job changed, a car sold, a sister moved — each part of the world holds
what is said now, and keeps what was.

Run: set -a; . ./.env; set +a; .venv/bin/python scripts/demo_world.py [--port 7140]
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
USER = "the user"

# (days ago, [(who, what was said)]): one talk each.
TALKS = [
    (30, [("user", "I need gift ideas. My wife's birthday is coming up on 3 May."),
          ("agent", "Happy to help. What does she enjoy?"),
          ("user", "She loves jazz and small venues. And she's allergic to nuts, so no chocolates with nuts.")]),
    (21, [("user", "Our son Lev is seven and he's obsessed with Lego and football."),
          ("agent", "Lovely age. Is this for a present too?"),
          ("user", "Not yet. My mother-in-law Vesna is staying with us next week, so the house is busy.")]),
    (14, [("user", "Mila, my wife, wants to repaint the living room before Vesna arrives."),
          ("agent", "Any colours in mind?"),
          ("user", "Something light. We also have a cat, Biscuit, who will hate the smell of paint.")]),
    (1, [("user", "Big news: my sister Ana just moved from Lisbon to Belgrade, she lives ten minutes from us now."),
         ("agent", "That's wonderful!"),
         ("user", "And I started a new job at Globex as a product designer last week. Before that I was at Acme."),
         ("agent", "Congratulations on the new job!"),
         ("user", "We also sold our old VW Golf and bought a Skoda Octavia.")]),
]
# What the world should hold at the end: (whose, part, what holds now, what was — or None).
EXPECTED = [
    (USER, "spouse", "Mila", None), (USER, "child", "Lev", None), (USER, "sibling", "Ana", None),
    (USER, "relative", "Vesna", None), (USER, "pet", "Biscuit", None),
    (USER, "works_at", "Globex", "Acme"), (USER, "job", "designer", None), (USER, "owns", "Octavia", "Golf"),
    ("Mila", "born_on", "3 May", None), ("Mila", "likes", "jazz", None), ("Mila", "health", "nut", None),
    ("Lev", "age", "seven", None), ("Ana", "lives_in", "Belgrade", "Lisbon"),
]


def call(port: int, path: str, body: dict | None = None, timeout: float = 600) -> str:
    request = urllib.request.Request(f"http://127.0.0.1:{port}{path}",
                                     data=json.dumps(body).encode() if body is not None else None,
                                     headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=timeout) as answer:
        return answer.read().decode()


def shown(world: dict) -> str:
    lines = []
    for name, person in world.items():
        filled = {p: v for p, v in person["parts"].items() if v["now"] or v["was"]}
        if not filled:
            continue
        also = f' (said as: {", ".join(person["known_as"])})' if person["known_as"] else ""
        unknown = "" if person["named"] else " — name not known yet"
        lines.append(f"  {name}{also}{unknown}")
        for part, v in filled.items():
            now = "; ".join(x["value"] for x in v["now"]) or "—"
            was = "; ".join(x["value"] + (" (ended)" if x.get("ended") else "") for x in v["was"])
            lines.append(f"      {part:10} {now}" + (f"   was: {was}" if was else ""))
    return "\n".join(lines) or "  (empty)"


def holds(world: dict, whose: str, part: str, now: str, was: str | None) -> bool:
    got = world.get(whose, {}).get("parts", {}).get(part, {"now": [], "was": []})
    ok = any(now.lower() in x["value"].lower() for x in got["now"])
    return ok and (was is None or any(was.lower() in x["value"].lower() for x in got["was"]))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--port", type=int, default=7140)
    args = parser.parse_args()
    if not os.environ.get("NEBIUS_API_KEY"):
        raise SystemExit("NEBIUS_API_KEY is not set: set -a; . ./.env; set +a")
    name = f"demo-world-{datetime.now():%Y%m%d-%H%M%S}-{args.port}"
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
        world = {}
        for days, talk in TALKS:
            when = (datetime.now() - timedelta(days=days)).replace(hour=20, minute=0)
            print(f"\n== {when:%Y-%m-%d}")
            for who, text in talk:
                call(args.port, "/say", {"messages": [{"role": who, "text": text}], "now": when.isoformat(timespec="minutes")})
                print(f"  {who}: {text}")
                when += timedelta(minutes=2)
            call(args.port, "/settle?wait=900", timeout=960)
            world = json.loads(call(args.port, "/world"))
            print("\n  the world now:\n" + shown(world))
        print("\n== What the world should hold")
        passed = 0
        for whose, part, now, was in EXPECTED:
            ok = holds(world, whose, part, now, was)
            passed += ok
            print(f"  {'ok ' if ok else 'MISS'}  {whose} · {part}: {now}" + (f" (was {was})" if was else ""))
        print(f"\n{passed} of {len(EXPECTED)}.  The memory: {where}")
    finally:
        server.terminate()
        server.wait(timeout=30)
    return 0


if __name__ == "__main__":
    sys.exit(main())
