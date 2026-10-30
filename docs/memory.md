# The memory

An active personal memory for any agent. It hears the conversation by itself, keeps what the user
says about their life in the user's own words, lays a light skeleton over those words — the
people and things they mention, the plainest links between them, the topics they make up — and
answers the agent with facts, never decisions.

**The texts are the flesh, the structure is the skeleton.** What the user said is kept as said and
is what an answer is made from. The skeleton only finds the texts that bear on a question and says
what a long talk has come to. Whatever is hard to formalise is never forced into a field: it stays
in the words that said it, and the model reads it there.

## What it holds to

1. **It listens; nobody has to tell it.** Hooks pass every message of the conversation (the Claude
   Code plugin; any agent with MCP can pass them itself). The agent is never asked to remember to
   save something, and cannot forget to.
2. **The user's words are the source.** What the user said, rewritten only so it stands alone, is
   kept append-only. Everything else — dialogues, topics, entities, links — is derived from those
   words and rebuilt from them at any time.
3. **A fact stands on what was said, never on what the model wrote.** A mention, a link, a fact
   about the user stands on an entry, with the words it comes from, checked by code to be there. A topic's text, which the model writes, helps to find
   and to sum up, never to prove: it cannot confirm itself.
4. **The texts are the links.** "My wife Mila loves jazz" joins the user, Mila and jazz by being
   said. Nothing is drawn out of it as a formal triple but a few plain links worth following
   (spouse, parent, friend, works at…) — a skeleton, not a fence: any other link the entry states
   is kept too, under its own name.
5. **Newer holds; older stays.** Every text carries its day. What was said later says what holds
   now, and what was said before stays beside it: a topic says what was chosen, and also what was
   ruled out and why.
6. **Facts, not decisions.** The memory stores, structures and finds. It gives the agent
   facts with the words and days they stand on, and the user's limits. Choosing is the agent's,
   with the user.
7. **Private and under the user's control.** It runs on the user's machine; secrets are withheld
   before any model sees them; an entry is forgotten only when the user asks and confirms which.

## An example

Monday, choosing a TV. The agent lists three; the user says *"the sony is too dear"*, then
*"yeah, our living room is very bright, the LG would glare"*, then *"ok, let's take the samsung"*.
The journal keeps *"The Sony Bravia 8 is too dear"*, *"Our living room is very bright, the LG C4
would cause glare"*, *"Ok, let's take the Samsung S90D"* — each dated, the user's words beside it.

Each entry is read as it is kept: it mentions Sony Bravia 8, LG C4, Samsung S90D, the living room;
*"My wife Mila"* earlier gave the link *Mila — spouse — the user*. The topic "TV selection" grows
a layer with each entry.

A month later: *"Hey, we went with the LG after all, we put up blinds."* The topic gets its next
layer. Measured live on 2026-10-29, its text read: *"Wants a new TV around 55 inches for the living
room (2026-10-26). Considered Sony Bravia 8; ruled out, too dear (2026-10-26). Considered LG; would
glare due to bright living room (2026-10-26). Chose Samsung S90D (2026-10-26). Changed to LG after
putting up blinds to reduce glare (2026-11-28)."*

Then the agent asks which TV was chosen in the end and what was ruled out. The memory answered:
the LG (fact 5, 2026-11-28); the Sony ruled out, too dear (fact 2); the LG first ruled out for
glare, which the blinds later solved (fact 3); the Samsung chosen at first and then overridden
(fact 4). The agent neither says "Samsung" nor offers the Sony again.

## What it works with

