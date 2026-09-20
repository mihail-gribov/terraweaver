# Open questions

The world is written from conversation, and conversation leaves loose ends. A user says "from
October my dentist is Dr. Patel instead of Dr. Rao" and the host records Patel but never ends
Rao — now there are two current dentists. A host asks which Olga was meant, doesn't wait for the
answer, and records a second one.

Three ways to treat that, and only one of them is right:

- **refuse the write.** Wrong: the user said it, and their life is not the world's to correct.
  The world refuses only what is formally impossible (two mothers, a cycle of authority).
- **decide it.** Worse. Which Olga was meant is not the world's to decide, and never was.
- **take it, and remember what doesn't add up.** This.

A question is attached to the entity it's about and outlives the run that raised it. That last
part is the point: a hint is read once, by one host, in one run, and s20 showed exactly what
happens then — the host read "Michael already has a dentist for that time", answered the user
correctly, and left the world wrong. A question comes back every time anyone works with Michael.

## There is always one reading

A question that leaves the world ambiguous would be worse than no question at all: the host asks
"who is my dentist", gets two, and either picks one silently or hands the mess to the user. So
every open question carries the reading that holds while it is open, and that reading is a
**rule** — the same for every host, at every hour, without anyone deciding:

| kind | the rule while it is open |
|---|---|
| `two_at_once` | **the later statement counts.** Lists come newest-first, so the first one is the one that counts |
| `maybe_the_same` | **they stay two records.** Nothing is merged without an answer; a lookup returns the one it matched |
| `noticed` | **the latest value recorded stands** — which is how attributes already work |

Recency decides, except for identity, where recency would quietly merge two people. `q.assumption`
says it in words and `q.line()` prints the question with it, so a host can always answer — by the
standing reading, saying which it is: "as recorded, Nina from October 1".

## Who can answer

Not every doubt is the user's to settle, and the world shouldn't spend their attention on the
ones that aren't. Three things can close a question, and they are not interchangeable:

- **a rule of the world** — the doubt stopped holding, or normalisation decided it. Closes
  itself, nobody is asked.
- **the user, through the host** — whose life this is. Anything about who someone is, what they
  meant, what they want. `q.answer("Nina replaces Rao")`.
- **an accepted norm or a source that can be checked** — a company's registered name, a domain,
  a city, the standard form of a title. `q.answer("Acme Corp Ltd", by="companies-house.gov.uk")`.
  What settled it is kept with the answer, so a later reader can weigh it.

The world may ask the host to check something with the user; it may equally settle a matter of
form from a reliable source instead of asking. Reaching those sources is the deferred work in
`docs/ideas-research.md`; the record keeps room for it now so it isn't bolted on later.

## Three moments to ask, and only three

A question is worth nothing if it is raised at the wrong time. Interrupting a task to ask about a
dentist is worse than answering by the rule and asking later.

1. **The read depends on it.** `[ask first]` in the result, at the moment the host holds the
   answer. Only then — a doubt about an entity a run merely touches stays quiet, because
   repeating it on every contact is noise, and the criterion in the literature is relevance to
   the answer at hand (query-driven repair, `docs/related-work.md`). Raised when a run reads the relation, the attribute or the identity a question hangs
   over — not for any other read of that entity. Ask before answering, or answer by the standing
   reading and say which it is.
2. **The task is over.** `world.questions(here=True)` is what this task actually worked with —
   both ends of every relation it wrote, not only what it changed. `reset_session` returns the
   same list, because a host starting a new task is a host that just finished one: the user is
   there and nothing is in flight. "Two things I'd like to check with you."
3. **The user offers.** `world.questions()` is everything open, ordered by how often the entity
   is worked with (`usage.py`) — the person asked about every week comes before the one met once
   at a conference. The doubt that never comes up never gets asked, and that is correct.

## What the host sees

    [open questions] Michael: two dentists at once: Arun Rao and Nina Patel. Did the new one
    replace the old one? [Nina Patel replaces them — end the old one / both stand]
    — put them to the user if they're here; entity.questions() to answer or drop them

Nothing is blocked. The line says there is something the user could settle, and the host raises
it when the user is around — not in the middle of a task the user is waiting on.

    for q in owner.questions():
        print(q.text, q.options)
    q.answer("Nina replaces Rao")     # closes it; recording what follows is the host's job
    q.drop("asked — it's a different Olga")
    anna.question("two numbers on file, which is current?")   # one the host noticed
    world.questions()                 # everything open, across the world

Most of this is a known mechanism under another name — inconsistency-tolerant query answering,
prioritized repairing, deferred entity resolution, truth maintenance. `docs/related-work.md` maps
each piece to its established name and to what that literature does better than we do.

## Where they come from

| kind | raised when | hangs over | closes itself when |
|---|---|---|---|
| `two_at_once` | a second relation with the same label to the same person, overlapping in time | that relation kind | one of them is ended or removed |
| `maybe_the_same` | something is recorded as new next to one that answers to the same name | identity — every lookup that picks it out | — (only an answer settles it) |
| `noticed` | the host called `entity.question(..., about="phone")` | that attribute or relation | — |

Two rules keep the list from becoming noise:

- **a question that has become moot closes itself.** Each kind knows how to re-check its own
  reason, and the check runs when the list is read. End Rao's relation and the question is gone,
  closed as `settled_itself` — nobody had to answer it.
- **an answered question is never raised again.** The answer is kept with it, so the same doubt
  about the same entities doesn't come back.

## What this does not do

It does not verify that the host actually asked the user — the world never sees the conversation.
That gap is real and known (`docs/TODO.md`): `world.settle(needs, new=True)` can be called by a
host that asked nobody. What the world can do is refuse to forget: the second Olga stands, and
the doubt about her stands with her until someone answers it.
