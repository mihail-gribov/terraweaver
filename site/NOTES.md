# Site notes

## Purpose

For a judge or a visitor who has two minutes: say what the memory is, show it working, point to the
code. The demo instance must never look like a place to put real data.

## Content (as of 2026-10-30)

| Section | Source |
|---|---|
| Tagline, "active, not a store" | `README.md` |
| What it looks like (concert) | `README.md` |
| Two replays | `scripts/replay.py` over `benchmarks/runs/demo-recall-*-20261030-035627` |
| Question classes | `docs/submission.md` |
| Models | `README.md`, `memory/models.py` |

## Decisions

- One static file, no framework and no build: the page has to survive being copied to a bare machine.
- The replays are iframes of generated pages, so they are the same player as in the video.
- The evaluation-only warning stays above the fold.

## Open

- Numbers from LongMemEval_S once the seed-1 run is final (they are placeholders in `docs/submission.md`).
- A link to the demo video when it is uploaded.
- Whether the live demo should be reachable from the page, once the prefilled world and the daily reset exist (`HOSTING.md`, "Still to do").
- An Open Graph image for link previews.
