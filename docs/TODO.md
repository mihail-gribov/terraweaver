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
