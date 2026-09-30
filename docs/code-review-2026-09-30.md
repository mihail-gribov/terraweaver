# Code review, 2026-09-30

A review of the whole `terraweaver/` package (54 modules, ~20k lines), `benchmarks/`, `scripts/`
and `tests/`, against `docs/architecture.md` and the rules in `docs/decisions.md`. Branch
`facts` at commit `9045ab8`.

**Method.** Every module was read in full. Every finding marked *(reproduced)* was reproduced on
an in-memory world (`tests/base.py` doors) with a snippet; the rest were verified by reading the
code and its callers. Module metrics (sizes, imports, cycles, function lengths) were computed
over the package with `ast`. All 26 test scripts pass (`python tests/test_*.py`). Nothing in the
repository was changed.

The review is in three parts: the architecture (the main emphasis), the findings by layer with
`file:line`, and a short ordered list of what to do first.

---

## 1. Summary

The design is coherent and unusually well argued: append-only statements, images as a
derivation, trust-then-time resolution, refusals that name the data they protect. Those
invariants are visible in the code, not only in the documents. The problems are at the seams,
and most of them have one of four causes:

| Cause | Where it shows |
|---|---|
| Process-wide mutable state | one world per process; `world.now`, sandbox modules and the current world leak between sessions |
| Modules committing on the shared connection | the "a run that raises keeps nothing" guarantee is void; 29 `commit()` sites in 16 modules |
| Derived tables rebuilt on read | `periods`, `texts`, `meanings` rebuilt per read; quadratic at a few hundred entities |
| Silent `except Exception: continue` | a callable-vs-object contract mismatch kept a whole feature dead in the served world |

Eleven findings are rated high. Each is one paragraph in section 3; the short list:

1. `periods.rebuild_for` commits inside the statement transaction; a failing statement that
   touched tags keeps its writes *(reproduced)*.
2. `rebuild_for` deletes an entity's repeat rules and never reinserts them *(reproduced)*.
3. Tie-break between statements with equal `last_said` is by string id, so `…:10 < …:9`; under
   `set_now` every correction in a run is lost on rebuild *(reproduced)*.
4. `properties._at_once` sorts starts before ends at the same moment, so every clean handover is
   reported as a broken one-at-a-time rule *(reproduced)*.
5. `_check_functional` raises one `one_<kind>_per_object` question per new subject, not once per
   object *(reproduced: 9 questions on one organisation with 10 employees)*.
6. `tags.holding` rebuilds the entire `periods` table on every read *(reproduced: 0.24 s at 100
   entities, 0.84 s at 200)*.
7. `set_variable` never works: it builds `world.pin(...)` without `keep`, which `pin` refuses
   *(reproduced)*.
8. `world.pin("agent", …)` is allowed and shadows the assistant binding in every session
   *(reproduced)*.
9. `start_task` over a task that cannot close leaves the old task open and leaks its state into
   the new one *(reproduced)*.
10. Sandbox module objects are shared: `math.sqrt = 7` in one session is seen by every other
    session and world *(reproduced)*.
11. `inspector.look_at_types` calls `world.engineer(...)`, but the server installs an
    `outside.Open` object that is not callable; the `TypeError` is swallowed and no type is ever
    read in the served world *(reproduced)*.

---

## 2. Architecture

### 2.1 What holds up

- **Statements are the record; everything else is a derivation.** `facts.py` is append-only,
  `assembly.py` is pure over the statements, `rebuild.py` is idempotent. The `not_recording`,
  `trusted_writes` and `stating` context managers make "the image changes here, the statement
  goes into the record" enforceable rather than hoped for.
- **Refusals name the data.** `relations.py` refusals, `NotInWorld`, `_construction_problem`,
  `did_you_mean`/`take_as` all follow the rule from the architecture document.
- **Growth is checked.** `growth.apply_growth` refuses unknown keys and additions without a
  `because`.
- **Testability at the door.** `open_world()` in one line and `tests/base.py` make every finding
  in this review reproducible in a few lines. That is rare and worth protecting.
- **The right patterns already exist in the codebase** where performance was fixed once:
  `world._worth_loading` (SQL over the values table instead of loading a class) and
  `periods.rebuild_for` (one subject, not the table). Most of the performance findings below are
  places that did not copy them.

### 2.2 Process-wide state: one world per process

`ontology.py` keeps ten pieces of mutable module state: `_WORLD`, `_CHANGED`, `_STATING`,
`_WRITE_GUARD`, `_TRUSTED`, `_FILLING`, `_TRACK`, `ACCESS`, `_OPEN_TOKENS`, `_SAID_IN_WORDS`.
`timeutil._MOMENT` (the world's "now") and `sandbox.MODULES` (the module objects handed to host
code) are the same kind of thing. `World.__init__` calls `set_world(self)`, so opening a second
world silently redirects every `Person.find/new/relate` of the first; the package docstring
documents this as "only one world is current at a time" and offers a context manager.

Consequences that were reproduced:

- `world.now` set in session A is read by session B and survives `finish_task`
  (`runtime.py:289-301`).
- `math.sqrt = 7` in session A is `7` in session B (`sandbox.py:246-267`).
- A stored procedure captures `current_world()` at bind time and keeps pointing at the previous
  world under the `open_world()` context manager (`procedures.py:137-146`).

