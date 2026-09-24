# What a relation type carries

A working document, started 2026-09-24. Part one is what is there now, read out of the code and
the thirty-eight types two worlds hold. Part two is what we found wrong with it. Part three is
where new properties go, with what each one would settle of the existing ones — because the
thing this document exists to prevent is a second way of saying something already said.

## The rule this is written against

**Two statements of one thing is how supersession was lost.** That is in `BY_NATURE`'s own
comment, and it has been earned twice more since: a nature that repeats what cardinality says,
an `over_time` that overwrites the cardinality it sits beside. Any property added below has to
say what it settles and what it must therefore not repeat.

## Part one — what is there now

Counted across the 38 relation types in `ontology/core/` and one recorded world.

### Said by whoever defines the type

| property | in | what it is |
|---|---|---|
| `kind` | 38 | the word a link of this type is written with — `capital_of`, `authority` |
| `nature` | 38 | one of five: `related_to`, `part_of`, `kind_of`, `same_as`, `derived_from` |
| `from` / `to` | 38 | the classes at each end. `any` in every grown type |
| `roles` | 32 | what each end **is** — "a city that serves as a capital" / "the country" |
| `labels` | 38 | words this link is called in speech. Empty in every grown type |
| `reverse` | 34 | the word for reading it from the far end — `managed_by` |
| `reads` | 38 | how it reads as a sentence. A template in every grown type |
| `example` | 38 | how it is written. A template in every grown type |
| `notes` | 1 | an aside about how it is usually recorded |

### Worked out from cardinality and `over_time`

| property | in | what it is |
|---|---|---|
| `functional` | 29 | one object per subject: `False`, `True` (corrects), `at_any_time` (hands over) |
| `inverse_functional` | 28 | the same for the other end |

### Algebra, declared per type

| property | in | what the world does with it |
|---|---|---|
| `transitive` | 2 | a read follows the chain to its end (`relations.py:1453`) |
| `symmetric` | 3 | writing one side writes the other; used in seven places |
| `acyclic` | 3 | a cycle is refused |
| `irreflexive` | 7 | a thing cannot stand in it to itself |
| `asymmetric` | 7 | declared and read nowhere |

### Machinery

| property | in | what it is |
|---|---|---|
| `free` | 1 | the untyped link (`Related`), before any type exists |
| `one_of_a_label` | 2 | one holder per label, not per type |
| `transitive_via` | 1 | another type's chain extends this one |
| `same_class` | 1 | both ends must be of one class |
| `compose` | 1 | how two of them combine |

## Part two — what is wrong with it

**`over_time` overwrites the cardinality beside it.** All four cardinalities with
`over_time=True` produce the same thing:

    one-to-one    True  ->  at_any_time / at_any_time
    one-to-many   True  ->  at_any_time / at_any_time
    many-to-one   True  ->  at_any_time / at_any_time
    many-to-many  True  ->  at_any_time / at_any_time

So `over_time` carries two claims at once: **one at a time** — which is a claim about how many,
and therefore cardinality — and **the displaced one ended rather than was wrong**, which is a
separate question nothing else asks.

**Cardinality cannot say "one at a time".** `one-to-many` means one *ever*. An employer is one
*now* and many over a life, and there is no word for that — which is why `over_time=True` was
made to mean it, and why it had to override everything to do so.

**The second question only applies to one of the three.** "Did the displaced one end, or was it
wrong?" is meaningless where many are allowed, and settled by construction where one is allowed
ever — a birthplace cannot have ended. It is a real question only for "one at a time". It is
currently asked of every type, which is one reason it is answered badly: `FamousFor` was
declared accumulating, and the fault was not `over_time` at all but choosing "many" where the
facts meant "one ever".

**`part_of` and `kind_of` are physically identical** — transitive, acyclic, irreflexive, and the
world follows both chains the same way. What would part them is inheritance: under
classification what holds of the object holds of the subject, under containment nothing does
but position. Neither is implemented, so today they are one nature under two words.

**A template reads as content.** Every grown type has `reads`, `example` and `reverse` filled in
by pattern — "a capital of b — whichever end you start from is the subject", `capital_of_of`.
Handed to a reader as though it said something, it produced confident wrong answers. An empty
field would have been skipped; a filled one was taken as an instruction.

**Measured, the properties that carry checkability are the empty ones.** `roles` empty in all 26
grown types, `from`/`to` `any` in all 26, `labels` empty in all 26. With `roles` empty an outside
reader found nothing in 115 links; with them named it found 13 written backwards.

## Part three — new properties

Each entry says what it settles, and what it therefore replaces. Nothing goes here that another
property already says.

### Proposed: cardinality gains a temporal reading

    one ever        at most one, for good — a birthplace. A second telling is a correction.
    one at a time   one now, many over time — an employer. A second telling is a change,
                    unless somebody says it was a mistake.
    many            no limit. Nothing supersedes anything.

**Settles:** `functional` / `inverse_functional` entirely, including the `at_any_time` case
that `over_time` was carrying.

**Replaces:** the "one at a time" half of `over_time`.

**Leaves:** the other half — *ended, or was wrong* — which becomes a question asked only of
"one at a time", and only when a second telling actually arrives, because that is where it is
answerable and nowhere else.

### Open, not yet proposed

- **What may be inferred**, which is what is left of `nature` once cardinality and time are
  taken out of it: `identity` (what holds of one holds of the other), `derivation` (staleness
  runs from the basis), `classification` (properties inherit down the chain), `containment`
  (position inherits, properties do not). Two of the four are not implemented.
- **Whether a template is worse than a blank** for `reads`, `example`, `reverse` — measured as a
  cause of wrong answers, unmeasured as a fix.
