# TODO

Ordered by what currently blocks progress. The focus is reading the world; write tasks are
deliberately parked (see below).

## Debug the host–world loop

The world is served over MCP; the host agent writes code against the object model through
`describe_world()` and `run(code)`. Everything else — procedural memory
(`docs/procedural-memory.md`), `remember`, `research`, `extend` — builds on this loop, so it
comes first.

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
