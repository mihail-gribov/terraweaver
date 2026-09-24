# The inspector

Designed and built 2026-09-24 (`terraweaver/inspector.py`, readers in `terraweaver/outside.py`,
run by `experiments/inspect_links.py`). Links only for now — the shape is meant to take
everything the world creates, and that is written at the end.

## Why

The world checks what it can check against its own record: the run of a type, a cycle, a second
holder where one is allowed. What it cannot check is whether a link says what somebody meant. A
`capital_of` written from the country instead of the city is a wrong fact and reads as a
perfectly ordinary row — worse than a missing one, because the world then asserts that Great
Britain is London's capital.

Measured: once the links that never landed were fixed, a backwards link was the commonest wrong
fact left standing — three of six flags in a hundred-fact run, and thirteen found across a
hundred and fifteen links once the inspector could see them.

## Semantic, not substantive

The distinction the whole thing rests on, and the user's words for it:

- **Semantic** — *can this be so at all*. Is each end the kind of thing that belongs at that end?
  "Rome capital of Japan" is well formed and false. "Japan capital of Rome" is malformed. Only
  the second is the world's business.
- **Substantive** — *is it so*. Not the inspector's business and must not become it. The world
  holds what the person said; a benchmark of it holds deliberate absurdities on purpose; and a
  capital really does get moved. What an outside reader makes of the truth of a fact is kept as
  a remark and is never grounds for anything.

Measured, this is not a nicety. Asked whether links agreed with common knowledge, a reader
flagged seventeen of a hundred and fifteen — and the list was almost exactly the benchmark's
superseding pairs, the facts it exists to keep. A reader allowed to act on that would throw away
precisely what it was built to hold.

## Three kinds of check

    on     how             what
    type   deterministic   twin_type             two types read as one idea
    type   deterministic   ends_named            the type never said what its two ends are
    type   open            ends_could_be         what each end is, in checkable words
    type   open            name_says_direction   the word does not say which end starts
    link   deterministic   against_the_run       this link runs against the rest of its type
    link   closed          ends_fit_their_roles  is each end the kind of thing that belongs

**Deterministic** is worked out from the world's own record: free, certain, and the only kind
that may ever correct anything by itself.

**Closed** is one question with named options to an outside reader — cheap, calibrated, and
where the volume is: one per link.

**Open** is where a word has to be invented: expensive, so once per type and never per link.

The user's rule behind the split: *there are two ways of getting intelligence, open questions and
closed ones, and two tools, and both must be used, because a closed question is an order of
magnitude cheaper.* On a hundred-fact world that came to 26 open questions against 115 closed
ones.

## How the question is put decides the answer

The same judgement, asked four ways over the same links:

    a plain English sentence       5/5 on a picked set — but rejects the deliberate falsehoods
    "can this be so at all"        9/12 — keeps them, misses reversals
    "which of A or B"              7/12 — and inverts correct links at p=0.93
    the ends named, four yes/nos   12/14 — and every miss an abstention

The last is the one, and what makes it work is **naming the two ends**. Told only a type's name
and description, a reader guesses, and guesses confidently — which is the dangerous kind of
wrong, because acting on it corrupts a correct link. Told what each end is supposed to be, it
answers or abstains.

With `roles` empty the inspector found nothing at all in 115 links. With the ends named
(26 open questions) and the links judged (115 closed ones), it found 13 written backwards —
including all three the checker knew about — and left 90 alone.

So the recorder is **asked** for `subject_is` / `object_is`, not made to give them:
`define_relation` without them says what cannot be checked and hands back the call to write, and
the close adds one line and closes anyway. A type without named ends works perfectly well. It is
only the checking that cannot be done, and that is worth a line rather than a wall.

## Once per thing, and where each check runs

A link is read **once**. The mark is over the link's own content, so a link whose end has moved
is read again and one nobody has touched is not (`link_checks`, keyed by a digest of what was
read). Types are marked the same way (`type_checks`).

Timing decides where a check runs, and it is not a detail:

- A host's run is stopped after ten seconds.
- A naming answer comes back in four or five seconds; one in several takes twenty.

So nothing that waits on a reader may be called from inside a run, or the run dies of the check.
What the world can do for free it does the moment a type is defined — while the host is still
holding the pen, where a correction is one more argument on the call being made. The reader runs
at the close, where nothing is waiting, with `TTL = 10` seconds; whatever it does not answer in
time is left marked unread for a later pass. Online where it keeps up, deferred with a mark
where it does not.

`can_ask=False` is for a pass with nobody there — a sweep over an old world, a nightly run. The
finding is written down either way, so the same link is not read twice; it simply is not put to
an agent that is not listening. A question nobody is there for is not caution, it is a queue.

## What it does with what it finds

**All is well — nothing is said.** The agent does not need to hear that a check passed.

**Changed, and certain — said.** One check may act: a link that is the only one of its type
going one way against five or more going the other is turned round, a remark on it records that
the world did it and why, and the close tells the agent what was turned. It is allowed to
because it is deterministic — counted from the world's own links, not read from outside — and
because it is held to the narrow case. Five against one: at two or three the majority is not a
majority, and it is at two or three that a type is young, which is where every reversal in the
measured run was written.

A fact that turned round while nobody was looking is a fact the agent can no longer account
for. That is the whole reason for saying it, and for saying it with the sentence it was: the
agent has what the person said and the world only has a count.

**Unclear — asked, with the options named.** A verdict becomes a question on the link, which is
how everything uncertain in this world is kept: it outlives the run, it is asked once, and
answering it closes it. Nothing an outside reader says is ever applied — it is one more account
of the fact, and the person's own account outranks it.

Renaming and merging are offered, never done. `twins` reports two types that read as one idea;
`world.take_in(<the type>, "<the word>")` is what moves the links across once somebody decides.
A clearer name is offered the same way: define the clearer word and take the links in, which
leaves the record saying what it always said. Nothing is renamed in place, because a word whose
meaning can be changed afterwards makes every statement written under it unreadable in the way
it was written.

## A class is a class

There was a version of this that looked only at the types a world had grown for itself, on the
grounds that what the world ships with is not the host's to fix. That is not a distinction the
world has, and drawing it was wrong: a type whose ends are not named cannot have its links
checked, and it makes no difference who wrote it. `PartOf` came back "part" and "whole", which
is right and useful; `Related` came back "entity" and "entity", which is vacuous and harmless.

Where an answer is worth keeping it goes *beside* the core file, never into it — which is what
`growth` is for and has always been for: the core is read as it is and never written to, and
additions live next to it and are merged in on the way.

## Known wrong

A role written too narrowly turns into a false alarm. A reader called `affiliated_with` an
organisation-to-organisation link, so "Princess Alice affiliated with Anglicanism" came back
impossible. The link is fine; the role is too tight. That the verdict is kept as a question and
never applied is the reason this costs a question rather than a fact.

The deterministic majority rule is wrong where a type has only two or three links and no
majority exists yet — which is exactly where today's reversals were written. It is weak there,
never confidently wrong, and that difference is why it is the one allowed to correct.

## Later: everything else the world creates

The shape here is not about links. A thing created, a class defined, an attribute declared, a
description written — each is something the world could hand to the same checklist, with the
same three kinds of check and the same rule about what may be acted on. That is where this is
meant to go. Links first, because that is where the wrong facts are.
