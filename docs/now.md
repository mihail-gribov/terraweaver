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

State on 2026-10-02. Three of the world's own causes are closed, worth about 62 of the 105:

1. ~~The lost names~~ — **one mechanism closed** (a failed load left a shell, 29 facts in run8);
   the second survived five reproductions and is **guarded at the door** with a log line
   (`was about to be written without its`). The next run's log says where it comes from.
2. ~~Supersession by arrival order~~ — **closed** (27). Same world whichever order the facts are
   read in. The label half (28) is diagnosed; the check is no longer asked about a label; whether
   the door should hold the task open until the host says the fact in words **is the user's call**.
3. ~~Duplicates from a lookup blind to the classes beneath it~~ — **closed** (6 of 10). The other
   four are the host's own.
4. **Prose instead of a link (17)** — the close's prose gate *did* fire, 93 times in run8's host
   log. So the host was told and these are the host's; leave until measured.
5. **Measure — now.** A 20-question smoke test over `var/run8/world` (~$1) to see the question
   phase reach the end, then the full chain from scratch on today's code and the 100 questions
   (~$10, 3–4 hours, as a service). Read the new world with `why_it_failed.py` before reading
   its number, and grep its server log for the name guard.

Not on this list until the number moves: the picker on Nemotron, research as "pick it for me", the
demo. And `docs/architecture.md`, `contextvars`, the god modules — all argued in `decisions.md`.

---

## The full run on 2026-10-02's code — var/run9: 52%, with the names pass lost

`scripts/measure.sh full var/run9` — 455 facts, $5.47 to write, 1176 turns, 193 minutes.
**Accuracy 0.52** on the 100 questions. The link reading did its job — 163 of 189 typed, 26 left —
and then **the names pass died whole**: `RecursionError` inside a load, 241 bare names never read.
So 52% is the number *without* one of the three phases, which is the first thing to know about it.

**The crash, and my part in it.** `Entity.__setattr__` decides whether an assignment is an
overwrite by reading the current value with `getattr` — and for a relation's word that is the
reading property, which runs `related()`, which loads the entities at the far end, each of whose
loads comes back through `__setattr__` for its own words. The depth is the length of a chain
through the graph. That code is old; what made the chain the length of the *world* is today's
`kinds_of`: a lookup on `Thing` now loads every kind of Thing. Fixed where it belongs — whether
something is an overwrite is a question about the **stored** value, so it is read from `__dict__`
and nothing is computed. Verified on var/run9 itself: all 241 waiting names load cold, and
`Thing.find` across every kind takes 0.1 s.

**Lesson, written so it is not relearned:** a change that widens what a read *loads* can turn a
harmless recursion into a fatal one. `kinds_of` passed 27 of 27 and two gates; the gate is 25 facts
and never had a chain long enough. A whole-world load needs a whole world to test it.

**Next:** run the names pass on var/run9 (`measure.sh read`, resumable, cheap), then the 100
questions again over the same world — the number with all three phases, on one world, one code.

## var/run9's 48 wrong answers, laid out (free, read-only, on the world the questions saw)

13 said "not recorded"; **35 gave a value**. By what the world held, counting copies first:

| | shape |
|---|---|
| **17** | the later telling **never landed** (12 — the world holds the earlier value; 5 — nothing) |
| **7** | the later telling **landed and was ended** |
| **6** | **the world held the gold and the host answered otherwise** (Klapisch: Malaysia held, "France" said) |
| 4 | both holding — the word is many-to-many |
| 1 | a duplicate subject (it was the biggest shape in run8 — `kinds_of` is doing its job) |

The host **invents APIs**: `world.write(subject=…, relation=…, object="India")`, `Related(subject=…,
object=…)` built by hand. "rugby union was created in India" was written in a `world.write` block,
which has no such door.

### The world's own reading timed out on define_relation — and that one was mine