This is the single design decision that makes the layer hard to test below the door level and
is the origin of every session-leak bug in section 3. The fix is not large: bind the world per
class (or a `contextvars.ContextVar`), make sessions own their clock and their module namespace,
and assert on rebinding until then.

### 2.3 Transactions: the guarantee is void

`runtime._exec_by_statement` runs each top-level statement inside `store.transaction()`, and the
server's `run` tool promises "a run that raises keeps nothing it wrote". `store.transaction`
implements that with `conn.commit()` on success and `conn.rollback()` on failure — on one shared
connection. But 29 sites in 16 modules call `conn.commit()` directly (`periods`, `tags`,
`facts`, `world`, `texts`, `meanings`, `questions`, `comments`, `portraits`, `variables`,
`procedures`, `selves`, `inspector`, `ticks`, `runtime`, `store`). Any of them reached inside a
statement commits everything the statement has done so far.

Reproduced: `x = [Person.new(full_name="Bob"), 1/0]` rolls back (Bob is gone), but
`x = [Person.new(full_name="Ann", tags=["friend"]), 1/0]` keeps Ann, because the tags write
goes through `periods.rebuild_for`, which commits (`periods.py:329`). `run_script`'s docstring
in `store.py` describes exactly this class of bug.

Rule to adopt: only `store.transaction` commits. A module that needs durability outside a
transaction opens one. This is a one-day sweep and it restores a guarantee the architecture
document and the host guide both rely on.

### 2.4 Derived tables rebuilt on read

Three derived tables are rebuilt from the statements on read rather than invalidated on write:

| Table | Rebuilt by | Called from |
|---|---|---|
| `periods` | `periods.rebuild` (DELETE + full re-derivation) | `tags.holding` on every read; `vocabulary` once per entity |
| `texts` | `texts.rebuild` | `texts.search`, i.e. every `like()`, `entities()`, `similar()`, and again in `_holding` |
| `meanings` | `meaning.refresh` walks `world.all(cls, history=True)` for every class, twice | every `like()` |

Together with whole-class loads in the hot paths (`relations_of` loads every row of every
relation class when `kind=None`; one `relate()` loads the type's table four to six times;
`_named_elsewhere` loads and sorts every entity on every `new()` and find miss; `graph.reaches`
loads a class per frontier node; `typed_between` loads every typed class per go), the batch cost
is quadratic. Measured: 100 `new`+`relate` take 0.28 s at n=100 and 0.63 s at n=200. The
455-fact runs the decision log describes are already on the wrong side of this.

The fix is one pattern applied everywhere: rebuild on write with a per-subject dirty flag, and an
index by `(subject_id, object_id)` in the store. `_worth_loading` and `rebuild_for` are the
templates.

### 2.5 Two doors, three copies: duplication

- **`WorldView` (runtime.py) vs `World` (world.py).** Sixteen public methods exist under the
  same name in both (`all`, `find`, `get`, `identify`, `new`, `ensure`, `where`, `relate`,
  `verify`, `take_in`, `tagged`, `untag`, `happening`, `repeats`, `like`, `rebuild`). Most
  `WorldView` methods are one-line pass-throughs; a few (`all`) add behaviour. A facade is fine,
  but it needs to be mechanical (generated, or a `__getattr__` with an allow-list) so the two
  cannot drift.
- **`classes_here`** exists three times, byte-identical: `formalise/make.py`, `portraits.py`
  (`_classes_here`), `sentences.py`. Only the first is used.
- **Two write loops** with different senior-engineer logic: `formalise.formalise_one` and
  `portraits._the_loop`; two measurement stores with different shapes (`readings` vs
  `portraits`).
- **Five benchmark `main()`s** re-implement the record/ask/summarise loop; `ASK` is copied
  verbatim into `run_fc.py`, `run_blank.py`, `reask.py` and `experiments/base_run.py`; `commit()`
  is computed four ways; `experiments/base_run.start_base_server` duplicates
  `host.start_server` minus the environment. One `benchmarks/loop.py` would remove ~250 lines.
- **Enum parsing** is done in three places (`ontology.py:1299`, `:1654`, `:1672`); the second
  parse in `__setattr__` re-matches a value `_check_type` has already matched.
- **"Holds at"** is implemented twice (`timeutil.py:132-152` exact, `facts.py:137` bound).
- **Name resolution to a folder** lives only in `open_world`; `server.py --blank --db mike`
  opens a file literally named `mike` in the cwd (`server.py:387-395`).

### 2.6 God modules and long functions

| Module | Lines | Carries |
|---|---|---|
| `ontology.py` | 2244 | class factory, `Entity` (periods, repeats, tags, graph walks, timeline, questions), the `__setattr__` state machine, growth hooks |
| `runtime.py` | 2085 | `WorldView` facade, sessions, task lifecycle, close-time readings, describe/catalogue, variable tools, per-statement executor, ~15 report formatters |
| `relations.py` | 1806 | type construction, `relate` with seven checks, functional/role/cycle rules, handovers, timeline, path description |

