# 02 — which way round, asked the way the world asks it

**The question.** A link joins two things and the account says which way it goes. Can a closed model
tell a link written the right way round from one written backwards — put to it as the world now puts
it, and answered well enough to act on?

**Why it is asked again.** Jev was measured on this on 2026-09-24 and deliberately left unwired.
Three ways of asking, over the links of `fixed100`:

    plain English sentence      5/5 on a picked set, but it rejects the benchmark's deliberate
                                falsehoods and mangles any `_by` / `_language` type name
    "can this be so at all"     9/12 — keeps absurd-but-possible 4/4, catches impossible 1/1,
                                catches reversed 1/4
    "which of A / B"            7/12 — catches some reversals and confidently inverts others

What decided it was not the average but **the shape of the errors**: the wrong calls came with
p=0.93 (`Starship Troopers author Robert A. Heinlein`, judged right way round) and p=0.89. A
confidently wrong verdict corrupts a correct link, which is worse than the error it was meant to
catch. The world's own majority rule was kept instead — weak, but never confidently wrong.

**What changed on 2026-09-27**, and why the measurement is worth repeating. The question is no longer
"is this true", "can this be so" or "which of these two". The world renders what it is about to hold
as a phrase and puts it beside the account:

    The record is about to hold this: «Chang'an capital of Tang Empire».
    Is that the same thing the account says?
        says_so    yes — the account says capital of, and this way round, or it does not say
                   which way round and this one is not against it
        backwards  the account says the other way round: «Tang Empire capital of Chang'an»
        not_in_it  the account is about something else

Nobody has been measured on *that*. And the question is built here by `check._asking` — the same
function the live reading calls — so what is measured is the question the world really asks.

## What it runs against

A world some run already wrote, kept by `--keep`: `world.db` and `grown/` side by side. Nothing is
written; this only reads and asks. Graded against `experiments/expected/*.json`, which says per fact
which entity was the subject and which the object — written down once and corrected by hand, so the
verdict is compared with the direction the **sentence** had and not with the world's opinion of
itself.

Both parties are asked the same question at the same moment: **Jev** (`TYPESAFE_API_KEY`) and
**the engineer answering a closed question** (`outside.AsChoices` over Nemotron), which is what the
live reading falls back to when no picker is configured, and therefore the standing arrangement.

## Running it

    scripts/measure.sh direction var/gate-noread          as a service, with a log
    .venv/bin/python experiments/02_link_direction/run.py var/gate-noread --limit 60

`.env` is read by `benchmarks/host.py`, not by `terraweaver`, so run it through the script or export
the keys yourself.

## What it settles

Per picker, two numbers and only two matter:

1. **How often it is right** on the direction the sentence gave.
2. **How sure it is when it is wrong.** This is the one that decides. A picker wrong at a low
   confidence can be wired behind a threshold — `check.SURE_ENOUGH` is 0.6 and the doubt goes to the
   line, not against it. A picker wrong at 0.93 cannot be wired at all, at any threshold, because
   there is no confidence at which its wrong answers are rarer than its right ones.

A third thing worth reading off the same run: whether the two pickers are wrong about the *same*
links. If they are not, neither is measuring the question — they are each measuring themselves.