293 of 1151 runs failed (25%; run8: 439 of 1438, 30%). 35 were `RunTimeout`, **33 of them the
world's own reading on `define_relation`** (run8: 23 of 25, the same shape — not new). One
`define_relation` on var/run9's world costs 1.3 s on a free machine. By hour: the reading's first
hour averaged **1.7 s a run with 18 timeouts**, its third **0.16 s and none** — same code, same
world. The difference was a cold index, and **a claim I made on 2026-09-30 that had stopped being
true**: "the worker that ran past the deadline still writes its vector into the index". After the
SQLite write moved to the calling thread, a late worker computed the whole vocabulary and threw it
away, so the index never warmed while the embedder was slower than the budget. Now a late worker's
vectors land in a process-level dict (`meaning._LANDED`) and the next call on the owning thread
writes them down. Measured: first call gives up at 0.3 s, second finds ten vectors in 0.00 s with
no new call to the embedder.

## Where the gold went, for every wrong answer whose gold does not hold (var/run9)

- **14 — nothing between subject and gold, ever.** The host named them together in a list of
  names to identify, and never wrote the fact as a link. The host's write side.
- **8 — written only in runs that failed** (goaltender/pesäpallo, rugby union/India in a
  `world.write` block, Microsoft/Steve Jobs). The host did not re-send. The host's recovery.
- **7 — typed correctly and then ended.** The world's — and **mine**, see below.
- 1 — bare, the reading gave up.

### The 7: the hand-over compared a date the fact held from with a moment it was told

Two real cases, read off the links' own statements:

    Rozhdestvensky died_in Moscow  no start          created 02:21 (told first)
    Rozhdestvensky died_in USA     starts 2020-01-19 created 02:40 (told second — the gold)
                                   -> USA closed at 02:21: "held before Moscow began"

    Watsuki famous_for Fairly OddParents  from 02:20 (the gold)
            famous_for Rurouni Kenshin    re-typed by the reading at 03:57, ended the gold