| Function | Lines | Note |
|---|---|---|
| `runtime.finish_task` | 234 | stacked gates; the `recording` gate ignores `closing` (finding 3.3.3) |
| `relations.relate` | 207 | seven checks, each rescanning the table |
| `authoring.define_relation` | 170 | 11 parameters; no duplicate check |
| `runtime.run` | 159 | |
| `ontology.Entity.__setattr__` | 154 | comments outnumber code; see below |
| `selecting.where` | 59 | 12 parameters |

`Entity.__setattr__` is the clearest case. It refuses, corrects, grows the class, normalises,
records history, states a fact and notes the change, in one method, with the decision log for
each branch inline. It also contains two constructs that do nothing:
`me = _name_of_me(self) if "_name_of_me" in globals() else "it"` (line 1230; the function is
always defined) and `given = value if "given" not in dir() else given` (line 1316; `given` is
never a local, so this is `given = value`). Splitting it into `_coerce`, `_admit` (refuse or
grow) and `_record` would make each testable.

Three splits would pay for themselves: task lifecycle and gates out of `runtime.py` into
`tasks.py`; result formatting into its own module; `WorldView` beside `world.py` as a generated
facade. `relate()` should load the type's rows once and pass them to its checks.

### 2.7 Coupling through attributes bolted onto `World`

`World` is extended at runtime by whoever installs into it: `extras` (a dict of bound methods
from `authoring.install`), `engineer`, `better`, `jev`, `grown_dir`, `specs`, `pending`,
`_reading_it_later`. Readers use `getattr(world, "x", None)` and `(world.extras or {}).get(...)`;
two of them reach a bound method's `__self__` to call a second method on the installer
(`ontology._take_the_word` → `extras["attribute"].__self__.provisional`;
`runtime._words_taken_on_the_fly` → `.unsaid()`).

The cost showed up as finding 11: `look_at_types` expects `world.engineer` to be callable and
`write_the_questions` expects it to have `.json(...)`; the server installs an `Open`. Neither
test nor type says which is right, and the bare `except` hid the mismatch. The fix is a declared
optional protocol on `World` (`take_word`, `engineer: Engineer | None`) installed explicitly,
and no `__self__`.

### 2.8 Import structure

54 modules, 1 top-level cycle (`formalise` package), but **557 cycles once function-local
imports are counted**; `ontology` is in 540 of them, `portraits` 453, `world` 449, `authoring`
446, `runtime` 419. `ontology.py` alone has 12 function-local imports, `world.py` 9,
`runtime.py` 7. Local imports are used as the cycle-breaker everywhere, which means the
dependency graph the file headers show is not the real one, and an import moved to the top of
a file can break start-up. The direction that would untangle it: `ontology` should not import
`world`, `authoring`, `portraits` or `relations` at all (it does so through `current_world()`
and local imports); those are layers above it.

### 2.9 Silence: 61 `except Exception` sites

`except Exception: continue` / `return None` appears in every module of the upper layers, with
`noqa: BLE001` and a comment saying one failure must not stop the world. That is the right
policy for the world's own work and the wrong policy for programming errors: it turned a
`TypeError` (finding 11), a `TypeError` in `portraits._make_one` (a class silently lost when the
engineer emits an extra attribute key) and an `ImportError` in procedures into silence. A
`log.debug` with the exception in each of these would have surfaced all three on the first run.

### 2.10 Documentation versus code

`docs/architecture.md` was written "before the work rather than after it" and has not been
brought back to what was built. Contradictions a reader will trip on:

- **Two databases.** The doc promises `var/world.db` + `var/agenda.db` and "the agenda refers, it
  does not quote". There is one database; `questions`, `tick_runs`, `runs`, `procedures`,
  `link_checks`, `type_checks`, `tag_reviews`, `entity_access` all live in it through
  `store.conn`, and question texts embed names ("two records look like one person: X and Y",
  `ticks.py:90-96`; `runtime.py:498-501`). "Delete everything about me" is therefore not a
  one-file operation.
- **Modules.** The doc lists 15 modules; the package has 54. `portraits`, `authoring`,
  `formalise/`, `meaning`, `outside`, `comments`, `texts`, `periods`, `recurrence`, `tags`,
  `selves`, `nameforms`, `restructure`, `inspector`, `sentences`, `selecting`, `variables`,
  `lookup`, `initiative`, `graph`, `properties` are absent.
- **"To go once the migration lands": `history.py`** is still live (`world.py:183`,
  `ontology.py:631,742`), keeps a second non-statement record of past values, stores `until` as
  ISO text while everything else moved to integer stamps, and is wiped by `clear_all` on
  rebuild. The `selves.py:384-390` write-through, also marked as going away at step 2, is still
  there and writes the two parties' images by a second rule that ignores trust.
- **"Core classes are never edited by the world; never a redefinition."** A class the world
  changes is written *whole* into `grown/` and replaces the preset on load
  (`growth.py:63-67`, `authoring._save`, `ontology._keep_spec`), bypassing every
  `GrowthRefused` check. `growth.py`'s docstring describes the newer design; the architecture
  document does not.
- **"Every refusal must name the data it protects" / take all, then ask.** `_check_roles`
  (`relations.py:328-354`) hard-refuses a second holder of a role at the write door even when
  the first holder's link has ended.
