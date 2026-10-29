# Adapting to the host

The world is used by a language model writing Python against an API it did not design. It will
reach for the obvious word, the obvious shape, the obvious call — and where the world's word is
different, the host pays a statement, a turn, or the user's patience. Most of what looked like
"the model is weak" this month turned out to be the world answering a reasonable question badly.

This is how to find those places and what to do about them. It is a method, not a checklist of
fixes: the fixes go stale, the method does not.

## Read what it did, never what it might do

Every run is recorded (`experiments/results/scenarios/<stamp>/*.jsonl`, and the `runs` table in
any world). The transcript holds the code the host wrote and what came back. Guessing at host
behaviour from the API's shape has been wrong nearly every time; reading ten transcripts has
been right nearly every time.

Two counting rules, both learned by getting them wrong:

- Count **per tool result**, not per text match. A transcript replays context, so a single
  error appears three or four times in the raw text — early counts were inflated threefold.
- Count **what the failure cost**, not how often a message appeared. A message that arrives
  with the answer costs nothing; the same words in an exception used to cost the whole run.

## The question to ask of every failure

**What did the host mean, and could the world have known?** That splits everything into three:

1. **It meant something unambiguous and the world refused.** `Organization.find(full_name=…)`
   when the class calls it `name`; `idea.name` for `idea.title`; `date` where a `datetime` is
   wanted. The world knew. Answer the question that was meant and say what was read as what.
2. **It meant something the world cannot settle.** Two people answer to "Annie"; nothing
   matches. Refuse — and name what would settle it, in words the host can act on: which call,
   which attribute, which date.
3. **It made a mistake the world has no view of.** A wrong year, a reversed sentence with both
   ends the same type, a draft printed instead of sent. Sometimes the world's own data can see
   it anyway (*every other 'dentist' link goes the other way*) — that is consistency with what
   is recorded, which is the world's business. Otherwise leave it: the world does not reason
   about content.

## Fix the word before the message

`.main` was documented correctly and still misread by five hosts out of six, because the word
says "the main one" and the value was a list. A better error message would have been a better
apology, not a fix. When a name invites the wrong reading, change the name — and leave the old
one answering, so whoever learned it is sent to the new one instead of into silence.

The same goes for two words for one place (`comment()` writing into `descriptions`): one word,
one place, no synonyms.

## Silence is the worst answer

An empty list, a `None`, a bare `AttributeError` — these read as facts about the world ("there
is no CloudNine here") when they are facts about the question. Three of the four traps found in
one day were of this kind. A refusal must say what is wrong with the question and name the
nearest thing that would have worked, deterministically (`ontology.did_you_mean`), so the same
mistake gets the same answer twice.

## Know what each channel costs

| channel | what happens |
|---|---|
| `raise` | the statement is undone; everything before it stands |
| `note_hint` | `[hints]`, nothing is lost |
| `note_assumed` | `[assumed]`, nothing is lost |
| holding (`resolution.py`) | the write waits for an answer, and is repeated every run until it comes |

Writes that cannot be applied *yet* are held, not refused — refusing them used to take
unrelated work down with them. Reads that genuinely have nothing to return still raise, and the
message has to be worth the statement it costs.

## A trap is confirmed by recurrence

One host doing something odd is noise. The same shape in three scenarios is a trap, and the
count of discarded statements is the evidence. Rank by that count before fixing anything: the
list from a single pool is a ranked list of frictions and it has never yet matched what we
guessed the priorities were.

## Re-run only where it happened

After a fix, run the scenarios where the failure actually occurred, not the pool. The pool is
for asking "did the whole thing move", which is a different and more expensive question, and it
answers it badly at small n.

## Watch what the fix itself costs

Every accommodation can mislead. Learning which "Annie" was meant taught the world the wrong
Anna twice, because the evidence was read off the host's namespace — where a loop leaves its
last value bound. The rule that came out of it generalises: **the namespace is the host's
scratch paper; evidence is what the world itself did.** Prefer signals the world produced:
what `get()` settled on, what a query returned, what a statement wrote.

And keep the reversal honest. Loosening identification so that any single match without a
contradiction counted as the same entity made a second Robert Wolfe impossible to record; four
suites went red and the change came out again, with the reason written next to the code so the
next person doesn't retry it blind.

## Take the stack before you take a guess

A suite hung one evening. In an hour it got three explanations — the machine is slow, the local
embedding server is queued, the change made this afternoon did it — and each was plausible, each
was said before anything was measured, and each was wrong. The stack, when it was finally taken,
named the line in one second: a commit blocked inside SQLite, because the disk was at 99%.

Worse came first. The suite had been reported failing several times that day and each time the
failure was explained away as the timeout being too short. An explanation that costs nothing to
believe is the one to distrust; a failing check is a fact, and the convenient reading of it is
not.

    faulthandler.dump_traceback_later(30, exit=True)   # before the call that hangs

Two real defects were hiding under the full disk, invisible while there was room: the fixture
committed once per entity (366 writes to the disk for 331 entities) and setting any dated list
rebuilt the period table of the whole world. Neither was the cause of the hang. Both made the
world fragile exactly when it was under load, which is when it matters.

**Three rules out of it.** Take the stack before explaining. Never write off a failing check as
an artefact of how it was run — rerun it alone and read what it says. And when several runs share
one machine, one local model and one disk, the measurement is of the queue, not of the code.

## A link has two ends, and half the checks written in haste forget one

Three defects in one day, all the same shape. `take_in` compared the ends as one unordered set,
so a Thing → Thing link passed a Person → Thing type. `_check_functional` called a link "the same
one said again" on its object alone, so a symmetric relation let a second spouse through. And
earlier, a filter that never looked at direction at all.

A relation is the only thing in this world with two ends, and every check over it has to say
which end it means. When one is written quickly, the second end is what goes missing — and it
goes missing silently, because the check still passes on the cases anyone would try first.

**The rule:** any comparison of two links names both ends explicitly, and says what it does when
the relation is symmetric. If a test can pass with the ends swapped, it is not testing direction.
