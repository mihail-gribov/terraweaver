# Now: the plan being walked, what is ruled out, and what flickers

`docs/decisions.md` records why a change went in, after the fact. This file is the opposite: it is
the working note kept *while* the work is going on, so the same ground is not covered twice. It is
short on purpose and it is edited, not appended.

**Rules for this file.** One line per hypothesis, and when it is ruled out it stays here marked
ruled out — a dead hypothesis is worth more than an empty line, because it is the thing somebody
will think of again tomorrow. A problem that appears and disappears goes under "flickers" the first
time it appears, with what it was, or it will be diagnosed from scratch again.

---

## Why we circled (2026-09-30, written after a day of it)

1. **Fixed what a reader found, not what the data said.** Thirty-odd defects out of
   `docs/code-review-2026-09-30.md`, every one real and every one tested — and not one of them
   was known to cost a fact. The measurement of *why facts are missing*
   (`experiments/why_it_failed.py`) was written at the end of the day. It should have been first:
   it takes minutes, costs nothing, and it names the causes in order of size.
2. **Measured with an instrument that cannot resolve the effect.** Two gates of 25 facts gave 84%
   and 68%. The difference was the *host* writing differently, not the code. A 25-fact gate
   answers "does the chain run" and nothing else. Anything about the number needs the 455.
3. **Re-derived the same diagnosis three times** because nothing was written down: the lost name
   was blamed on `find()` (my own test called it wrong), then on `retype` (clean in isolation),
   then on a rename (0 of them in run8). Hence this file.

---

## The number, and what it is made of

`var/run8/world` — 455 facts, written and read on 2026-09-30 with the code of that morning.
`check_expected` says 210 of 316 standing expectations as owed (**66%**), 1 backwards.
`why_it_failed.py` on the same world says what the other 105 are:

| count | shape | whose |
|---|---|---|
| 33 | both ends are in the world and no link joins them | to diagnose |
| 29 | the name is in the record and **not in the image** (21 entities) | **the world's** |
| 12 | both ends there, the fact is in prose instead of a link | the host's |
| 10 | an end was never put in the world (the object) | the host's |
| 10 | both ends are there twice over — the link is on a duplicate | the world's |
| 6 | an end was never put in the world (the subject) | the host's |
| 5 | said in prose about the other end, never made a thing | the host's |

Reproduce, free, no models:

    .venv/bin/python experiments/check_expected.py var/run8/world --upto 455
    .venv/bin/python experiments/why_it_failed.py  var/run8/world --upto 455

---

## The plan, in order

1. **The 21 entities whose name the image lost** — 29 facts, the largest single defect that is the
   world's own. In progress; hypotheses below.
2. **The 33 "no link"** — diagnose before fixing. First thing to check: how many of them are facts
   that contradict common knowledge (the slice has them on purpose — "Israel is located in the
   continent of North America"), which would mean the engineer or the picker is refusing a fact for
   being false rather than for not being said.
3. **The 10 duplicates** — the link is written to a second copy of the right thing.
4. **The 17 prose-instead-of-a-link** — the host's, and the gate at the close
   (`_facts_hiding_in_prose`) only fires when the prose names something *already in the world*,
   which is why "wide receiver" slipped past. Widen that gate.
5. **Then, and only then, one full chain on the fixed code** + the 100 questions. ~$10, 3–4 hours,
   as a transient service. Before it, a 20-question smoke test over an existing world (~$1),
   because the question phase has failed for harness reasons three times.

Not on this list until the number moves: the picker on Nemotron, research as "pick it for me", the
demo. And `docs/architecture.md`, `contextvars`, the god modules — all argued in `decisions.md`.

---

## Item 1 — SETTLED 2026-10-01: a failed load left a shell where the next lookup finds it

**Found in `runs`, not in the source**, as usual: run 569 of run8 is
`thomas_kyd = Person.get(full_name="Thomas Kyd")` / `thomas_kyd.born_in = it`, and the damaged
row's `accessed_at` is 35 ms before it.

`store._load` does `memo[instance_id] = obj` *before* filling the values, because a cyclic
reference has to find the object there. A fill that raised therefore left a half-built object in
the identity map — and the identity map is what makes one row one object, so from then on:

- `Person.get(full_name="Thomas Kyd")` answered **`NotInWorld`** about a thing whose name the
  record plainly held, which is worse than a wrong answer;
- the next `save` of that shell wrote **null over every value it had**, which is the 21 entities.

And only `TypeError` was caught per row, while the door refuses in whatever words fit the mistake
(`ValueError` for a period that is not a moment, `AttributeError` for a word the class no longer
has) — so one such row aborted the whole load and produced the shell.

Both fixed: `_rows_onto` catches `TypeError | ValueError | AttributeError` per row and logs it, and
`_load` drops the object from both maps if the fill did not complete. Test:
`tests/test_review_fixes.py::a_row_that_will_not_load_costs_only_that_row`.

**What it was worth: 29 of the 105.** Not verified against a fresh run yet — item 5.

## Hypotheses that were wrong about item 1 (kept so nobody walks them again)

Twenty-one entities hold a name in the record and nothing in the image. Nine are `Person`. The row
is null in *every* column, `created_at` included, except `accessed_at` — so something called
`world.save()` on an object that had nothing in it.

- **ruled out** — `find()` is broken. It is not; the test called `world.find("City", "Chang'an")`
  positionally and the text landed in `history=`. Call it `find("City", name="…")`.
- **ruled out** — `retype` loses the name. In isolation it carries it, and it always writes
  `created_at`, which these rows do not have.
- **ruled out** — a reading renamed the thing. Real, and fixed 2026-09-30 by
  `ontology.reading_one`, but there are **0** renames in run8 (measured: 420 images agree with the
  record, 0 differ, 21 empty). It was the gate's shape, not this one.
- **ruled out** — `rebuild.py:50` builds entities with `object.__new__`. It does, and `_fill`
  always ends by setting `created_at`, which these rows do not have.
- **still true and still open, separately** — a stale reference saved after a `retype` flips the
  class back (`retype`, then `save(the old object)` writes the old class's rows). Reproducible. Not
  what cost the names, and worth its own fix: `runtime._hand_back_what_moved` repoints session
  variables and nothing repoints what a link holds.
- **explained** — the record holding `full_name` twice (once `agent`, once `world`) is the reading
  re-stating the name it was given, which is harmless and is what `ontology.reading_one` now
  allows through.

---

## Flickers — things that look like a bug and are not, or are not always

- **Tests time out under machine load.** `tests/test_round_trip.py` fails with
  `RunTimeout: the run took longer than 10 seconds` when the machine is busy (the user's own
  `gcg_prefix.py` / `fit_marks.py` / `ollama`, load 13–21) and passes alone. Seen twice on
  2026-09-30 and diagnosed twice. Check `uptime` before believing a timeout. Partly *also* real:
  a `define` asked the embedder five times, which is why `meaning.spending()` now bounds the whole
  run at 2 s.
- **A gate's number moves with the host, not the code.** 84% then 68% on the same 25 facts, 3 turns
  then 24. Use a gate to see that the chain runs; never to compare code.
- **The reading's own measurements are in the world.** `readings` and `portraits` tables in each
  run's `world.db`, plus `runs` and `value_history` — read those before theorising. Most of what
  was found on 2026-09-30 was found in `runs`, not in the source.