- **Tickets, `done_when`, `Ticket`** appear in the doc and nowhere in the code; the world's own
  work is `Task` in `ontology/core/Task.json`. `ticks.py` is described as "a procedure cron
  calls"; nothing constructs `Ticks` or calls `tick()` anywhere in the repository.

Also: 28 % of the package is comments and docstrings, and a large share of those are decision
logs ("Measured 2026-09-28: eleven such attributes…") that duplicate `docs/decisions.md`. The
rule "record why, not just what" is right; the place for the why is the decisions file, with a
one-line pointer in the code. Inline, it makes a 154-line method out of 40 lines of logic.

### 2.11 Dead code and leftovers

- `run_task.py` imports `terraweaver.agent` and `terraweaver.impls`; neither exists.
- `agentfile.py` (self-declared parked), `onboarding.py` (one-line pass-through).
- `assembly.unsettled`, `assembly._kept_apart` (written for the `not_same_as` case in finding
  3.1.6 and never called), `runtime._merge_questions`, `runtime._entity_ids`, result keys
  `rolled_back` and `standing` with no reader, `usage.times`/`clear`, `texts.holding`/`about`,
  `authoring.describe_class`, `portraits._a_word_it_has_not`, `WIDEST`, the
  `SYSTEM/FORMALISE/MAKE_ONE/KEEP_ONE` aliases, `inspector.CHECKLIST/NOT_CHECKED/TTL`,
  `variables.turns_left` column, `outside.Local`, `getattr(entity, "_better", None)` in
  `portraits.py:431` (nothing sets it).
- `if True:` blocks (`selves.py:141`, `ontology.py:2179`), `if False:` (`relations.py:640-653`),
  `if …: pass` (`relations.py:424-425`), `world is None` checks after `current_world()`, which
  raises (`ontology.py:198,1717,1750`, `questions.py:112`).
- Unused imports: `sentences.py` (`json`, `prompts`, `datetime`, `timezone`), `meaning.py`
  (`urllib.error`), `outside.py` (`math`), `selves.py:349` (`ontology`); `import ast` and
  `import json` re-imported inside functions.
- `.gitignore` lists `var/` twice; `terraweaver.db` in the repository root is an ignored
  leftover from 2026-09-03.

### 2.12 Tests

- 26 scripts, all passing, each its own runner with its own `check()`; there is no `pytest` or
  `unittest` entry point, so nothing runs them all, and `docs/DEV.md` lists a loop over four of
  them.
- Eight modules are referenced by no test: `agentfile`, `inspector`, `llm`, `onboarding`,
  `restructure`, `selecting`, `sentences`, `ticks`. `sandbox`, `server`, `portraits`, `graph`,
  `timeutil` are referenced by one.
- Every high finding in this review is on an untested path: rebuild under `set_now`,
  `rebuild_for` on a subject with repeats, rollback of a statement that touched periods, a
  handover through `properties.contradicts`, `set_variable`, `start_task` over an unclosable
  task, a task close with a `Nemotron`-shaped engineer.

---

## 3. Findings by layer

Severity: **H** high, **M** medium, L low. *(reproduced)* means run on an in-memory world.

### 3.1 Statements, images, periods (`facts`, `store`, `assembly`, `resolution`, `values`, `rebuild`, `history`, `selves`, `nameforms`, `periods`, `recurrence`)

1. **H** `periods.py:84,329` — `rebuild`/`rebuild_for` call `conn.commit()` inside the host
   statement's transaction; a failing statement that wrote tags keeps everything it did
   *(reproduced, section 2.3)*. Drop the commits; let `store.transaction` end.
2. **H** `periods.py:309-330` — `rebuild_for` deletes the subject's rows including repeat rows
   and reinserts only `_from_statements`, so every tags write and every `spells` read wipes that
   entity's repeats until a full rebuild *(reproduced: `cycles()` empty after `rebuild_for`)*.
   Exclude `every IS NOT NULL` from the delete.
3. **H** `facts.py:352` + `assembly.py:280` — the tie-break for equal `last_said` is the string
   id (`facts_Person:10` < `facts_Person:9`) and `resolve` keeps the first of a stable reverse
   sort; under `set_now` (the replay mode the code was built for) 12 successive `city`
   statements resolve to the first *(reproduced)*. Sort by `(last_said, table, int(row))` or
   add a sequence column; test rebuild under `set_now`.
4. **M** `assembly.py:276,326,334`, `periods.py:131,147,197` — `datetime.utcnow()` instead of
   `timeutil.now()`: images resolve at the wall clock while `happening()` uses the world's
   clock, so the two disagree under `set_now`. Resolve `at` once at the top of `assemble`.
5. **M** `facts.py:209-218` — restatement dedup ignores `run_id` and can move `restated_at`
   backwards; `retract_run("A")` removes a statement run B also made *(reproduced)*.
6. **M** `assembly.py:180-197` — `not_same_as` is honoured only for the direct pair; a told
   `same_as a b` plus a rule match `b~c` joins `a` and `c` that the user separated
   *(reproduced)*. `_kept_apart` exists for this and has no callers.