| | What it is | Kept |
|---|---|---|
| **Message** | one message of the conversation, the user's or the agent's | the agent's message is read to resolve the user's, then dropped; both stay only in `heard.jsonl`, the log for looking at a run |
| **Entry** | one user message, rewritten to stand alone, with the words as said beside it, numbered and dated | the journal (`facts.md`), append-only — the source of truth |
| **Dialogue** | the entries of one talk in a row, the user's only, until a pause of more than an hour | not stored: a stretch of the journal |
| **Topic** | a text the reader writes over the entries on one subject, across dialogues, layered and dated: considered, ruled out and why, chosen, changed | every version, with the entries it stands on (`topics.jsonl`) |
| **Entity** | a person, place, thing, organisation or event an entry names, with a kind from a flat set ("person", "TV", "place") — the kinds in use are shown to the reader first; no hierarchy | as mentions (`mentions.jsonl`) |
| **Mention** | an entry naming an entity, with the words it names it by ("My wife Mila"), its day and dialogue | `mentions.jsonl` |
| **Link** | two entities joined by what an entry says, with the words: a few common relations named the same way every time, any other under its own name | `links.jsonl` |
| **The user** | the one entity every dialogue shares: every entry is the user's, so "I", "we", "my" are the user — a fact of the source, made one by code | everything said of the user's people hangs on them: "my wife Mila" is *Mila — spouse — the user* |
| **Image** | one entity as the memory knows it now: every entry that mentions it, the newest first, its links and its topics | built when asked for, never stored |
| **Interest** | a question the user asked, with how often it came back | the interests log |
| **Portrait** | everything personal known of one person, as a text the reader writes over itself, each line with its day — the flesh the user's world is drawn from | every version (`portraits.jsonl`) |

## The user's world

A structure the memory fills as the user speaks, half fixed. What every person can have is fixed:
the same parts for the user and for each of their people. What fills the parts comes only from the
user's words, each value with its quote, fact and day. Whatever does not fit is still kept, as a link
under its own name or in the text.

| Part | One or many | Read as |
|---|---|---|
| spouse, partner, manager | one | *Mila — spouse → the user* |
| child, parent, sibling, pet | few: a list where one of each is usual | *Lev — child → the user*; "the user is the father of Lev" says the same |
| relative, friend, colleague | many | *Ana — friend → the user* |
| born on, age, lives in, works at, job, studies at | one | *Mila — born_on → 3 May*: the value in the entry's own words |
| owns, skill, speaks, hobby, health, likes, dislikes | many | *the user — owns → LG C4* |

Each part is one row of one table (`PARTS` in `memory/graph.py`). The row says its group, its size, what fills it (a person, an animal, a thing or a value), what the reader and the decision model are told, what the user calls it ("my wife"), and its inverse. The reading, the tree of questions, the joins, the world and recall all read the same row, so a new part is one new row.

How it is filled:
- **One value:** the newest holds and the older is kept as *was*. Leaving Acme for Globex: works at Globex; was Acme.
- **A list:** grows. An entry that says an item no longer holds (sold, broke up, moved out, went with another instead) ends it. The item is kept as *was*, with the fact that ended it.
- **Someone not yet named:** "My wife loves jazz" gives the user a wife, *the user's wife*, whose name is not known yet. Code sets this from the words, not a model. What is said of her is hers.
- **Named later:** "Mila, my wife…" names her. *The user's wife* and Mila are joined as one person, and what was said before the name is Mila's. Code joins the two when the user has only one person in that place: one spouse, or the only sister the memory knows. Friends, colleagues and relatives are many and are never joined this way. The join is a row of its own with the fact that made it, so it can be undone.
- **Plain facts by code:** the user's plainest links ("my wife Mila", "Mila, my wife", "our son Lev") are set by code from the words. A model may miss them.

What is not filled yet is part of the structure: *not known yet: born on, the name of the user's wife*. This is where the memory's questions to the user will come from.

The world is kept as `world.json` beside the graph, updated after every entry, and served at `GET /world`. Like everything but the journal, it is rebuilt from the journal. `ask` gets the user's world and the worlds of the people the question names. Beside a message go only the parts it speaks of ("my wife", "the TV", "her birthday") and the worlds of the people it names.

## What it does

**Hears.** Every message comes through `say`. A gate — the decision model over the last four
messages, one token — says whether the user's message tells anything personal. If it does, Nemotron
Super rewrites it to stand alone, resolving "it", "those", "up to 400" from the agent's message just
before it and from nothing else. The rewrite goes into the journal with the user's words beside it.
A question of the user's is noted as an interest; the memory does not answer it — the agent asks if
it needs to.

**Reads at once, beside the conversation** (`memory/graph.py`). An entry is read as soon as it is
kept, in the background, while the talk goes on: what was just said is what the next request is
likely to need. One call to Nemotron Super per entry, shown the entry, what the user said earlier in
the dialogue, the entities and kinds already known, and the topics' last texts. It gives the
entities the entry mentions, the links it states, and the topics it belongs to with their new text.
Code keeps a mention or a link only when its words are in the entry, and makes every "I", "we",
"user" the one user. A known entity is given its known name, so an image gathers what every
dialogue said of it. An `ask` that comes while entries are being read waits for them, a bounded
time.

