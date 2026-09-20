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

## Where they come from

| kind | raised when | closes itself when |
|---|---|---|
| `two_at_once` | a second relation with the same label to the same person, overlapping in time | one of them is ended or removed |
| `maybe_the_same` | something is recorded as new next to one that answers to the same name | — (only an answer settles it) |
| `noticed` | the host called `entity.question(...)` | — |

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