7. **M** `history.py`, `selves.py:384-390` — migration leftovers writing images by a second
   rule (section 2.10).
8. **M** perf `assembly.py:126,150,289,308,316`, `rebuild.py:117` — `facts.about(subject)` three
   to four times per subject per rebuild, `matching_pairs` O(N²) in both directions,
   `unsettled` repeats all of it. Load `facts.all()` once, group by subject; bucket candidates by
   class and first name token.
9. L `store.py:121-126` — rolled-back objects keep their place in `self.made` and are reported
   as created. `store.py:281-283` — `except TypeError: continue` around `_fill` also swallows
   errors from loading a referenced instance. `store.py:200-209` — `clear_all` leaves orphan
   value rows of a class with no instances.
10. L `facts.py:306-314` — `stale()`/`basis_of()` only look at the conclusion's own subject; a
    basis on another subject makes the conclusion stale at birth. `facts.py:229` — "never from
    conclusions" is bypassed when a basis is passed as an id string. `facts.py:386` — `_iso`
    returns an int now.
11. L `resolution.py:138` — options shown to a person are numbered from 0. `resolution.py:266-279`
    — choice 2 without `incoming_attrs` silently saves as-recorded.
12. L `values.py:376-382` — `Url.normalize` raises `ValueError` on a bad port *(reproduced with
    `http://x.com:abc/`)*; one malformed stored URL makes every comparison through
    `canonical()` raise.
13. L `recurrence.py:441` — `read("0 weeks")` yields `Every(0)`; `which()`/`covers()` divide by
    zero *(reproduced)*.
14. L `nameforms.py:463-475` — `_pairs()` rebuilt on every `by_table` call; `:501-504` —
    `by_initial` does not check the "unless two Ms are about" its docstring promises.
15. L `timeutil.py:132-152` vs `facts.py:137` — two "holds at" implementations.

### 3.2 Ontology, relations, world (`ontology`, `relations`, `world`, `properties`, `growth`, `graph`, `tags`, `questions`, `selecting`, `lookup`, `restructure`, `variables`, `conditions`)

1. **H** `properties.py:161-175` — `_at_once` sorts `(moment, -change)`, so a start at T
   precedes an end at T and a clean handover counts as two held at once; `contradicts()` then
   reports every world-made handover as a broken rule, which is what `findings()` feeds the
   agenda *(reproduced)*. Sort key `(moment, change)`.
2. **H** `relations.py:1129-1148` — `_check_functional` raises `one_<kind>_per_object` with
   `involves=[r.subject, subject]`, so the dedup key differs per pair and every new employee of
   an organisation opens another question *(reproduced: 9 at 10 employees)*. Dedup on
   `(obj, kind)`.
3. **H** perf `tags.py:81-90` — `holding()` runs `periods.rebuild(world)` (DELETE + full
   re-derivation) on every read; `vocabulary` calls it per entity; `tagged`, `due_for_review`,
   `merge`, `selecting._carries` all go through it *(reproduced: 0.24 s at 100, 0.84 s at 200)*.
   Use `rebuild_for`, or rebuild once per `vocabulary`.
4. **M** `ontology.py:19-37,66-79` — process-wide globals; `World.__init__` rebinds the current
   world (section 2.2).
5. **M** `ontology.py:1884-1912` — `_relation_role` captures `rel.get("functional")` when the
   property is lent; a later `Type.one_per_subject = False` is not seen: two links held,
   `eve.works_at` returns one `Thing` *(reproduced)*. Read the spec inside `read()`.
6. **M** `ontology.py:2084-2100` — `_take_the_word` reaches `extras["attribute"].__self__.provisional`
   behind `except Exception: return None` (section 2.7).
7. **M** `world.py:937-975` — `create()` with `tags="vip"` (bare string) normalises the image but
   writes no statement, so the tag vanishes on rebuild *(reproduced)*. Use `instance.tags`.
8. **M** perf `world.py:320-367` — `_named_elsewhere` loads and sorts every entity of every class
   on every `new()` and every find miss; `_worth_loading` (`:564-610`) is the pattern to copy.
9. **M** `relations.py:328-354` — `_check_roles` calls `_overlaps` with no dates, so an ended
   holder still blocks and the write door hard-refuses *(reproduced: mother link ended 2015
   still blocks)*. Substitute `now()` as `_check_functional` does; raise a question, not a
   refusal.
10. **M** `relations.py:1034-1059` — `_hand_over` ends a standing link at a `start` earlier than
    that link's `created_at`, producing `from None until 2010, created 2026` *(reproduced)*.
    Compare against `valid_from or created_at`; ask when the new start is earlier.
11. **M** perf `relations.py:456-662`, `:1222-1305`, `graph.py:231-252` — one `relate()` loads the
    type's table four to six times; `relations_of(kind=None)` loads every relation class then
    one `facts.about` per hit; `graph.reaches` loads a class per frontier node (section 2.4).
12. **M** `growth.py:63-67` with `authoring._save` and `ontology._keep_spec` — whole-file grown
    override of a preset class bypasses every `GrowthRefused` check (section 2.10).
