# TODO

Ordered by what currently blocks progress. The focus is reading the world; write tasks are
deliberately parked (see below).

## Two instances in every world: `user` and `agent`

Every world should hold two explicit instances: `user` — the person the world belongs to and
the host talks with — and `agent` — the assistant itself. Today the fixture has `owner` (a
Person) and `me` (an Agent persona); decide whether `user` / `agent` replace them or sit next
to them, and make them present in every world, not only in `job_search`.

## Debug the host–world loop

The world is served over MCP; the host agent writes code against the object model through
`describe_world()` and `run(code)`. Everything else — procedural memory
(`docs/procedural-memory.md`), `remember`, `research`, `extend` — builds on this loop, so it
comes first.

## A scenario needs its own world, not the fixture underneath

`scenarios/run.py` starts every scenario's server with `--rebuild`, which loads `job_search`, and
then runs the scenario's SETUP on top. For the small scenarios that is a feature — there is
already a world to work in. For a scenario about something specific (s26, keeping a move
together) it means the checks keep tripping over entities nobody in the story ever mentioned: a
Job search project, an Anna Peterson, a dozen events.

What it wants: a scenario that says `FIXTURE = None` (or names its own), so SETUP builds the only
world there is. Small change to the runner, and it makes the scenarios that come next honest.

## Structuring what was written as prose

A remark is what the host writes when the class has no place for something — "allergic to
peanuts", "her son started school", "prefers mornings". The world should read those, notice when
the same *sort* of fact keeps coming back, and propose the attribute that is missing; then the
remarks can be read into it instead of sitting as prose.

The obvious way does not work, and it was measured rather than assumed: clustering short remarks
by embedding similarity. In bge-m3, remarks on one topic sit 0.46–0.61 apart while remarks on
different topics sit at 0.49 — no threshold separates them, and a schema proposal built on that
would be noise. Embeddings stay where they are good: retrieval, and finding what is plainly the
same thing said twice (`ticks.py`, *said-twice*).

What should do it instead: **the model names the kind** of each remark — "dietary", "family",
"work", "preference" — once per remark, kept with it like any judgement, with its basis. Then
counting kinds is arithmetic, and a kind that recurs across enough people is an attribute
proposal with real evidence behind it. That is the agenda's work, and it wants the judgement
layer (`facts.conclude`) rather than a new mechanism.

## Research for one thing: "find out more about this"

The person says "I'm interested in a BMW X5, 2026". The world records the thing and then goes and
fills it in — specifications, prices, what people say about it — so that by the time they come
back to it there is something to talk about. `entity.research()`, roughly.

The shape it should take, from what is already decided elsewhere:

- **a ticket, not a call.** Expensive, several pages, background, one at a time, on a budget; it
  does not happen in the middle of answering someone.
- **what it finds are statements**, each with the page it came from as its source — so they are
  checkable, outranked by the person's own word, and retractable one by one if a source turns
  out to be rubbish. Where it summarises rather than copies, that is a conclusion with its basis
  (`facts.conclude`), and it goes stale like any other.
- **only where it is allowed** (`lookup.py`): a public thing — a car model, a company, a place —
  or anything at all if the person asked for it about that thing. Never a person from this world,
  and never a query carrying what they told us.
- **it has an "as of".** Prices and reviews age; the entity should say when it was looked into,
  and the tick should notice when that was long ago.

Open: whether a researched thing is an ordinary entity of an ordinary class (a `Product` we do
not have yet) or something looser, and how much of a page is worth keeping versus fetching again.

## Giving a new link its rules: the parts not built

The chain is described in `docs/architecture.md`. What exists: the trigger (`ticks.py`,
*loose-links* — a `related` label used three times or more) and the evidence
(`properties.py` — what the links have ever done, and which declared rules the data breaks).
What is missing is the middle: a ticket that asks whether the type already exists, brings the
model's general knowledge to bear on its properties, checks that setting them breaks nothing,
and writes `ontology/grown/`. That is the agenda's first real job.

## A change that happened in the past can't be backdated

`person.organization = new_place` ends the old membership *now* and opens the new one *now*. When
the user says "she moved to Halden in July", there is no way to say so through the derived
setter: the world records today. Seen in s24, where the answer correctly read "the change is
recorded as ending today" — which is true and wrong at once.

What it needs: the period to travel with the assignment (`person.set("organization", place,
starts=date(...))`, or the same through `relate`), and `history("organization")` to read from the
statements rather than from when the write happened.

## Judgements: the parts not built yet

The layer itself works — `facts.conclude(...)` with a basis, staleness when the basis moves,
`entity.why(attr)` handing the host the judgement and what it rests on. What is missing:

- **the forms**: `ontology/judgements/` — what a judgement is *about*, what it is drawn from,
  what fields it has, and what work produces it. The third structure of classes
  (`docs/architecture.md`), still only described.
