# An ontology the host writes, and the world keeps honest

## The host already builds one; it just has nowhere to put it

In the FactConsolidation run (455 facts, `benchmarks/README.md`) the host was given a world with
a fixed set of classes and a stream of things that did not fit any of them. It did not give up
and it did not ask. It invented an ontology on the spot, in the only places that would take one:

- **`Idea` became the catch-all** — its own description invites this ("a free-form note… not yet
  structured into its own entity"). Into it went a sport ("American football"), a position
  ("quarterback"), a religion ("Christianity"), a book, and a country ("Israel") that had a
  perfectly good class waiting for it.
- **The predicate became a free `Related` label** — `associated with sport`, `plays position`,
  `author of`, `citizen of`, `educated at`, `affiliated with religion`. That is a vocabulary of
  relation types, written by a host at runtime, one label at a time.
- **What was left became prose** — of the Person slots used, only `full_name`, `descriptions` and
  `notes` appear at all. "Chief executive officer of Microsoft" lives in `descriptions`, as a
  string, on two different people, which is why nothing could supersede it.

Seven of eight losses on that benchmark came from the third of these. The lesson is not that the
host misbehaved — it behaved sensibly with what it had. The lesson is that **the world's
representation is not closed**: there are statements a person can make for which it offers no
home where a value can change, and the host's improvisation lands in places where supersession,
history and time do not apply.

So: let the host author the ontology properly, and let the world do what it is for — keep the
data uniform, and measure.

## The model

**A class is something the host defines.** A name of its choosing, and a description of what
kind of thing it is, given at definition time. The description is not decoration: it is what the
next lookup searches, and a class without one is a dumping ground with a name.

**Attributes are declared, not implied.** Any attribute, any time, with a description of what it
holds. A declared attribute is an ordinary attribute of this world — it has a value that can
change, a validity period, a history, and it supersedes. That single property is the whole point
of the exercise.

**Relation types are defined the same way.** A name, a description, what may stand on each side,
and how many may stand there: one-to-one, one-to-many, many-to-many. A relation type may carry
attributes of its own and be worked with like a class. To the existing characteristics
(`docs/relations.md`) this adds nothing new in kind — it makes them writable at runtime.

Cardinality alone is not enough to make the benchmark's kind of question work. What decides
"who is the CEO *now*" is **functional at a point in time**: at most one holder at any moment,
so a new holder ends the previous one's period rather than sitting beside it. Every definition
must be able to say that, whatever the vocabulary ends up being.

**Discovery before invention.** Before a host invents `job position`, the world should be able to
answer "is there already a class about this?" and "what attributes already exist that mean
roughly this?" — a search over names and descriptions, through the meaning index that is already
there (`meaning.py`). This is the part that decides whether the result is an ontology or a heap,
and it is also how the host-facing guide stops growing: the guide describes the mechanism, and
the vocabulary is looked up rather than listed.

**Uniformity is the world's business, and it is a solved problem here.** This is tags again
(`tags.py`): one canonical form for a name, the spelling kept as given in the record, usage
counted, look-alikes proposed and never merged behind anyone's back, merging done as an ordinary
reversible write when somebody decides. Class and attribute names want exactly that treatment.

**Identity must be declared.** Our identity machinery is per class — name matching, name forms,
honorifics, distinguishing keys. A host-defined class inherits none of it, so a definition says
what identifies one of these things (a key attribute, or a name treated the usual way). Without
that, duplicates breed faster than anything else in the system, and the `maybe_the_same` question
is left to carry a load it was not built for.

**The core classes stay given.** `Person`, `Organization`, `Place` and the rest carry behaviour
that took a long time to get right, and they keep precedence: if a core class fits, it is used,
and the open door is refused for it. The FC run is the evidence — the moment a catch-all existed,
a country went into it.

**Nothing is lost by restructuring later.** The record keeps statements as they were made
(`facts.py`); classes shape the image, not the record. So a class invented loosely today and
promoted to a proper one tomorrow costs a `rebuild()`, and the same statements reassemble into
the better shape. This is the property that makes it safe to let the host improvise at all, and
it is the one thing in this design we did not have to invent.

## What the world guarantees, and what it leaves alone

The world constrains the data and the agreed structures, never the reasoning
(`feedback-world-constrains-data-not-reasoning`). Concretely, it refuses:

- a class or attribute defined without a description;
- an open-class definition for something a core class already covers;
- a write that breaks a declared characteristic — two current holders of a functional relation,
  a cycle in something declared acyclic;
- a value that contradicts what is recorded, in the way it already does — by asking, not by
  overwriting.

It does not refuse: an ugly name, an odd modelling choice, a class that will turn out to be two,
a relation nobody else would have drawn. Those are judgements about meaning, and they belong to
the model and to the person — the world's part is to count them and bring them back as proposals
when the evidence accumulates (`ticks.py`, `properties.py`, `ontology/grown/`).

## Host-facing shape (a sketch, not the signature)

```python
world.classes_like("sport")                  # is there already something for this?
world.attributes_like("language spoken")     # what already exists that means roughly this?

Position = world.define("Position", "a role a player occupies in a team sport",
                        identified_by="name")
Position.attribute("sport", "the sport this position belongs to")

world.define_relation("heads", "the person who currently leads an organisation",
                      subject="Person", object="Organization", one_per="object",
                      functional_in_time=True)
```

Everything after definition is the world as it already is: `ensure`, `relate`, periods, history,
comments, questions, tags, meaning.

## What we are actually going to find out

The reason to build this is not only the thirty-five points on a benchmark. It is the question
underneath: **given room, what structure does a host build?** Nobody knows, and the answer is
worth more than the score. What gets measured on the first run:

- how many classes it defines for 455 facts, and how many are the same idea twice;
- whether it looks before it invents, once looking is possible;
- whether the vocabulary converges — the tenth batch reusing what the second one defined — or
  keeps branching;
- what it declares functional, and whether supersession then works (the direct before/after on
  the identical 20-question slice, where seven of eight losses are supersession);
- what it does with the core classes once it can make its own — the precedence rule tested, not
  assumed.

## Order of work

1. The open class: definition with a description, declared attributes, the identifying attribute,
   precedence over the core set, usage counted. Measure on the identical FC slice.
2. Discovery: `classes_like` / `attributes_like` over descriptions. Measure again — this is the
   difference between an ontology and a heap, and it should show as reuse, not as accuracy.
3. Host-defined relation types with characteristics. The bigger half, and the one that carries
   the checks.
4. Promotion: a loosely defined class that recurs becomes a grown class in `ontology/grown/`,
   with its evidence. The trigger and the evidence exist; the middle does not.

Measure between each. The point of this document is not that the design is right — it is that
the design is testable, and the first test is already written.
