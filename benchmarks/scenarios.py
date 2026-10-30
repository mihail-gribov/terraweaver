"""Scenarios: short personal histories, each check one class of task the memory claims, scored by words.

LongMemEval measures the memory against a long history, but a failure there takes an hour to find.
A scenario is a dozen talks over two months among thirty of everyday talk, told through the
memory's own door (`say`), then checked:

  latest     a value that changed: the answer must give what holds now
  count      events spread over talks: the answer must give the number
  time       days, order, how long ago: the answer must get the timing right
  world      who is who in the user's life: the answer must name the right person
  recall     nobody asks: a new message alone must bring the right fact beside it (`/say`)
  unknown    never said: the memory must say it does not know

A check passes when the answer holds every group of words (any one word of a group), so a reader
sees why it passed. Every scenario runs on a fresh memory of its own, all of them at once.

Run: set -a; . ./.env; set +a; .venv/bin/python benchmarks/scenarios.py [--only family,books] [--port 7150]
"""
import argparse
import json
import os
import random
import subprocess
import sys
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from judge import declined  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
NOW = datetime(2026, 10, 30, 19, 0)

# name: {"talks": [(days before NOW, [(who, what was said)])],
#        "checks": [(class, question or message, [[any of these words], ...])]}
# The traps are on purpose: an event told twice, a plan that never happened, a value changed twice,
# someone else's fact beside the user's, a number to add up, a day to count to.
SCENARIOS = {
    "family": {
        "talks": [
            (44, [("user", "I need gift ideas, my wife's birthday is on 11 November."),
                  ("agent", "Happy to help. What does she enjoy?"),
                  ("user", "She loves jazz and small venues. She's allergic to nuts, so no chocolates.")]),
            (40, [("user", "My sister Ana moved from Lisbon to Porto for a new job.")]),
            (37, [("user", "Our son Lev turned seven last weekend, the Lego party was chaos.")]),
            (34, [("user", "My friend Tom's wife Sara is allergic to shellfish, so the barbecue is fish-free.")]),
            (30, [("user", "The interview at Initech went well, they offered me a senior role.")]),
            (26, [("user", "I turned down Initech in the end, the commute would have been awful.")]),
            (20, [("user", "My mother-in-law Vesna is staying with us for two weeks from 2 November.")]),
            (12, [("user", "Ana moved again! Porto didn't work out, she lives in Belgrade now, ten minutes from us.")]),
            (6, [("user", "Started at Globex as a product designer on Monday. Left Acme after five years.")]),
            (4, [("user", "Funny, my new colleague at Globex is also called Ana. She lives in Novi Sad and commutes.")]),
            (2, [("user", "Vesna's visit is postponed to December, her flight got cancelled.")]),
        ],
        "checks": [
            ("world", "Who is Vesna?", [["mother-in-law", "mother in law", "wife's mother", "Mila's mother"]]),
            ("world", "What is my wife allergic to?", [["nut"]]),
            ("latest", "Where does my sister live?", [["Belgrade"]]),
            ("world", "Who is Ana?", [["sister"], ["colleague"]]),
            ("recall", "What should I get my wife for her birthday?", [["jazz"]]),
            ("latest", "Where do I work now?", [["Globex"]]),
            ("latest", "When is Vesna coming to stay with us?", [["December"]]),
            ("count", "How many times has my sister moved since September?", [["two", "2", "twice"]]),
            ("time", "How many days are left until my wife's birthday?", [["12", "twelve"]]),
            ("time", "How old will Lev turn on his next birthday?", [["eight", "8"]]),
            ("recall", "Can you book a table for my wife's birthday dinner? Somewhere with great desserts.",
             [["nut"]]),
            ("recall", "Let's plan a family dinner with my mother-in-law on 5 November.", [["December", "postpone"]]),
            ("unknown", "Which company did Ana move to Porto for?", []),
            ("unknown", "Who is my wife's favourite jazz musician?", []),
        ],
    },
    "books": {
        "talks": [
            (75, [("user", "Finished 'The Martian' on holiday, perfect beach read.")]),
            (50, [("user", "Just finished 'Piranesi' by Susanna Clarke. Strange and beautiful.")]),
            (45, [("user", "Started 'The Overstory' today, it's huge.")]),
            (38, [("user", "I gave up on 'The Overstory', too slow for me.")]),
            (31, [("user", "Started the audiobook of 'Project Hail Mary' for my commute.")]),
            (24, [("user", "Finished 'Project Hail Mary', loved the ending.")]),
            (19, [("user", "Finished 'Klara and the Sun' on the train home.")]),
            (18, [("user", "'Klara and the Sun' stayed with me all day, what a quiet ending.")]),
            (15, [("user", "Polished off 'Station Eleven' over the weekend, couldn't put it down.")]),
            (12, [("user", "Almost done with 'The Remains of the Day', twenty pages left.")]),
            (9, [("user", "The book club picked 'Normal People' for next month.")]),
            (5, [("user", "Finished 'The Remains of the Day' at last.")]),
            (3, [("user", "Started 'Tomorrow, and Tomorrow, and Tomorrow' tonight.")]),
            (1, [("user", "Gave 'Normal People' a go early, not for me, stopped at chapter three.")]),
        ],
        "checks": [
            ("count", "How many books have I finished in the last two months?", [["five", "5"]]),
            ("count", "How many books did I give up on?", [["two", "2"]]),
            ("latest", "What am I reading right now?", [["Tomorrow"]]),
            ("time", "Which did I finish first, 'Klara and the Sun' or 'Project Hail Mary'?", [["Hail Mary"]]),
            ("time", "How long did it take me to get through 'Project Hail Mary'?",
             [["7 days", "seven days", "a week", "one week", "1 week"]]),
            ("recall", "Any idea what I should read next?", [["Normal People"]]),
            ("unknown", "Who recommended 'Piranesi' to me?", []),
            ("unknown", "Which book is the book club reading this month?", []),
        ],
    },
    "running": {
        "talks": [
            (35, [("user", "Ran 5 km along the river this evening.")]),
            (28, [("user", "Ran 5 km this morning. Legs are dead.")]),
            (27, [("user", "Yesterday's run left me sore, I took the stairs very slowly.")]),
            (24, [("user", "Another 5 km run today, 27 minutes.")]),
            (21, [("user", "Wanted to go for a run but it poured all day, so I stayed in.")]),
            (20, [("user", "Gym session today: weights and rowing.")]),
            (17, [("user", "Did my first 10 km run! 58 minutes.")]),
            (13, [("user", "Easy 6 km run with my neighbour Marko.")]),
            (12, [("user", "Correction: yesterday's run with Marko was 7 km, my watch had it wrong.")]),
            (10, [("user", "Skipped running this week, my knee hurts."),
                  ("agent", "Rest it. If it lasts, see a physio.")]),
            (7, [("user", "The physio says it's a mild strain, no running for a week.")]),
            (3, [("user", "Knee is fine again. Ran 8 km today without pain.")]),
        ],
        "checks": [
            ("count", "How many times did I go running in October?", [["five", "5"]]),
            ("count", "How many kilometres did I run in October in total?", [["35"]]),
            ("latest", "How long was my run with Marko?", [["7 km", "7km", "seven"]]),
            ("time", "How many days ago did I run my first 10 km?", [["17", "seventeen"]]),
            ("time", "When was my longest run?", [["13 October", "October 13", "13 Oct", "Oct 13", "2026-10-13", "17 days"]]),
            ("latest", "Is my knee still a problem?", [["fine", "without pain", "recovered", "no longer"]]),
            ("world", "Who do I sometimes run with?", [["Marko"]]),
            ("recall", "Thinking of signing up for a half marathon in four weeks.", [["knee", "strain", "physio"]]),
            ("unknown", "Which running shoes do I use?", []),
        ],
    },
    "home": {
        "talks": [
            (40, [("user", "We need a new TV for the living room, around 55 inches."),
                  ("agent", "Three options: the Sony Bravia 8, the LG C4 OLED and the Samsung S90D."),
                  ("user", "The Sony is too dear. Our living room is very bright, the LG would glare."),
                  ("user", "Ok, let's take the Samsung.")]),
            (33, [("user", "The Samsung is out of stock until December, ugh.")]),
            (28, [("user", "We went with the LG C4 after all and put up blinds. Paid 1,290 euros.")]),
            (25, [("user", "The landlord raised our rent from 1,000 to 1,150 euros.")]),
            (18, [("user", "Talked to the landlord: 1,100 euros if we sign for two years. We signed.")]),
            (15, [("user", "Bought a Sonos Beam soundbar for 450 euros.")]),
            (11, [("user", "Our neighbour's Golf got stolen last night, right in front of the building.")]),
            (8, [("user", "The washing machine broke, the repair was 180 euros.")]),
            (4, [("user", "The plumber finally fixed the leaking tap, 95 euros.")]),
            (2, [("user", "We sold our old VW Golf and bought a Skoda Octavia.")]),
        ],
        "checks": [
            ("latest", "Which TV did we end up buying?", [["LG"]]),
            ("latest", "How much is our rent now?", [["1,100", "1100", "1 100"]]),
            ("latest", "What car do we drive?", [["Octavia", "Skoda"]]),
            ("count", "How much have we spent on the home since October: the TV, the soundbar and repairs?",
             [["2,015", "2015", "2 015"]]),
            ("time", "How many days after picking the Samsung did we buy the LG?", [["12", "twelve"]]),
            ("recall", "I need a new remote for the living room TV, which one should I look for?", [["LG"]]),
            ("recall", "Should I get a car alarm? Cars are getting stolen around here.", [["Octavia", "Skoda"]]),
            ("unknown", "How much did we sell the Golf for?", []),
        ],
    },
    "trips": {
        "talks": [
            (58, [("user", "Back from a long weekend in Vienna, the museums were great.")]),
            (52, [("user", "Booked flights to Lisbon for mid-October.")]),
            (45, [("user", "Dreaming about Japan next spring, nothing booked, just looking.")]),
            (38, [("user", "Work trip to Munich, three days, saw nothing but the office.")]),
            (30, [("user", "The Lisbon trip is cancelled, the airline is on strike.")]),
            (22, [("user", "Weekend in Ljubljana with my wife, lovely little city.")]),
            (14, [("user", "Booked Japan for April: Tokyo and Kyoto, two weeks.")]),
            (10, [("user", "Flew to Athens for a friend's wedding, back on Sunday, exhausted.")]),
            (6, [("user", "My colleague just got back from Iceland, the photos are unreal.")]),
        ],
        "checks": [
            ("count", "How many trips abroad have I actually taken in the last two months?", [["four", "4"]]),
            ("time", "Which trip was more recent, Munich or Vienna?", [["Munich"]]),
            ("latest", "Am I still going to Lisbon?", [["cancel"]]),
            ("latest", "Is the Japan trip booked?", [["April", "booked", "yes"]]),
            ("recall", "Should I start learning some Japanese?", [["April", "Tokyo", "Kyoto"]]),
            ("unknown", "Which hotel did we stay at in Ljubljana?", []),
        ],
    },
}
# Everyday talk with nothing to keep for the checks, spread between the talks that matter.
NOISE = [
    "Ugh, Monday. Too many meetings today.",
    "It's raining again, the whole week looks grey.",
    "Made a big pot of lentil soup, good for three days.",
    "How do I turn a PDF into a Word document?",
    "Can you explain what a Docker volume is?",
    "The coffee machine at the office is broken again.",
    "Watched the new season of that detective show, the ending was silly.",
    "I keep forgetting to water the plants.",
    "Write me a polite email declining a meeting on Thursday.",
    "What's a good substitute for buttermilk in pancakes?",
    "Spent the whole evening fixing a bug in our CI pipeline.",
    "The neighbours are drilling again on a Sunday.",
    "Is it 'affect' or 'effect' in 'the change will ___ everyone'?",
    "Tired today, slept badly.",
    "Quick question: how many grams in a cup of flour?",
    "Our team had a retro today, everyone complained about deadlines.",
    "Translate 'see you tomorrow' into German.",
    "I tried a new pasta place near the office, it was fine, nothing special.",
    "My laptop battery is dying fast, any tips?",
    "Remind me how to undo the last git commit.",
    "Lovely sunny morning for once.",
    "Listened to a podcast about sleep, apparently I need more of it.",
    "Ordered new headphones, they arrive Friday.",
    "What's the difference between a latte and a flat white?",
    "Long day. Pizza and an early night.",
    "Draft a short message to the team about the release slipping a week.",
    "Is there a keyboard shortcut to split the screen on Linux?",
    "The supermarket was out of oat milk again.",
    "Spent an hour on the phone with the bank, finally sorted.",
    "Give me three ideas for a team lunch.",
]
ANSWERS = "Sure, here you go: a short practical answer."
CLASSES = ("latest", "count", "time", "world", "recall", "unknown")