- **the machinery**: what to re-derive, when, on what budget. This is work for the agenda: one
  expensive job at a time, ordered by who is actually asked about.
- **"why do you think that" reaching the ticket.** Today the answer is the judgement plus its
  basis, handed to the host to put into a sentence. Once work is organised into tickets, the
  run that made it names the ticket that ordered it — `run_id` already carries it — and the
  answer can include what the world was trying to work out, not only what it read.

## Onboarding: what belongs in it beyond the two parties

`terraweaver/onboarding.py` is the named step that brings a world up from the files beside it.
It runs on every open, not once. Today it reads `USER.md` / `soul.md` into the two parties
(`selves.py`) and nothing else. What belongs there:

- class additions and procedures from `AGENT.md` (the parked sketch below);
- the first conversation — a world with nothing in it asking for the few things that make the
  rest useful, rather than waiting to be told;
- importing what already exists (contacts, a calendar) as statements from those sources.

## Parked: AGENT.md as the person's own growth

`terraweaver/agentfile.py` parses class additions and procedures out of an AGENT.md — the same
two upper levels the world grows for itself, written by hand instead. Written as a sketch, not
wired in: the write path comes first. (`USER.md` and `soul.md` are live — see `selves.py`.)

## From the literature review (docs/related-work.md), in order

1. **A check before the commit.** 20–26% of runs come back as errors and are rolled back whole;
   each is a fork where two attempts of the same task diverge. SWE-agent's ablations put +3pp on
   exactly this: validate the write, report the violation, don't let the run die on line one.
   Savepoints — keeping the good statements of a run that failed late — belong in the same
   discussion, against the atomicity rule set deliberately.
2. **A proposed `same_as` instead of a duplicate.** When an agent answers its own identity
   question, record a link with provenance "agent", ranked below a user-confirmed one, rather
   than a second person. Merge is a derived artifact, never a destructive edit: keep the source
   records, keep the link table, compute the survivor — then un-merging is deleting a link.
3. **Rank doubts by what the answer changes**, not by how often the entity is touched:
   P(it flips an answer) × consequence × future reads − cost of asking. Access count is only the
   third factor.
4. **Report pass^k** (done for the runner) and audit our own EXPECT blocks the way the Agentic
   Benchmark Checklist says to — a check that reads a question object rather than a result fails
   for the wrong reason, which has already happened here once.

## A hint the host ignores, a question the host answers itself

Partly addressed: contradictions are now kept as open questions on the entity
(`docs/questions.md`), so a doubt outlives the run that noticed it and comes back every time
anyone works with that entity. What is still open is below.

Two failures from the same run, both host behaviour that the world can see but not prevent:

- s20: the world hinted "Michael already has a dentist for that time: Arun Rao — both stand
  unless you end one". The host read it, answered the user correctly ("Arun Rao through
  September 30"), and never ended the relation. The answer was right, the world was wrong.
- s19: `Person.get(full_name="Olga")` came back as a NeedsResolution; the host swallowed it in a
  bare `except`, called `world.settle(needs, new=True)` on its own, and created a second Olga —
  exactly what the guide forbids ("never answer it yourself — not even with new=True").

The rule of this project is to enforce in code, not in the prompt, and neither of these is
enforced today. A question keeps the doubt alive (s20's two dentists, s19's second Olga), but it
still doesn't make the host act. Open: whether `settle(..., new=True)` can require the user's
answer at all — the world never sees the conversation, so it can't be verified from inside — and
whether an open question should reach the user another way than through the host that ignored it.

## Direction of relations, measured

Hosts wrote relations backwards — `owner.relate(nina, "service", label="dentist")` for "my
dentist is Nina". The answer so far is convention, not a new API: one rule stated once (the
subject is the one the label describes), an example per relation type in the world description
showing the sentence it makes, and every result printing a relation as that sentence. If runs
still come out reversed, the fallback is a role-first call — `nina.relate_as("dentist",
of=owner)` and `owner.who("dentist")` — where direction can't be got wrong because it isn't
expressed.

## Close the `Preference` gap

A fact is stored as `predicate` + free-text `value` — "wants" / "зарплату от 150000". Nothing
records what a fact is *about*, so "чего я хотел от работы" can only be answered by matching
keywords against free text, which is where `read_owner_wants` goes wrong: the agent decided
`wants_remote: False` while the world says the opposite.

This is the same gap `Event.kind` had, and the same fix applies — record the thing that gets
asked about instead of leaving it to be inferred.

## Make a misused `FindResult` fail loudly

`FindResult` is list-like, so passing the whole result where an entity is expected —
`Person.find(organization=Organization.find(name="TechCorp"))`, forgetting `.main[0]` — doesn't
raise. It silently matches nothing, and an empty result reads as "there are none". A wrong
answer delivered confidently is worse than an error.

## Detect emulating scripts

A scenario check trusts that the agent's script did the real work. It doesn't have to:

- hardcoding the expected answer — `report("hello-terraweaver")` passed the `machine_echo`
  check after the `Machine` class had been removed entirely;
- computing the answer with plain Python while bypassing the world model;
- reporting a plausible constant instead of deriving the value.

The world now counts what a script actually touched (`world_queries`, `world_writes`,
`entity_reads`), and exp01 refuses an answer from a script that consulted nothing. That closes
the blunt case. Still open: a script that touches the world *and* reports something unrelated.

Ideas: check that the reported value derives from what was read; run a scenario against a
deliberately altered world and require the answer to change — an emulating script gives the
same answer either way.

## Parked: the write path

`link_person_org` fails 0/3. Told to record a new person, the agent searches with `find`,
doesn't find them, and reports "not found" rather than creating them with `ensure`. Parked by
choice while the focus is on reading — not because it's understood.

Related: creating an entity still bypasses the consistency layer entirely. `Person(...)`
direct construction is allowed, so deduplication can be avoided at creation the same way it
used to be avoidable on attribute writes.

## A design pool: scenarios that guard the ideas, not the model

The unit suites check that a mechanism is arithmetic. They cannot check that it earns its place.
A design scenario does: the task is what a person would actually say, nothing in it explains how
to store anything, and the mechanism is the only cheap way to get the answers right. If the
mechanism rots — or stops being reachable from the host's side, which has happened twice — every
probe in its scenario goes wrong at once. Run them as their own pool: `--level design`.

Written: `s27_standing_things` (cyclic periods).

Wanted, one per idea we've committed to:
- tags with periods — something true for a season, asked about after the season
- `where` with no class — a question about a thing that is not one kind of thing (s26 is a draft
  of this; it needs its own fixture instead of the job-search one)
- the two-stage record — "those were two different people after all", and nothing is lost
- questions — a contradiction taken, remembered, and raised when the entity is next touched
- direction — a relation written from the wrong end, and the world saying so
- identity — a name that is a form of another name, merged; a namesake, not merged

## Known limits of repeats

- No weekday rule: "every weekday" has no form here. `every="week"` anchored on a Tuesday is the
  way to say "every Tuesday"; five rules is the way to say "every weekday", which is silly.
  Whether to grow the vocabulary (RFC 5545 has BYDAY) or leave it is an open question — the
  parser stays small on purpose.
- No exceptions to a rule: "every other Tuesday, except the one in August". The record is
  append-only, so a skip would be its own statement subtracted by the derivation; nothing does
  that yet.
- A cyclic entity's repr says nothing about repeating. `entity.repeats()` and the write receipt
  do, and `world.repeats()` lists them, but a host printing an Event sees only the anchor and
  may read a series as a one-off. Fixing it means a query per repr, so it waits for a per-run
  cache.

## Half-open periods are invisible

s20 fails this way twice over: told "from October 1 my dentist is Patel instead of Rao", the host
ends Rao on September 30 and starts Patel on October 1, leaving a day with no dentist. Periods
here are half-open — [from, until) — so the handover is "until October 1", and nothing says so
where the host is looking. Worth a check in code rather than a line in the guide: for a relation
type with `one_of_a_label`, when one ends and another of the same label starts within a day or
two but not at the same moment, say that there is a gap (or an overlap) and what closes it.

## Free text is a type now, and comments are the odd one out

`list[text]` makes a slot hold several free texts, each stated on its own, each with its own
period: `entity.add("descriptions", ..., starts=, until=)`, `entity.drop(...)`,
`entity.spells("descriptions")`. Assigning the whole list goes through the same door. Tags are
the same machinery with one extra rule (one form to compare by), and `list[enum[a, b, c]]` is
the same again, drawn from a vocabulary.

Which leaves comments as a second mechanism for the same thing — free text about an entity, with
a date and a period — kept in its own table with its own words (`when`, `tentative`, `ttl`,
`forget()`, world-wide search). Two things worth deciding:

- Whether a comment becomes a `list[text]` item with `tentative` as a marker on the statement,
  and comments.py becomes a way of reading rather than a place of storage. That would leave one
  answer to "where does free text go", and one set of words for its time.
- What a comment has that a text item doesn't: `when` (the thing happened then) separate from
  the period (it holds from then), a default ttl, and searching across every entity at once. The
  first is real and would have to survive the merge.

## The ladder, as a template for structuring

Prose → vocabulary → value is the same slot growing up, and it is the shape the world should use
when it structures something itself (level 2, `ontology/grown`): a `list[text]` slot whose texts
keep repeating the same few words is a `list[enum[...]]` waiting to be declared, and a slot that
never holds more than one is an ordinary attribute. The world can see all three from the record
alone — count the distinct texts, count how often each recurs, count how many hold at once — and
propose the change rather than make it. Nothing does this yet; properties.py does the equivalent
for relations, and is the model to follow.
