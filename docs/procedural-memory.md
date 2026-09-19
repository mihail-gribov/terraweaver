# Procedural memory

The world remembers not only facts but *how it is used*. Code that agents write against the
object model is harvested, generalized and packaged into procedures; the next agent gets a
ready procedure instead of writing it again. Procedures nobody calls any more are forgotten.

Facts are the world's declarative memory. Procedures are its procedural memory. Both are
built by Nemotron; agents only use them.

## Where this sits

The world is served over MCP to any agent (the host). The split of roles is fixed:

- **The host** reasons, answers the user and writes Python against the object model.
- **The world** — Nemotron inside the MCP server — builds and maintains itself: facts
  (`remember`), data from the web (`research`), structure and behaviour (`extend`), and
  procedures learned from use (this document).

Everything here depends on the host–world loop working well first: `describe_world()` tells
the host what exists, `run(code)` executes the host's code in a persistent per-session
namespace. Procedures are harvested from `run`, so that loop is what has to be debugged
before anything below is worth building.

## Why

- **Determinism.** A procedure runs the same way every time. The same suite on unchanged
  code has returned anything from 10/13 to 14/14, and some errors are stable reasoning
  mistakes rather than noise — `status != "applied"` in place of `== "not_applied"` was seen
  four times. Fixed once in a procedure, it stays fixed.
- **Fewer host tokens.** Calling `evening_options(with_=anna, day=saturday)` costs a line;
  writing it costs a script and often a retry.
- **Shared across agents.** A procedure derived from one host's code serves every other host
  connected to the same world.
- **It follows actual use.** The set of procedures drifts with what the user is doing this
  month, instead of being designed up front.

## Lifecycle

### 1. Harvest

A `run` script becomes material for a procedure only if it:

- finished without an error;
- actually consulted the world (`world_queries` / `entity_reads` > 0 — already counted);
- is non-trivial: several steps, not a single `find`.

Stored with it: the code, the bound inputs (entities and literals it used), and its output.

### 2. Generalize (Nemotron)

- literals and bound entities become parameters (`anna` → `person`, "this week" →
  `start, end`);
- a name and a docstring are written;
- placement is decided (see *Placement* below).

### Placement

In v1 the set of classes is fixed; the set of methods is open. A procedure never changes the
schema — it only adds a method, so every procedure is a method and the only question is whose:

- **A class method** when the procedure is about one entity: `person.days_since_contact()`,
  `vacancy.fits(owner)`.
- **A `World` method** when it spans several classes or none: `world.week_agenda(start)`,
  `world.open_applications_with_contacts()`. `World` already holds the built-in `all`, `find`,
  `ensure`, `owner`; learned global functions sit next to them.

The rule is deterministic: if the procedure's main parameter is an entity of one class, it
belongs to that class; otherwise to `World`. Nemotron decides only the borderline cases.

Rules around it:

- A learned method never shadows a built-in one (`find`, `ensure`, `save`, ...) or an
  attribute; registration refuses it.
- `describe_world()` always shows built-in methods; learned ones are shown by usage.
- Learned methods are another layer of the same registry `impls.py` already uses, keyed by
  `(class, method)` — with `("World", name)` for global ones — stored next to the world's DB.

### 3. Candidate, then procedure

A generalized script enters a **candidate pool**, not the world. It is promoted only after
the same pattern recurs 2–3 times with different inputs. One-off scripts never clutter what
the host sees.

Same pattern = same code once constants are abstracted (normalized AST). That is cheap and
deterministic; only borderline pairs go to Nemotron.

### 4. Verify

The host's original run is a free test oracle: the packaged procedure, given the same inputs
against the same world state, must produce the same output. Every recurrence adds another
case. A candidate that disagrees with any of its source runs is not promoted.

### 5. Serve

`describe_world()` lists procedures next to the classes, but only the most used and the most
relevant to the task at hand — the host's context is finite.

### 6. Forget

Each procedure carries a usage score that decays over time (e.g. a call's weight halves over
two weeks). Below a threshold the procedure disappears from what hosts are shown.

It is archived, not deleted: if the pattern comes back, the procedure returns with its tests
instead of being rebuilt from scratch. To the host this is forgetting all the same.

A host calling an archived method is proof it is still needed: the call revives it instead of
failing with `AttributeError`.

### 7. Survive schema changes

Not an issue in v1: the class set is fixed. Once `extend` can change a class, every procedure
depending on it re-runs its tests; broken ones are archived or regenerated.

## Constraints

- **Procedures are read-only.** They come from `run`, which is read-only, and they run under
  the same write guard. A packaged procedure cannot corrupt the world.
- **Deterministic execution.** A procedure's body is fixed code; no model is called when it
  runs.
- **Portable.** Procedures, their tests and usage stats live next to the world's database and
  travel with it.
- **One mechanism with two entry points.** A procedure the host asks for explicitly
  (`extend`) and one learned from use end up the same: code in the world, with tests.

## Risks

- **Packaging a wrong procedure.** Verification only proves the procedure does what the host
  did, not that the host was right. Mitigations: promotion only after independent
  recurrences; a host that calls a procedure and then rewrites the same logic by hand is a
  signal the procedure is off.
- **Over-generalization.** A literal turned into a parameter may have been essential to the
  meaning. Tests from several recurrences with different inputs are what catch this.

## Open questions

- Promotion threshold and decay half-life — to be tuned on real usage, not guessed.
- How many procedures `describe_world()` can show before it hurts more than it helps.
- Whether a host should be told a procedure exists when its code duplicates one — i.e.
  suggest-on-duplicate in the `run` result.

## Measuring it

The same task before and after its procedure exists: host tokens, steps, wall time, and
stability over repeated runs (`experiments/repeat_runs.py`). The existing read scenarios can
be run with exp01 acting as the host to produce the first harvest.

Compare against controls, not only against "no procedures": SkillEvolBench (arXiv:2605.24117)
found that reusing raw past trajectories often beats distilled skills, and that more skills
bring clutter. So the baselines are (a) no memory, (b) the host shown the original harvested
scripts as examples, (c) packaged procedures. Deployment cases should include changed inputs
and composing two procedures, not only replaying the harvested task.
