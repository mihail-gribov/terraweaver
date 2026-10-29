# The memory

An active personal memory for any agent. It hears the conversation by itself, keeps what the user
says about their life in the user's own words, builds on those words a graph that knows where every
fact came from and when it stopped being true, and answers the agent with facts — never decisions.

## What it holds to

1. **It listens; nobody has to tell it.** Hooks pass every message of the conversation (the Claude Code
   plugin; any agent with MCP can pass them itself). The agent is never asked to remember to save something, and cannot forget to.
2. **The user's words are the source.** What the user said, rewritten only so it stands alone, is
   kept append-only. Everything else — dialogues, topics, the graph, the images of people and
   things — is derived from those words and can be rebuilt from them at any time.
3. **A fact stands on what was said, never on what the model wrote.** A fact about the user stands
   on an entry, a fact about the world on a web page, each with a quote checked by code. Texts the
   model writes — a topic's summary — help to find, never to prove: a summary cannot confirm itself.
4. **Nothing collapses.** Every statement stays its own assertion, with its text and its day. What
   two conversations said is kept apart; that they speak of one person is a link of its own, with
   its own support, which a later fact can undo.
5. **Time closes, it does not delete.** A newer fact closes an older one; the older stays, closed,
   with what closed it. The answer gives what holds now; the history says what was ruled out and why.
6. **Facts, not decisions.** The memory gathers, stores, structures and finds. It gives the agent
   facts with the words and days they stand on, and the user's limits. Choosing is the agent's,
   with the user.
7. **Private and under the user's control.** It runs on the user's machine; secrets are withheld before any model sees them; a web
   query that names a person from the memory is refused; neither the agent nor the memory removes
   anything.

## An example

Monday, choosing a TV. The agent lists three; the user: *"the Sony is too dear"*, then *"LG glares
in our bright living room"*, then *"ok, the Samsung"*. The journal keeps *"The Sony TV is too
expensive for me"*, *"The LG TV has glare in our bright living room"*, *"Let's take the Samsung
S90D"*, each dated, the user's words beside the rewrite.