`_hand_over` asked "when did the standing link begin" as `valid_from or created_at` and set that
against the new link's start. **Those are two different axes**: `valid_from` is when a fact held
in the world (the host passed the benchmark's day, 2020), `created_at` is when it was told (2026).
2020 < 2026, so the later telling was taken for the older and closed by `_HeldBefore` — the piece
added this morning. Yesterday's bug was two clocks; today's is two axes, and it is the same
mistake: **comparing things that are not the same kind of time.**

The rule: **compare like with like.** Both links carry a date somebody *said* → order by those.
Otherwise → order by when each was told. A date the world inferred at a hand-over
(`from_is == BEFORE`) is not a said date.

**SETTLED 2026-10-02**, tests first from the real cases, all three now green:
`_which_is_later(standing, start)` is the one decision both branches of `_hand_over` ask. And an
earlier *said* date is no longer refused (`_not_ours_to_end`): both dates were said, so nothing is
assumed — the new link is kept as what held until the standing one began, the standing one is left
alone, and the question is raised. `test_superseding` held the old refusal as a check; rewritten to
the new behaviour, on purpose.

**Watsuki was NOT the host re-telling** — I nearly "fixed" correct behaviour by assuming it. Read
off `runs`: at 03:57 it was the **names pass** (`session = the world's own reading`) writing
`it.famous_for = "Rurouni Kenshin"` out of the account given at 01:58, *now* — so by the order of
tellings it overruled the user's correction. The names pass now writes `as_of(said_at)` like the
link reading does. Reproduced both ways: without the change the correction is lost, with it it
stands. Test: `the_names_pass_writes_as_of_when_the_words_were_said`.

## The answering side — first look, 2026-10-02 (20 questions over run8, $1.33)

The question phase reached the end: 20 of 20, none failed to reach the world. 8 right. That world
was written with yesterday's code and its number is not today's; what it is good for is *where
the answers go wrong*, which nothing had measured until now. Of 12 wrong: 5 "not recorded"
(expected, the world holds 66% of facts) and **7 wrong values**, read against what the world holds:

| question | the world holds | whose |
|---|---|---|
| CEO of Microsoft (gold Steve Jobs) | Steve Jobs *holds*, Satya Nadella *ended* | **the host's** — the world was right |
| Germany's continent (gold Africa) | **three Germanys**: Africa is on a `Thing` Germany the host made, Europe on the `Country` | **duplicate** — the host asked `Country.find` and got Europe |
| author of Sidereus Nuncius (gold Beckett) | one book, Beckett *and* Galileo both holding | **no supersession** |
| quarterback's sport (gold Muay Thai) | one thing, Muay Thai *and* American football both holding | **no supersession** |
| Kingdom of Ireland's religion | Zoroastrianism *and* an entity showing a raw id | the lost name; the host read its description |
| goaltender's sport (gold pesäpallo) | Ice hockey only | the later telling never landed |
| Tunisia team's sport (gold basketball) | baseball only | the later telling never landed |

**Corrected the same day — the first version of this table was wrong.** It said three of seven
were "both holding". The diagnostic behind it collected links of *every* entity whose name matched,
so Germany's three copies looked like one Germany with two continents. Re-run by the link's own
ends against each copy separately: two are genuinely both-holding, Germany is a duplicate. **Lesson
for the next diagnostic: count the copies of a name before reading its links as one thing's.**

So, of seven wrong values: **2 no supersession** (the word typed many-to-many, so both tellings
stand and the host breaks the tie with what it knows of the real world); **1 duplicate** (made by
the host, almost certainly because `Thing.get` did not see the `Country` — closed today by
`kinds_of`); **1 lost name** (guarded today); **2 later tellings that never landed**; **1 the
host's own** — the world held the right answer and the host gave the other one.

What the host was actually shown, read from `host.jsonl`: for Germany, `located_in` returned
`[Europe]` — one value, because it was asking the copy that had one.

## Item 1 — ONE mechanism closed, and the loss still happens: there is a second

**Measured on the third gate (25 facts, all of today's fixes, free machine):** 45 images agree
with the record, **0 renamed, 3 with the name lost** — `Person Thomas Kyd`, `City Berkeley`,
`City Bengaluru`. In run8 it was 420 / 0 / 21. As a rate that is 6% against 4.8%: **no improvement
measured.** The mechanism below is real, reproduced and tested, and it is not the only one.

The three break into two shapes, which is itself new information:

- `Person Thomas Kyd` — every column null but `accessed_at`, `aliases` and one `$ref`, and
  **`created_at` null**: the shell shape, the one closed below.
- `City Berkeley`, `City Bengaluru` — the row is **full** (`created_at`, `descriptions`,
  `located_in`, `country` all set) and only `name` is null, with **no `value_history` row for
  `name`**, so that row was never written non-null: the City row was created without the name.

### What is eliminated for the City shape (do not re-walk these)

Each was reproduced faithfully and came out clean — name intact, row otherwise identical to the
damaged one:

- `become("City")` on an in-memory Thing. Clean.
- `become("City")` on a Thing **reloaded** after clearing the identity map. Clean.
- the whole `portraits.formalise` pass with stub engineer and picker, growing `City` and placing
  the thing under it (`comes_in` enqueues it; `world.new` alone does not). Clean.
- the same, where the engineer's code also writes an attribute **and a link to another entity**
  (`it.country = "England"`, `it.located_in = Thing.get(...)`) — which is what the gate's code did
  and what its damaged row holds. Clean.

- **ruled out** — a *second* reading of the same thing. `portraits` in the gate world: each of the
  three was read **once** (one query, free).
- **ruled out** — `City` already existing, with the thing placed second under it (London first,
  then Berkeley and Bengaluru, through the real pass). Clean.
- **ruled out** — `Thing.identify(...)` as the creating door: the host made fourteen places and
  organisations in one loop that way, all were placed under grown classes, and only two lost the
  name.

**Stopped reproducing after five clean ones, and guarded the door instead (2026-10-02).**
`World._with_its_name(instance)` runs before every image write that does not go through a load —
`World.save`, `_determined`, `retype` — and if the identifying attribute is empty while the record
holds a value for it, the record's value is put back. It **logs a warning every time** with the
class and the id. So the next run does not need a reproduction: grep its server log for
`was about to be written without its` and the entity and the moment are there, and `runs` at that
moment says which code handed it over. Both shapes are covered by a test.

## Item 1a — SETTLED 2026-10-01: a failed load left a shell where the next lookup finds it

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

## Item 2 — the "no link" bucket, split (2026-10-01)

Of the 105, the ones where both ends are in the world under single copies and nothing joins them
split cleanly in two:

- **27 — a link IS there between the right ends, and it is ended.** Both the bare `related` link
  and the correctly typed one, both `valid_until` set.
- **28 — no link between them at all, ever.** Diagnosed 2026-10-01, and it is not the picker
  refusing true-but-strange facts. See below.

### The 28: the reading was given a label, not the fact in words

`readings.words` is what `words_of(link)` found on the bare link, and **124 of 442 (28%) hold a
single bare word** — `created_in`, `citizen_of`, `affiliated_with`, `capital_is`, `has_capital` —
with no sentence anywhere. The host wrote `label=` where the fact in words was wanted.

Everything downstream is built around having the sentence, so with only `has_capital` to go on:

- the **look** guesses, and guesses towards a magnet: `has_capital` (Iran/Tehran) and `works_in`
  (Mahmoud Abbas/politician) were both answered **`mayor_of`**;
- the **check** then correctly says `not_in_it` — 217 readings carry that verdict, at 0.51 to 0.99
  — because the words really do not bear the claim out;
- the goes run out, `settle_by_verdict` takes the link back, and the fact is gone.

So the picker and the engineer are doing their job and the fact is lost upstream of both. **The
world accepts this**: `relations.relate` offers the host a choice — "either a word for it
(`label=…`) or the fact in the words it came in (`description=…`)" — and the label is the cheaper
one to produce, so that is what a host produces.

**What to do, and it is a decision, not a defect** (the rule it touches is "the host narrates, the
world formalises", and the other rule it touches is "never refuse a write; accept it and hold the
task open for what is missing"):

- accept the label as now, and at the close tell the host which links have no sentence and what
  that costs — the shape every other missing thing is handled in;
- and, meanwhile, a label-only link is not something the check can be asked about: there are no
  words for a claim to be borne out by, so asking is a call spent on a foregone refusal. The
  reading should take the label as the word and skip the check. **That half is purely the world's
  own business and goes in without asking.**

### The 27: the reading types facts in arrival order, and supersession is by order

Traced to the link's own statements (`var/run8/world`, `PlaysPosition`):

    Hines Ward -> cornerback     typed 02:22:11, ended 02:25:30  (fact 37 — the telling that stands)
    Hines Ward -> wide receiver  typed 02:25:31                  (fact  4 — the telling it replaced)

A one-at-a-time word ends the standing link where the new one begins, so **the link written last
is the one that stands**. The reading is deferred and resumable by design, so what is written last
is whichever pass the queue fell into — not what the user said last.

- **ruled out** — `when_said` returning `""` for links the host wrote with `label=` rather than
  `description=`. Measured: 0 of 427 bare links in run8 had no moment. The queue's sort was fine;
  it is the *pass boundary* that reorders, because each pass sorts only what is still unread.
- **done** — `when_said` now falls back to every statement about the link and then to its birth,
  and returns a moment rather than a string. Right in itself; it is not what fixes the 27.
- **done** — the reading types a fact **as of when it was said** (`timeutil.as_of`, entered per
  link in `formalise.formalise`). So the hand-over compares the two facts' own moments instead of
  their arrival order.
- **done** — `ontology.now_utc` reads the world's clock, not the wall clock. `created_at` is
  written from it and `created_at` is what "when did this link begin" falls back to, so under
  `as_of` every such comparison was against a moment six years later.
- **REVERTED, and why** — guarding the "no date was said" branch of `_hand_over` the way the
  dated branch is guarded (refuse to end a link that began after the boundary) **turns correct
  supersession off**: with it, both tellings stand in both orders. Losing supersession is worse
  than losing the 27. Do not re-add it without first establishing which branch of
  `_check_functional` ends what — `AT_A_TIME == "at_any_time"`, so a `many-to-one` word takes the
  `functional == "at_any_time"` branch and hands over there.
- **SETTLED 2026-10-02 — the revert was answered, and the guard is back.** The guard was right;
  `created_at` was not. `Entity.__init__` took `datetime.now()` directly, past `now_utc`, so under
  `as_of(2020-01-01)` a link's `created_at` was 2026-10-02 — "when did this begin" was always the
  wall clock against a boundary in the world's 2020, and the guard refused every hand-over. Found
  in one line: make a link under a moved clock, print `created_at`. Now `created_at` is on the
  world's clock and `accessed_at` stays on the wall's (attention, compared only with itself);
  `Entity._show` and `Spell.holds` read "now" from the world as well.
- **and the last piece** — the older telling arriving second was left *open* beside the newer one.
  `_hand_over` now returns `_HeldBefore(moment)` when it refuses because the new link is the
  older one, and `relate` closes the new link where the later one began. Both orders now give the
  same world: `cornerback` stands, `wide receiver` held until 2020-01-02. Test:
  `the_later_telling_stands_whichever_order_it_is_read_in`.

## Item 3 — SETTLED 2026-10-01: a lookup did not see the classes beneath it

Of the ten facts where one end is in the world twice, **six have a bare `Thing` copy made by the
world itself** beside the right one under a grown class: `Thing English` beside `Language English`,
`Thing Canada` beside `Country Canada`, `Thing Asia` beside `Continent Asia`. The other four are
the host's own doing (two `Thing Soviet Union`, both `stated by ['agent']`).

The six are explained by one line, reproduced without a model:

    t = world.new("Thing", name="Canada");  t.become("Country")
    Thing.get(name="Canada")   ->  NotInWorld: no Thing with name=Canada in the world
    Thing.all()                ->  []

The names pass places things under classes the world grew — that is its whole job — and from that
moment every `Thing.get` for them failed. A host or an engineer told "there is no such thing" has
one honest move left, which is to make a second one. `Person` and `AIAgent` are declared
`parent: Thing` in the base specs, so a kind of a thing *is* a thing by the world's own word.

**Fixed, and the asymmetry is deliberate** — do not "finish the job" by making listings inclusive
too:

- `World.kinds_of(class_name)` is the class and everything under it, `own` classes excluded (a
  Task is a kind of Event, and `Event.all()` is a host asking about its calendar).
- **Lookups read inclusively**: `find`, and `get`/`identify` through it.
- **Listings stay exact.** `[i.name for i in Thing.all()]` is a line a host writes constantly and
  a Person has no `name`, so an inclusive listing turns it into an `AttributeError` that costs the
  rest of the block — it broke two of our own tests exactly that way, one of them *inside* a host
  run. `all(kinds=True)` is there for whoever wants it.
- An empty listing that *has* kinds says so once per class, with the count and which class to ask,
  instead of answering "nothing".
- A sweep over every class (`selecting.where`) de-duplicates by id: the same entity was coming
  back under its own class and under each ancestor — six of five on one query.

## Flickers — things that look like a bug and are not, or are not always

- **Tests time out under machine load, and the threshold is low.** Seen at load 13–21 on
  2026-09-30 and at **load 38** on 2026-10-01 (`specialist.py --score`, a postgres DELETE, the
  noosphere reading server — none of them ours). The tell is in the result itself: `duration_ms`
  of 12 000–15 000 on a run that takes under a second. **Above about load 20 the suite cannot be
  believed and a gate must not be started** — a gate at that load measures the other job. Check
  `uptime` first, every time.
- **A test that depends on today's date.** `tests/test_periods.py` asked "what held on
  2026-10-01" about a tag written `permanent=True` with no start — so the tag began at the moment
  the test ran, and from **2026-10-01** the question fell before its start. It passed for months
  and then failed twice in a row, which reads exactly like a regression in whatever was last
  touched (it cost twenty minutes of looking at `now_utc`). Fixed by giving the tag a start it can
  name. **Before blaming your own change: `git stash` it and run the test again.** Three instances so far,
  all on 2026-10-01: `test_periods.py` (`permanent=True` with no start, asked about 2026-10-01),
  `test_world_state.py` (`when=date(2026, 10, 1)` — a remark dated today sorts behind one recorded
  today at 02:21, so "newest first" flips). Both now use a date relative to the run.
  **Went off 2026-10-02, as predicted:** `test_runtime.py:130` compared `starts=date(2026, 10, 1)`
  against `today()` and expected it in the future. Now relative to the run.
  **Still armed:** `test_round_trip.py:127` `until=date(2026, 12, 31)` ("true until the year
  turns") goes off on 2027-01-01. Seventy-odd fixed 2026 dates in the suite altogether.
- **(the same thing, as first written)** `tests/test_round_trip.py` fails with
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