13. L `relations.py:1388-1398` — `_chain` follows only `nxt[0]`; a transitive `part_of` with two
    wholes drops the second. `:499,504,1452` — `rel["from"]` KeyErrors on a hand-written spec
    without it. `:1159` — `_too_many_handovers` checked on the object side only. `:1437` —
    `and/or` precedence trick. `:424-425`, `:640-653` — dead branches.
14. L `ontology.py:1721-1733` — `_reopen_what_the_world_ended` clears `valid_until` but leaves
    `until_is = BEFORE`. `:2228-2241` — in-place class redefinition returns before
    `_lend_relations`.
15. L `world.py:502-506,976` — `_reading_it_later` is an ad-hoc instance attribute. `:223-261` —
    `find()` sets `self.pending` even when called as a sweep from `selecting.where`.
    `:999-1002` — `save()` always `touch()`es, so an ended link counts as worked with.
16. L `properties.py:75,96` — `spec.get("acyclic")` here, `relations.rule()` at `:77`; a
    `part_of`-nature type is acyclic by nature but not checked.
17. L `tags.py:58-61` — `canonical` replaces `--` once: `"a - b"` → `"a--b"` *(reproduced)*.
18. L `growth.py:97-98` — relation additions `setdefault` silently, unlike attributes.
19. L `questions.py:146-149` — `for_the_user` overloads `answered_by`; `:281-314` — N+1 loads per
    question, run on every run start.
20. L `lookup.py:313-327` — `_personal` checks only Person/AIAgent names although the docstring
    promises "no name from this world".
21. L `restructure.py:462-465,476-478` — re-queries and recomputes per target; `:429,455,490` —
    broad excepts become counters.

### 3.3 Runtime, server, sandbox (`runtime`, `server`, `sandbox`, `session`, `ticks`, `procedures`, `agentfile`, `usage`, `llm`, `prompts`)

1. **H** `runtime.py:1323-1340` — `set_variable` builds `world.pin(name, (expr), desc)` without
   `keep`; `pin` raises when `keep is None`, so the MCP tool always fails *(reproduced)*. Pass
   `keep=True` or add a `keep` argument; no test covers it.
2. **H** `runtime.py:373-375` vs `variables.py:82` — the reserved set holds `owner`/`me` but not
   `user`/`agent`; `world.pin("agent", 5, …, keep=True)` succeeds and shadows the assistant in
   every session *(reproduced)*. `reserved |= ALWAYS`.
3. **H** `runtime.py:440,728-835` — `start_task` calls `finish_task(closing="abandoned")`, but the
   `recording` gate ignores `closing`; when the old task cannot close it stays open with
   `closed_as=None` and its `touched` set and namespace leak into the new task *(reproduced)*.
   Guard the gate with `closing is None and not abandon`.
4. **H** `sandbox.py:246-267` — `MODULES` values (SimpleNamespace, `_Dt`) are shared across
   namespaces; `math.sqrt = 7` in one session is seen in every session and world
   *(reproduced)*. Fresh namespaces per session, or immutable wrappers.
5. **M** `runtime.py:1052-1055,1486-1500` — `_the_world_writes` goes through `run()`, which
   auto-opens an unnamed Task for the world's own reading and never resets that session; its
   `touched` grows for the life of the process *(reproduced)*.
6. **M** `runtime.py:902` — `asked = (…)` instead of `+=`; when any type lacks roles (base worlds
   have one) the summaries assembled above are discarded.
7. **M** `runtime.py:1789-1809,2057-2079` vs `:1837-1890` — the executor keeps running up to
   three statements after a failure, but the echoed block comments them out as "from here on,
   nothing ran" and the hint says the opposite; the host re-sends and duplicates
   *(reproduced)*. Return per-statement outcomes.
8. **M** `runtime.py:289-301` + `timeutil._MOMENT` — `world.now` is process-wide and survives
   `finish_task` *(reproduced)*; a string raises `AttributeError` although the docstring accepts
   a moment.
9. **M** `runtime.py:382-386` — idle expiry deletes the session without `variables.session_ended`
   and without closing its Task.
10. **M** `runtime.py:692-696` with `server.py:214-239` — `finish_task` returns `None` when no task
    is open; the `reset_session` tool then reports "the namespace is clean" with variables still
    bound *(reproduced)*; every result, including "Not closed", is prefixed "Task closed".
11. **M** `procedures.py:137-146` — a stored procedure is bound to the real `World`, not
    `WorldView`; `return world.store.conn` hands back the connection *(reproduced)*. `:70,117-119`
    — strict check drops `import math` from the checked tree but `bind` execs the original text
    without `__import__`; define succeeds, the first call raises *(reproduced)*.
12. **M** `ticks.py` — nothing constructs `Ticks` or calls `tick()`; the module is dead and
    untested. `:77-86` — O(n²) with `known_names` recomputed per pair. `:193` — calls private
    `entity._show_tags()`, which saves the image.
13. **M** `server.py:387-395` — `--blank`/`--specs` with `--db mike` opens a file named `mike` in
    the cwd and never installs the engineer.
14. L `sandbox.py:179-184` — `getattr("{0.__class__}", "format")(x)` bypasses the format guard
    *(reproduced; information leak only)*. `:65-69` — `import math as m` drops the alias
    silently.