As each entry is kept it is read: entities Sony TV, LG TV, Samsung S90D, the living room; the
assertions *ruled out: Sony — too expensive*, *ruled out: LG — glare*, *chosen: Samsung S90D*, each
on its entry. The topic "choosing a TV" gets its first version: *looked at Sony, LG and Samsung;
Sony dropped, too dear; LG dropped, glare in a bright room; settled on the Samsung S90D (#41–#43)*.

A month later: *"actually, we went with the LG after all, we got blinds"*. Its dialogue is read; the
new *chosen: LG* closes *chosen: Samsung* — closed, not deleted — and *ruled out: LG* is closed by
the same entry. The topic gets a new layer: *then moved to the LG, once blinds took the glare away*.

Then: *"which TV did we choose last time?"* The agent asks the memory. It answers with the topic,
and the facts under it: *chosen: LG (#57, 2026-11-28); before it the Samsung S90D (#43, closed by
#57); Sony ruled out, too expensive (#41)* — so the agent neither says "Samsung" nor offers the Sony
again.

## What it works with

| | What it is | Kept |
|---|---|---|
| **Message** | one message of the conversation, the user's or the agent's | the agent's message is read to resolve the user's, then dropped; both stay only in `heard.jsonl`, the log for looking at a run |
| **Entry** | one user message, rewritten to stand alone, with the words as said beside it, numbered and dated | the journal, append-only — the source of truth |
| **Dialogue** | the entries of one conversation in a row, the user's only, until a long silence or a new session | not stored: a stretch of the journal |
| **Topic** | a text the model writes over the entries on one subject, across dialogues, layered: considered, ruled out and why, chosen, changed — naming the entries it stands on | every version; a new one closes the one before |
| **Entity** | a person, place or thing as one dialogue speaks of it, with a plain kind word ("person", "TV") | per dialogue |
| **Assertion** | one thing an entry says of an entity: a value, or a relation to another entity | with its entry, quote, `said` and `until` |
| **The user** | the one entity shared by every dialogue: every entry is the user's, so "I", "me", "my" are always the user — a fact of the source, not a guess. A name the user goes by ("Alex") is bound to them by an identity link | one, always; everything the user tells of their people hangs on them ("my wife" is a person with *wife → the user*) |
| **Identity link** | "the Tom of Monday is Tom Becker": two dialogues' entities are one | with its entry and quote; can be undone |
| **Image** | what the memory knows of one entity now: the entities linked as one, their open assertions, latest first, each with its text | built when asked for, only cached |
| **Interest** | a question the user asked, with how often it came back | the interests log |
| **Finding** | what a gathering read on the web, with the page and quote it stands on | lives a TTL from its last use; about the world, never about the user |

How they connect: every text (entry, dialogue, topic) mentions entities; assertions and identity
links stand on entries, findings on pages; dialogues and topics are made of entries, and an entry
can be in several topics; an interest can belong to a topic.

## What it does

**Hears.** Every message comes through `say`. A gate — the decision model over the last four
messages, one token — says whether the user's message tells anything personal. If it does, Nemotron
Super rewrites it to stand alone, resolving "it", "those", "up to 400" from the agent's message just
before it and from nothing else. The rewrite goes into the journal with the user's words beside it.
A question of the user's is noted as an interest; the memory does not answer it — the agent asks if
it needs to.

**Reads at once, beside the conversation.** An entry is read as soon as it is kept, in the
background, while the talk goes on: what is just said is what the next request is likely to need,
and what is already read saves time then. The entry stands alone, so nothing waits for the next one.
It is read with what its dialogue has already given, so "my wife" and "Mila" there stay one entity;
out come the entities it adds, the assertions it makes with their quotes, and the topics it
touches. Each step reads the one new entry, never the whole dialogue again. A topic touched gets a
new version, written over its last one and the new entry; now and then it is rebuilt from all its
entries, so updates on updates do not drift. An `ask` that comes while an entry is being read waits
for it, a bounded time; past that it answers from the journal, by words and meaning, so the newest
entry is never missed.
- **Time.** A one-valued relation (the chosen TV, the budget, the city) is closed by the next value,
  by code. A many-valued one (likes jazz, likes classical) is closed only by an entry that says it
  no longer holds — a closed question to the decision model. Which kind a relation is, the model
  says once per relation.
- **Anchored on the user.** The user is always there, so whatever is said of their people is a
  relation to them: "my sister" is a person with *sister → the user*, "my wife" a person with
  *wife → the user*, each assertion on its entry. Across dialogues this is the strongest identity
  evidence a personal memory has: "my wife" on Monday and "my wife" on Friday share one relation
  to one user. A one-valued relation to the user (wife, manager) links them by code while the
  earlier one is open; a many-valued one (sister, colleague, friend) only makes them candidates.
- **Identity.** The new dialogue's entities are matched against the images already known —
  candidates by name and meaning, the judge decides from logprobs. A link is added, or undone when
  a new fact tells two apart, and the images it touches are built anew.

**Answers.** The agent asks through `ask`. The memory finds the entities, topics and entries that
bear on the question and answers with facts: each with its entry's number, day and quote, what holds
now first, what was closed beside it when it matters. When something has to be found outside, it
gathers: a program written by Nemotron Ultra over the memory and the web, every candidate returned
with each of the user's conditions judged against the page. When the memory does not say, it says so.

## What it is not

- **Not a store the agent writes to.** A store holds what the agent chose to keep, in the agent's
  words; this one hears everything and keeps the user's.
- **Not a summary that rewrites the past.** A memory that consolidates by rewriting loses what was
  said when the rewrite is wrong; here summaries are derived, and the words under them never touched.
- **Not a knowledge base that merges.** Merging on write makes one wrong match permanent; here
  identity is a link that a later fact can undo.
- **Not an advisor.** It does not pick the concert or the TV; it gives the facts and the limits the
  pick must meet.

## Where it stands (2026-10-29)

| | |
|---|---|
| Built and measured | hearing through hooks; the gate and the rewrite; the journal with days; interests; `ask` from the journal; gathering over the web with conditions judged; secrets withheld; person names kept out of web queries |
| Built, the older way | the world reads the journal after 30 s of silence into values and links, each with its entry and quote, and asks whether a later entry ends a link — but it merges identity on write and drops an ended link instead of closing it |
| Designed, not built | dialogues and topics as texts; assertions per dialogue with `said`/`until`; identity links that can be undone; images built when asked for |
| Set aside | the automatic class hierarchy and its generated methods; preparing ahead by interest; forgetting on the user's word (entries shown, confirmed, removed with all that stood on them, topics and images rebuilt without them); hooks for agents other than Claude Code |

## Open

- **Where a dialogue ends.** A new session ends it; within a session, how long a pause? This only
  says where entities live; it never decides when the memory works.
- **Relation names without a hierarchy.** Closing by code needs the same relation for the same
  thing ("chosen" and "went with"); the reader is given the relations already in use, and a near
  name is asked about, not guessed.
- **Identity across many dialogues.** Matching against images, not against every past entity, keeps
  it to a few judge calls per new entity; whether that holds at a year of talk is to be measured.
- **What re-reading keeps.** A dialogue read again replaces its own entities; the identity links
  made to them must find them again — by the entry and quote they stand on, not by an id.
