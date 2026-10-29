#!/usr/bin/env python3
"""Detect changes in the hackathon rules and overview pages.

The rules may be amended at any time (Official Rules, 11.5), and the judge
panel is still unannounced, so both pages are snapshotted as plain text and
diffed on every run.

    python3 scripts/check-hackathon.py           # diff against the snapshots
    python3 scripts/check-hackathon.py --update  # accept the current pages

Exit code 0 means no change, 1 means the pages moved, 2 means a fetch failed.
"""

import argparse
import difflib
import html
import re
import sys
import urllib.request
from pathlib import Path

PAGES = {
    "rules": "https://nebiusglobalaihackathon.devpost.com/rules",
    "overview": "https://nebiusglobalaihackathon.devpost.com/",
}

SNAPSHOT_DIR = Path(__file__).resolve().parent.parent / "docs" / "hackathon-snapshot"

# The page chrome (nav, footer, "other hackathons" widgets) changes on its own
# schedule and would drown the diff, so only the <section id="main"> body is
# kept — sliced by markers, since its closing tag cannot be matched by regex.
BODY_START = re.compile(r'<section[^>]*id="main"', re.I)
BODY_END = re.compile(r'id="(devpost-footer|register-bar)"', re.I)
DROP = re.compile(r"<(script|style|svg|noscript)\b.*?</\1>", re.S | re.I)
TAG = re.compile(r"<[^>]+>")


def fetch(url: str) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": "terraweaver-rules-watch"})
    with urllib.request.urlopen(request, timeout=30) as response:
        return response.read().decode("utf-8", "replace")


def to_text(page: str) -> str:
    start = BODY_START.search(page)
    body = page[start.start():] if start else page
    end = BODY_END.search(body)
    if end:
        # The marker sits on an attribute, so cut back to that tag's opening "<".
        body = body[:end.start()].rsplit("<", 1)[0]
    body = DROP.sub(" ", body)
    body = re.sub(r"<(p|div|li|tr|h[1-6]|br)\b[^>]*>", "\n", body, flags=re.I)
    body = html.unescape(TAG.sub(" ", body))
    body = body.replace(" ", " ")
    lines = [re.sub(r"[ \t]+", " ", line).strip() for line in body.splitlines()]
    return "\n".join(line for line in lines if line) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--update", action="store_true", help="overwrite the snapshots")
    args = parser.parse_args()

    SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
    changed = False

    for name, url in PAGES.items():
        try:
            current = to_text(fetch(url))
        except Exception as error:  # network, DNS, HTTP — all equally "come back later"
            print(f"{name}: fetch failed: {error}", file=sys.stderr)
            return 2

        snapshot = SNAPSHOT_DIR / f"{name}.txt"
        previous = snapshot.read_text(encoding="utf-8") if snapshot.exists() else ""

        if args.update or not previous:
            snapshot.write_text(current, encoding="utf-8")
            print(f"{name}: snapshot written ({len(current.splitlines())} lines)")
            continue

        if current == previous:
            print(f"{name}: unchanged")
            continue

        changed = True
        print(f"\n=== {name} changed: {url} ===")
        diff = difflib.unified_diff(
            previous.splitlines(), current.splitlines(),
            fromfile=f"{name} (snapshot)", tofile=f"{name} (now)", lineterm="", n=2,
        )
        print("\n".join(diff))

    if changed:
        print("\nReview the diff, then run with --update and log the check in docs/archive/about.md.")
    return 1 if changed else 0


if __name__ == "__main__":
    sys.exit(main())