def call(port: int, path: str, body: dict | None = None, timeout: float = 900) -> str:
    request = urllib.request.Request(f"http://127.0.0.1:{port}{path}",
                                     data=json.dumps(body).encode() if body is not None else None,
                                     headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=timeout) as answer:
        return answer.read().decode()


def with_noise(name: str, talks: list) -> list:
    """The scenario's talks with everyday talk spread over the free days, the same for every run."""
    pick = random.Random(name)
    used = {days for days, _ in talks}
    free = [d for d in range(1, max(used) + 3) if d not in used]
    noise = []
    for days, text in zip(sorted(pick.sample(free, min(len(free), len(NOISE))), reverse=True),
                          pick.sample(NOISE, len(NOISE))):
        talk = [("user", text)]
        if text.endswith("?") or text.split()[0] in ("Write", "Translate", "Draft", "Give", "Remind"):
            talk.append(("agent", ANSWERS))
        noise.append((days, talk))
    return sorted(talks + noise, key=lambda t: -t[0])


# The reader writes "mother‑in‑law" and "7 km" with non-breaking hyphens and spaces, and says it does not
# know in more ways than LongMemEval's list holds.
DASHES = str.maketrans({c: "-" for c in "\u2010\u2011\u2012\u2013\u2014\u2212"} | {c: " " for c in "\u00a0\u202f\u2009"})
NOT_KNOWN = ("does not contain", "doesn't contain", "no fact", "not specified", "does not specify")