15. L `runtime.py:1436,1456` — `_learn_name_choice` runs twice on the failure path. `:532-541` —
    `_facts_hiding_in_prose` loads every entity on every `finish_task`. `:2041` — `_reads_like`
    re-embeds the whole vocabulary (network) per `define` in a block. `describe_classes` calls
    `live_specs()` four times.
16. L `server.py:347` — `hmac.compare_digest` raises on a non-ASCII header (500). On loopback
    `/debug/export` dumps the world to any local process, by design.
17. L `session.py:72` — redundant clause; `:23-25,50` — binds the raw `World` under `world` and
    relies on `runtime.py:390` to overwrite it.
18. L `__init__.py` / `runtime.py:360-361` — for `:memory:` `home` defaults to `Path.cwd()`, so
    test worlds onboard from any `USER.md`/`soul.md` in the cwd.

### 3.4 Formalise, describe, authoring, portraits, inspector, meaning, comments, benchmarks

1. **H** `inspector.py:319-328` — `look_at_types` calls `engineer_of(world)(account)`, but
   `server.py:310` installs `outside.Nemotron(...)`, an `Open` with no `__call__`; the
   `TypeError` is swallowed and `_read_the_new_types` never reads a type in the served world
   *(reproduced; works with `outside.namer(engineer)`)*. `write_the_questions` in the same file
   expects `.json(...)`, the opposite contract.
2. **M** `formalise/write.py:102-117` (`typed_between`, used by `__init__.py:127,145`) — returns
   every current typed link between the two ends, not the ones this reading wrote; a
   pre-existing host link is judged against words about a different fact and counted as `made`,
   so the bare link is ended and the fact is lost. Snapshot link ids before `write.run` and
   diff. Also loads every typed class two to four times per go.
3. **M** `inspector.py:291-299` → `twins()` → `meanings.model.embed` — a network call inside the
   host's 10-second run, once per `define_relation`, despite the comment "nothing that talks to
   the outside happens here"; same in `authoring.define` → `classes_like`.
4. **M** `portraits.py:549-567` — an extra key in an engineer-emitted attribute raises `TypeError`
   in `_attribute_spec`; the bare `except` reads it as "name taken" and the class is silently
   lost. Project to `{name, description, type}` first.
5. **M** `authoring.py:377-477` — `define_relation` has no duplicate check; defining `mentor_of`
   twice overwrites class, cardinality and description silently *(reproduced)*, while `define()`
   refuses a duplicate.
6. **M** `authoring.py:80-104` — a new kind may equal another type's reverse (`founded_by` gets
   reverse `founded`; then kind `founded` gives two types answering to one word; resolution is
   whichever `resolve_kind` finds first) *(reproduced)*.
7. **M** `meaning.py:316-336,220` — every remark is indexed twice (`comment:N` and
   `text:<hash>`); `_holding` filters only `text:`, so an expired remark still answers `like()`
   and every hit appears twice, eating `limit` *(reproduced)*.
8. **M** perf `meaning.like/entities/similar` → `refresh()` walks every class twice and
   `texts.search` rebuilds the texts table; one `like()` rebuilds twice and loads the whole
   world (section 2.4).
9. **M** `benchmarks/run.py:57-95`, `run_blank.py`, `ask_world.py` — none applies
   `hosting.went_wrong`, so an unreachable world counts as a wrong answer; this is the 1 %
   accuracy failure `reask.py`'s comment records. `reask.py:214` — `--specs` is never passed to
   the server.
10. L `comments.py:135-136` — `when` (when the thing happened) is used as the start of the text's
    validity, so a future-dated remark is hidden from `descriptions`/`like()` while `described()`
    shows it; `ttl` runs from `when`, not now.
11. L `formalise/make.py:62-64` — fence stripping handles "```" and "```python" only; "```py"
    leaves `py` as the first token. `check.py:360` — `getattr(value, "date", lambda: value)()`
    for `value.date() if isinstance(value, datetime) else value`. `record.py` — `SCHEMA` lacks
    three columns `_columns` adds; a comment cites `look.A_NEW_WORD_NEEDS`, which no longer
    exists; `keep()` swallows every exception.
12. L `inspector.py:333-334` — `_what_it_offered(...) and []` hides a write behind a boolean.
    `:371` — `(world.extras or {})` and roles set in memory but never saved under `one_door`;
    `name_the_ends` names the ends of the free `Related` type.
13. L `authoring.py:168` — a `parent` that is not a class is silently dropped. `:406-407` —
    rejects `nature="association"` although `AS_WRITTEN` exists for it. `:607` — `_like` runs the
    spelling check on the description, not the name. `define()` prints with `print`.
14. L `portraits.py:266` — `at, _ = best, seen.add(best)`. `sentences.py:131-169` — `held` called
    with no ends lands every type under a misleading heading. `describe.py:596-602,631-632` —
    two contradictory comments; `own` is always `[]`. `:495` — expression for a side effect.
15. L `outside.py:227` — `inspect.stack()` per model call. `:169-171` — `key in asked or asked in
    key` matches almost anything for short option names.
