"""A memory recalled: a talk from a month ago comes back beside today's message, and the agent acts on it.

A month ago the user chose a TV with the agent: the Sony was too dear, the LG would glare in the bright
living room, the Samsung was taken. Two weeks later they went with the LG after all, having put up
blinds. Today, in a new session, they ask Claude Code about a soundbar. Nobody asks the memory
anything: the plugin's hook passes the message to the memory, the memory puts beside it the topic the
message goes on with, and the agent answers knowing which TV is on the wall and why.

The second story, `--story birthday`: a month of an assistant's ordinary use. In passing, inside
talks about a calendar, a weekend, a dinner, a party and a guest, the user lets slip the wife's
birthday, that she loves small jazz gigs and hates crowds, that she is allergic to peanuts (so no
Thai or Indian: "Yes, please"), that she wants a quiet evening for two, that her mother is staying.
Today they ask for help planning the evening, and nothing of it is said again.

Run: set -a; . ./.env; set +a; .venv/bin/python scripts/demo_recall.py [--story tv|birthday] [--model sonnet] [--port 7130]
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import time
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "adapters" / "claude_code" / "plugin"

# The old talks, as the hooks would have passed them: (days ago, who, what was said).
TV = [
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
BIRTHDAY_ON = f"{datetime.now() + timedelta(days=12):%-d %B}"
# Talks about work and the day, between the ones that matter: the most of what an assistant hears,
# and nothing the memory should read. Spread over the free days of a story, the same every run.
FILLER = [
    [("user", "the sprint review went long again, we spent an hour arguing about the API naming"),
     ("agent", "Classic. Did you land on something?"),
     ("user", "kind of. snake_case won, nobody's happy")],
    [("user", "can you look at this stack trace? NullPointerException in the billing job"),
     ("agent", "The invoice date is null for draft orders; guard it before formatting."),
     ("user", "ah right, drafts. thanks")],
    [("user", "our standup is now at 9:15 instead of 9:30, why does that annoy me so much"),
     ("agent", "Fifteen minutes less coffee. Fair enough.")],
    [("user", "rewrite this sentence so it sounds less passive-aggressive: 'as I already said in my last email'"),
     ("agent", "\"Just to build on my earlier note…\""),
     ("user", "perfect")],
    [("user", "the client moved the deadline up by a week. again."),
     ("agent", "Want help cutting the scope down to what fits?"),
     ("user", "maybe tomorrow, I'm done for today")],
    [("user", "what's the difference between a mutex and a semaphore, in one line"),
     ("agent", "A mutex lets one holder in; a semaphore lets N.")],
    [("user", "the new designer's mockups are actually really good"),
     ("agent", "Nice, that makes reviews easier."),
     ("user", "yeah, finally someone who uses the grid")],
    [("user", "summarise this thread for me, it's 80 messages about the logo colour"),
     ("agent", "Blue vs. teal; marketing wants teal; a decision is due Friday."),
     ("user", "80 messages for that lol")],
    [("user", "write a regex that matches an ISO date"),
     ("agent", "^\\d{4}-\\d{2}-\\d{2}$")],
    [("user", "our CI has been red all morning because of a flaky test"),
     ("agent", "Quarantine it and open a ticket, so the rest can merge."),
     ("user", "did that, the team is relieved")],
    [("user", "1:1 with my manager went fine, nothing dramatic"),
     ("agent", "Good to hear.")],
    [("user", "can you draft a short reply to the vendor: we need the invoice in euros"),
     ("agent", "Here's a draft: thank them, ask for the invoice in EUR, same details."),
     ("user", "sent, thanks")],
    [("user", "the office wifi is down so everyone is pretending to work in the kitchen"),
     ("agent", "The most productive meeting of the week.")],
    [("user", "explain eventual consistency to a product manager in two sentences"),
     ("agent", "Every copy of the data catches up, just not instantly. For a moment, two users may see different values."),
     ("user", "nice, stealing that")],
    [("user", "planning poker took 40 minutes for three tickets"),
     ("agent", "Maybe time-box it to two minutes a ticket?")],
    [("user", "how do I squash the last three commits"),
     ("agent", "git rebase -i HEAD~3, then mark two of them as squash.")],
]


def with_filler(story: list, seed: str) -> list:
    """The story with work talk on the days it leaves free, in the order of the days."""
    import random
    pick = random.Random(seed)
    used = {days for days, _, _ in story}
    free = [d for d in range(1, max(used) + 1) if d not in used]
    talks = pick.sample(FILLER, len(FILLER))
    filler = [(day, who, text) for day, talk in zip(sorted(pick.sample(free, min(len(free), len(talks))), reverse=True), talks)
              for who, text in talk]
    return sorted(story + filler, key=lambda t: -t[0])


BIRTHDAY = [
    # Every fact about Mila comes up in passing, while asking about something else — a calendar,
    # a weekend, a dinner, a party, a guest — often as a short answer to the agent ("yes please").
    (34, "user", "ugh, november is filling up already. can you help me block out some evenings?"),
    (34, "agent", "Sure! Anything fixed already that I should keep free?"),
    (34, "user", f"the evening of {BIRTHDAY_ON}, that's my wife Mila's birthday"),
    (34, "agent", "Blocked 🎂 Want a reminder a week before and the day before?"),
    (34, "user", "yes, both"),

    (30, "user", "any ideas for saturday? just the two of us for once"),
    (30, "agent", "There's the big open-air festival in the park, headliners from 6 pm."),
    (30, "user", "nah, Mila hates crowds. she'd much rather a small jazz gig"),
    (30, "agent", "Then there's a jazz trio at Bluebird on Saturday at 9, about 60 seats."),
    (30, "user", "perfect, that's totally her thing"),

    (27, "user", "need a place for dinner on friday"),
    (27, "agent", "How about Bangkok Garden? New Thai place, great reviews."),
    (27, "user", "god no. we tried thai last week and Mila had a reaction, turns out she's seriously allergic to peanuts"),
    (27, "agent", "Oh no, I'm glad she's okay. Should I skip Thai and Indian places from now on?"),
    (27, "user", "yes please"),
    (27, "agent", "Got it. Trattoria Nonna, two streets away: quiet, and nothing with peanuts on the menu."),

    (20, "user", "can you help me write thank-you notes to the parents from Lev's party?"),
    (20, "agent", "Of course! How old is he now?"),
    (20, "user", "seven! twenty kids and a mountain of lego. total chaos"),
    (20, "agent", "Here's a short note you can send to each family. How's Mila holding up?"),
    (20, "user", "exhausted lol. she says for her own birthday she wants something quiet, just the two of us"),

    (9, "user", "can you plan dinners for the next two weeks? we'll be four at the table"),
    (9, "agent", "Sure. Who's joining?"),
    (9, "user", "my mother-in-law Vesna is staying with us for two weeks from monday"),
    (9, "agent", "Lovely. Any dietary needs I should plan around?"),
    (9, "user", "just no peanuts, for Mila"),
    (9, "agent", "Noted: two weeks of dinners, peanut-free throughout."),
]
HOME = [
    # Each sum said in passing while asking about something else; a car service among them that is
    # not the home's. The plumber is "the tap", not "a repair".
    (28, "user", "LG C4 or Samsung S90D for a really bright living room?"),
    (28, "agent", "The Samsung gets brighter; the LG has better processing but can glare without blinds."),
    (28, "user", "went with the LG in the end, 1,290 euros. and we put up blinds"),
    (28, "agent", "Good call with the blinds. Enjoy it!"),

    (15, "user", "what soundbar goes well with the LG?"),
    (15, "agent", "The Sonos Beam is a good match for a 55-inch."),
    (15, "user", "ordered the Beam, 450 euros, arrives friday"),

    (12, "user", "remind me to take the car to the service tomorrow"),
    (12, "agent", "Reminder set for tomorrow morning."),
    (11, "user", "car service done. 300 euros, ouch"),

    (8, "user", "the washing machine shows error E21, what does that mean?"),
    (8, "agent", "Usually a blocked drain pump or filter. Try cleaning the filter first."),
    (8, "user", "didn't help, had to call a repairman. 180 euros, works now"),

    (4, "user", "who do I call about a dripping kitchen tap?"),
    (4, "agent", "A plumber. It's usually a worn washer or cartridge, a quick job."),
    (4, "user", "the plumber came this morning and fixed the tap. 95 euros"),
]
STORIES = {
    "tv": (TV, "I want to get a soundbar for the living room TV. What would you suggest?"),
    "birthday": (with_filler(BIRTHDAY, "birthday"), "Help me plan something nice for my wife's birthday evening."),
    # The answer is 2,015 euros: the TV, the soundbar, the washing machine and the tap; not the car.
    "home": (with_filler(HOME, "home"), "How much have we spent on the home since the start of October?"),
}


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
    parser.add_argument("--story", choices=STORIES, default="tv")
    parser.add_argument("--message", default=None, help="what the user says today")
    args = parser.parse_args()
    before, today = STORIES[args.story]
    args.message = args.message or today
    if not os.environ.get("NEBIUS_API_KEY"):
        raise SystemExit("NEBIUS_API_KEY is not set: set -a; . ./.env; set +a")

    name = f"demo-recall-{args.story}-{datetime.now():%Y%m%d-%H%M%S}"
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

        print("== Before\n")
        for days, who, text in before:
            when = (datetime.now() - timedelta(days=days)).replace(hour=20, minute=0)
            call(args.port, "/say", {"messages": [{"role": who, "text": text}], "now": when.isoformat(timespec="minutes")})
            print(f"  [{when:%Y-%m-%d}] {who}: {text}")
        print("\n(the memory reads what it kept into its graph...)", flush=True)
        call(args.port, "/settle?wait=900", timeout=960)

        print(f"\n== Today, a new session of Claude Code ({args.model}), the plugin on\n\n  user: {args.message}\n", flush=True)
        cwd = where / "cwd"
        cwd.mkdir()
        env = {**os.environ, "PERSONAL_WORLD": "on", "PERSONAL_MEMORY_URL": f"http://127.0.0.1:{args.port}"}
        run = subprocess.run(["claude", "-p", "--model", args.model, "--plugin-dir", str(PLUGIN),
                              "--allowedTools", "mcp__plugin_personal-world_memory__ask",
                              "--output-format", "stream-json", "--verbose"],
                             input=args.message, cwd=cwd, env=env, capture_output=True, text=True, timeout=900)
        # The agent's whole turn, its calls to the memory included: kept beside the memory's trace.
        (where / "agent.jsonl").write_text(run.stdout)
        events = [json.loads(l) for l in run.stdout.splitlines() if l.strip().startswith("{")]
        reply = next((e.get("result", "") for e in reversed(events) if e.get("type") == "result"), "")
        heard = [json.loads(l) for l in (where / "heard.jsonl").read_text().splitlines() if l.strip()]
        beside = next((h["answered"] for h in reversed(heard)
                       if any(args.message in (m.get("text") or "") for m in h["heard"])), "")
        print("  what the memory put beside the message:\n")
        print("\n".join(f"    | {line}" for line in (beside or "(nothing)").splitlines()))
        print("\n  agent:\n\n" + "\n".join(f"    {line}" for line in reply.strip().splitlines()))
        kept = ROOT / "benchmarks" / "runs" / name
        kept.mkdir(parents=True)
        for f in ("facts.md", "heard.jsonl", "trace.jsonl", "agent.jsonl", "graph"):
            if (where / f).is_dir():
                shutil.copytree(where / f, kept / f)
            elif (where / f).exists():
                shutil.copy2(where / f, kept / f)
        (kept / "today.json").write_text(json.dumps({"model": args.model, "message": args.message, "reply": reply}, indent=1))
        print(f"\nThe memory: {where}\nKept: {kept}")
    finally:
        server.terminate()
        server.wait(timeout=30)
    return 0


if __name__ == "__main__":
    sys.exit(main())