def passed(kind: str, said: str, words: list[list[str]]) -> bool:
    lowered = said.translate(DASHES).lower()
    if kind == "unknown":
        return declined(lowered) or any(p in lowered for p in NOT_KNOWN)
    return bool(said.strip()) and all(any(w.lower() in lowered for w in group) for group in words)


def run(name: str, port: int, out: Path) -> list[dict]:
    """One scenario on a fresh memory: tell its talks, wait until every entry is read, check."""
    scenario = SCENARIOS[name]
    where = out / name
    where.mkdir(parents=True)
    server = subprocess.Popen([sys.executable, "-m", "memory.server", "--name", f"{out.name}-{name}",
                               "--port", str(port)], cwd=ROOT, stdout=open(where / "server.log", "w"),
                              stderr=subprocess.STDOUT,
                              env={**os.environ, "TERRAWEAVER_USAGE": str(where / "usage.jsonl")})
    results = []
    try:
        for _ in range(60):
            try:
                call(port, "/notes", timeout=2)
                break
            except OSError:
                time.sleep(1)
        for days, talk in with_noise(name, scenario["talks"]):
            when = (NOW - timedelta(days=days)).replace(hour=20, minute=0)
            for who, text in talk:
                call(port, "/say", {"messages": [{"role": who, "text": text}], "now": when.isoformat(timespec="minutes")})
                when += timedelta(minutes=2)
        call(port, "/settle?wait=1800", timeout=1860)
        for kind, text, words in scenario["checks"]:
            now = NOW.isoformat(timespec="minutes")
            if kind == "recall":
                # The hook's door: the message alone, nothing asked; what comes back is put beside it.
                said = call(port, "/say", {"messages": [{"role": "user", "text": text}], "now": now, "wait": True})
            else:
                said = call(port, "/ask", {"question": text, "gather": False, "now": now})
                said = said.split("What it stands on:")[0]
            results.append({"scenario": name, "class": kind, "text": text, "words": words,
                            "said": said.strip(), "passed": passed(kind, said, words)})
    finally:
        server.terminate()
        server.wait(timeout=30)
    (where / "results.json").write_text(json.dumps(results, indent=1, ensure_ascii=False))
    return results


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--only", default="", help="comma-separated scenario names")
    parser.add_argument("--port", type=int, default=7150, help="the first port; one per scenario")
    args = parser.parse_args()
    if not os.environ.get("NEBIUS_API_KEY"):
        raise SystemExit("NEBIUS_API_KEY is not set: set -a; . ./.env; set +a")
    names = [n for n in args.only.split(",") if n] or list(SCENARIOS)
    out = ROOT / "benchmarks" / "results" / f"scenarios-{datetime.now():%Y%m%d-%H%M%S}"
    out.mkdir(parents=True)
    with ThreadPoolExecutor(len(names)) as pool:
        results = [r for rs in pool.map(lambda nk: run(nk[1], args.port + nk[0], out), enumerate(names)) for r in rs]

    for r in results:
        print(f"{'ok  ' if r['passed'] else 'MISS'} {r['scenario']:8} {r['class']:7} {r['text']}")
        if not r["passed"]:
            print("       said: " + " ".join(r["said"].split())[:300])
    print("\nby class:")
    for kind in CLASSES:
        got = [r["passed"] for r in results if r["class"] == kind]
        if got:
            print(f"  {kind:8} {sum(got)} of {len(got)}")
    print(f"\n{sum(r['passed'] for r in results)} of {len(results)}.  Results: {out}")
    (out / "results.json").write_text(json.dumps(results, indent=1, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