16. L benchmarks — `ASK` copied four times, `commit()` computed four ways, five `main()`s
    (section 2.5). `run_fc.py:51-59` — `port` parameter exists to be deleted; `fumbled` unused.
    `host.py:124` — raises if `message` is a string; `keys()` does not strip quotes.
    `judge.py:229-237` — `declined()` substrings match confident answers.
    `factconsolidation.py:151` — `IndexError` on "12.\tfact".

---

## 4. What to do first

In order; the first four are each under a day and remove a class of bug rather than one bug.

1. **Only `store.transaction` commits.** Remove the 29 module-level `commit()` calls (2.3). Add
   a test: a statement that writes tags and then raises leaves no row.
2. **Fix the four ordering/clock bugs in the record** (3.1.1–3.1.4): tie-break by numeric row,
   `timeutil.now()` everywhere, `rebuild_for` keeps repeats. Add a rebuild-under-`set_now` test.
3. **Stop rebuilding derived tables on read** (2.4): dirty flag per subject for `periods`,
   `texts`, `meanings`; `tags.holding` → `rebuild_for`.
4. **Replace `except Exception: continue` with `except Exception as e: log.debug(...)`** in
   `inspector`, `portraits`, `procedures`, `formalise/record`; then fix what surfaces, starting
   with the engineer contract (3.4.1) and the four runtime highs (3.3.1–3.3.4).
5. **Sessions own their state**: clock, sandbox module namespace, and the current world bound
   per class or via `contextvars` (2.2).
6. **Bring `docs/architecture.md` back to the code** (2.10): one database, `Task` not tickets,
   the 54 modules, whole-file growth, `history.py`'s status. Move inline decision logs to
   `docs/decisions.md` with a pointer.
7. **Split the three god modules** along the seams named in 2.6; make `WorldView` a mechanical
   facade; delete the duplicates in 2.5 and the dead code in 2.11.
8. **One test runner** (`pytest` or a `tests/run_all.py`) so the suite is one command, and tests
   for the eight modules that have none.

---

## 5. Checked against this session's problems (2026-09-30, after `af6c15a`)

The review changed nothing in the repository, and it was written at `9045ab8` — after 22 of the
session's 25 fixes. It cannot have induced any of them. The question worth answering is the other
one: does it *explain* what is still wrong? Each high finding was put to the run it would have hurt
(`var/run8/world`, 455 facts, 318 names, 442 links).

**Live, confirmed on data, and costing us**

- **3.4.1 — `look_at_types` is dead in every served world.** `outside.Nemotron` has `say` and
  `json` and no `__call__`; `ask(account)` raises `TypeError` and the bare `except` eats it.
  `var/run8`: 28 types defined, `looked_at IS NOT NULL` for **0** of them. A whole deferred check
  has never run once. The benchmark number does not depend on it only because the reading was moved
  out into its own phase.
- **3.4.2 — `typed_between` reads every current typed link between the two ends**, not the ones this
  reading wrote, so a pre-existing link is counted as `made`, the bare link is ended and the words
  are lost. `var/run8`: 7 of 402 end-pairs carry two types (`CapitalOf`+`MayorOf`,
  `AuthorOf`+`FamousFor`, `AssociatedWith`+`LocatedIn`, …), so ~2 % of the pairs the reading is
  asked about can misfire this way.
- **2.9 — the silence.** The give-ups are not mysterious once they are read back: of 90 failed
  names, 14 are `X links two entities; got Person and str/list`, 10 are `no 'subject' in the image`,
  9 are `NeedsResolution is not JSON serializable`, 6 a `SyntaxError`. Every one of them is a
  `TypeError`/`AttributeError` that a `log.debug` would have surfaced on the first run.
- **2.4 — derived tables rebuilt on read.** Not a wrong answer, a bill: $4.43 of writing and the
  timeouts that killed two reading phases this week.

**Real, but measured not to have touched the benchmark**

- **3.1.3 — tie-break by string id.** `stated_at` is a microsecond integer (`1790729304472324`);
  across every `facts_*` table in `var/run8` there are **0** ties on `(subject, slot, last_said)`.
  Reachable under `set_now` replay, which the benchmark does not use. It is *not* the 36 % of
  supersessions we miss.
- **3.2.9 — `_check_roles` blocks an ended holder.** No spec in this world declares a role `max` —
  not in `ontology/core/*.json`, not in `var/run8/world/grown/`. The check never fires here.
- **3.4.9 — `went_wrong` not applied.** True of `run.py`, `run_blank.py`, `ask_world.py`; the two
  scripts we measure with, `run_fc.py` and `reask.py`, both apply it (that was the 09-27 fix).
- **3.3.1 `set_variable`, 3.3.2 `pin("agent")`, 3.1.2 repeats wiped, 3.2.7 bare-string tags** — none
  is on the ingestion, reading or question path.

**What the review does not cover**

The 09-29 diagnosis stands: 81 % became 37 % through a one-letter name key on grown classes and an
embedder that was never there. Neither is in this review. Nor are the four live give-up causes
above; two of them (`no 'subject' in the image`, `is read, not assigned`) were fixed after `run8` in
`cadc987`/`af6c15a`, and two are still open.

Order to act, then, is section 4's list with two items promoted: the engineer contract (3.4.1) and
`typed_between` (3.4.2) first, because both lose data silently today.