**Answers.** The agent asks through `ask`. The memory finds the entries that bear on the question,
by words and meaning, each with its number and day; the graph adds the topics those entries belong
to and the images of the entities they and the question name. Nemotron Super, thinking, answers from
that with the numbers and days of the facts it used, works out how long or how many, and says when
the memory does not say. The memory does not search the web for a question: it answers from what it
holds, including what it has kept from the web itself (below).

**Keeps topics fresh from the web** (`memory/refresh.py`, `memory/web.py`). What a topic is about
can change outside the user's words: a venue closes, a price moves, a season starts. The object of
a web refresh is the **topic**, and the result is a message attached to it:

- *Fresh* means the topic's latest web entry is younger than a month (`FRESH`, 30 days). Freshness
  is read from that message. A check that found nothing keeps no entry (a "nothing" read into a
  topic would be noise), so it is recorded as a check beside the graph (`web_checks.jsonl`) and
  counts the same, also across a restart; so does a topic whose outside does not change.
- *Dormant* topics are left alone: if the user has not come back to a topic for three months
  (`DORMANT`, 90 days; counted from the latest **user** entry, never a web one, or a refreshed topic
  would keep itself alive) it is no longer relevant and is not refreshed.
- Every topic that is neither fresh nor dormant is due. A scheduler inside the server wakes every
  few minutes and, at most once an hour (`TERRAWEAVER_WEB_EVERY`, 3600 s, counted from the last
  sweep and kept beside the graph so a restart does not reset it), sweeps the due topics, one at a
  time and a bounded number per sweep. No outside cron and no HTTP route is needed.
- A one-token question to the small Nemotron says whether what is outside would change for this
  topic (places, events, prices, offers, news — not the user's own plans or people); a topic that
  does not change counts as checked. The queries are made from the topic and the user's questions on
  it, and carry no private detail: the model is told so, and code drops any query that holds the name of a person in the memory. Tavily finds the pages, the reader says
  what on them answers, each fact with its address, and a second one-token question says whether it
  matters.
- What matters is kept in the **same journal** as a web entry (`## #N · time · the web · topic T`),
  read into the topic like the user's entries, and shown to every model as "(from the web)" — never
  as the user's words. The agent hears of a sweep with the memory's next answer, whether it found
  something or nothing new.

The reasons are in `docs/decisions.md`: a price or an event list changes within weeks, so a month
is the natural beat; one search per topic per month and one sweep per hour bound the cost and the
noise, which matters most on the shared demo that spends the author's search key.

## What it is not

- **Not a store the agent writes to.** A store holds what the agent chose to keep, in the agent's
  words; this one hears everything and keeps the user's.
- **Not a summary that rewrites the past.** A memory that consolidates by rewriting loses what was
  said when the rewrite is wrong; here a topic is derived, every version kept, and the words under
  it never touched.
- **Not a schema to fill.** The world is not squeezed into fields: a few links are named the
  common way, everything else stays in the user's words.
- **Not an advisor.** It does not pick the concert or the TV; it gives the facts and the limits the
  pick must meet.

## Where it stands (2026-10-30)

| | |
|---|---|
| Built and measured | hearing through hooks; the gate and the rewrite; the journal with days; interests; `ask` from the journal and the graph (LongMemEval `_s`, seed 1, judged by Sonnet: 20 of 30, against 24 of 30 for the whole history in context); recall beside each message; secrets withheld; forgetting on the user's confirmed word |
| Built, measured on stories | the graph: each entry read as it is kept into mentions, links, layered topics and portraits; the user's world filled from four family talks, 13 of 13 values (`scripts/demo_world.py`) |
| Set aside | the ontology grown automatically and gathering over the web at the agent's request — the earlier world engine, kept on the `topics` branch and in the history; identity across dialogues that can be undone; rebuilding a topic from all its entries now and then; preparing ahead by interest; hooks for agents other than Claude Code |

## Open

- **Where a dialogue ends.** A pause of an hour for now; a new session of the agent would be the
  better mark, and the hooks know it.
- **One name for one thing.** The reader is shown the entities already known and gives a known one
  its name; two dialogues' "Tom" are then one image. Telling two Toms apart, and undoing a wrong
  join, needs identity as a link of its own.
- **Topic drift.** A topic is rewritten over its last version; over many updates it can drift. The
  remedy is a rebuild from all its entries now and then.
