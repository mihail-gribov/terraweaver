# The contract: how any agent works with a personal world

Any agent — Claude Code, Codex, OpenClaw, one somebody wrote — must be able to work with the
user's personal world without knowing how the world is built. This is the whole of what it needs
to know: four calls, in plain text, over MCP or HTTP. Every implementation of a world answers
these four calls the same way; every agent that makes them works with every world.

Version 0, 2026-10-10. The words MUST, SHOULD and MAY mean what they mean in RFC 2119. Why it is
shaped like this: `docs/decisions.md`, 2026-10-07 entries.

## Two sides

- **The host** is the agent the user talks to, or a subagent it sends. It is the user's side and
  not part of the world. It hears the user, resolves what the user meant ("she", "next Friday",
  "this city") from the conversation it alone can see, and retells it.
- **The world** is our system. It keeps everything it is told, with when and from whom, works out
  what it means — who is who, what replaces what, which class a thing belongs to — and says what
  it can't settle.

The host narrates; the world formalises. Nothing in the contract asks the host to know the
world's classes, relation types, ids or code, and nothing asks the world to see the conversation.

## The four calls

| Call | The host calls it | Takes | Returns | Changes the world |
|---|---|---|---|---|
| `context` | before answering a message | the user's message, a limit | what bears on it, or `nothing` | no |
| `tell` | when it hears something about the user's life | a statement and its source | `Kept.` | yes |
| `ask` | when it needs one specific thing | a question | an answer in words | no |
| `questions` | at a natural pause | a limit | what the world wants the user to settle | no |
| `search_memory` | when it needs the entries, not an answer | a query, a limit | the entries as told | no |
| `forget` | when the user asks for something to be forgotten | it in words, or entry numbers | the entries taken out | yes |
| `forgotten` | when the user asks what they had forgotten | nothing | the entries in the bin, until they are deleted | no |
| `add_memory` | — | as `tell` | as `tell` | yes |

`add_memory` and `search_memory` are the names every other memory uses (Mem0, Graphiti,
Supermemory, LangMem), so an agent that has seen them recognises them; `add_memory` is `tell`
under that name. Why the three were added: `docs/decisions.md`, 2026-10-15.

All input and output is plain UTF-8 text in English. Every call stands alone: there is no
session, no handle, no state the host has to carry between calls.

### Lists

`context` and `questions` answer with a list, in one form a host can read by code as well as
paste into a prompt:

- One item per line, each line starting with `- ` (dash, space). Every line of a list is an item;
  there are no headers, blank lines or other lines in it.
- An item never contains a line break: the world MUST turn line breaks inside an item into spaces.
  An item is never empty. It SHOULD be one sentence and MUST stay under 300 characters.
- Order means something: most relevant first for `context`, most pressing first for `questions`.
  A host that must cut a list cuts from the end.
- An empty list is not an empty string: it is the call's exact word for "none" — `nothing` for
  `context`, `Nothing to ask.` for `questions` — which never starts with `- `.

```
- Anna, the user's sister, lives in Porto; she moved there from Lisbon in September 2026.
- The user is allergic to cats.
```

### `context(message, limit=10) -> text`

What the world holds that bears on a message, so the host need not know what it doesn't know —
it won't ask about the user's sister if it doesn't remember there is one.

- `message` — the user's message **as written**, not a summary. Required.
- `limit` — the most items the host will take. Optional, 10 if not given. The world MUST NOT
  return more, and chooses the most relevant when it holds more.
- Returns the relevant facts **as they stand now**, as a list (above). When nothing bears on the
  message, it MUST return exactly `nothing`, so a hook can tell "no context" from context without
  reading it.
- It MUST NOT change what the world holds.
- It is called on every message, so it SHOULD answer in under two seconds; a host MAY drop the
  context and go on if it takes longer. It SHOULD NOT bring facts that merely mention a word in
  the message without bearing on it.
- The host puts the result beside the message. Where the user's latest word contradicts it, the
  user wins, and the host `tell`s the correction.

### `tell(text, source="conversation") -> text`

Something said about the user's life, handed to the world to keep.

- `text` — the statement. Required, not blank.
- `source` — where it came from: `conversation` for what the user said, otherwise a name a person
  would recognise: a file path, a URL, "email from Olga, 2026-10-09". One line of at most 200
  characters. Omitted or blank, it is `conversation`; the world turns line breaks in it into
  spaces.
- `text` MAY span several lines when the details belong together.
- On success it returns exactly `Kept.`. A blank `text` returns `Nothing was said, so nothing was
  kept.` and keeps nothing.
- `Kept.` means kept, not understood. `tell` never reports how the world read the statement, and
  never reports a doubt: it answers at once and the same way whether the statement was clear or
  not, so a host busy with the user can tell and move on. A doubt — "Olga" may be either of two
  people, a date with no year — surfaces later: as an item in `questions`, and as a caveat in the
  answers to `ask` and `context` that rest on it. A host that wants to know what the world made
  of a statement `ask`s.

What the host owes:

- **Self-contained.** The world sees only this text. Names instead of pronouns; absolute dates
  ("2026-10-20", not "Tuesday").
- **Dates by what was said, not by guess.** A date given without a year takes its year from the
  tense: "Mia starts school on September 1", said in October 2026, is 2027-09-01; "we met on
  January 20", said in October 2026, is 2026-01-20. A host that can't tell from the conversation
  which year is meant passes the date as said ("on January 20, year not said") rather than
  picking one.
- **As said.** No rounding, judging or embellishing; an uncertain statement stays uncertain
  ("the user thinks the meeting is on Tuesday").
- **Changes as changes.** "Anna moved from Lisbon to Porto", not only "Anna lives in Porto".
  A correction says what it corrects.
- **One subject per call** when unrelated things came up; related details go together.
- **No secrets.** Passwords, keys, tokens, card numbers are never told.
- **Only what the user asserted.** A question the user asks is not a fact: "when does Mia start
  school?" says nothing about when. Nothing is told as unknown.
- **Promptly.** At the moment it is heard, before the task the user asked for — a fact said in
  passing is the one that gets lost when the task takes over.

What the world owes:

- It MUST keep everything it is told, with the time it was told and the source. It never refuses
  a well-formed statement and never asks the host to restate it in another shape.
- It MUST reconcile on its own: the same person told twice, a value that replaces an older one,
  a later statement that ends an earlier one. Telling the same thing twice is safe.
- What it can't settle becomes a question in `questions`, never a refusal.
- It MUST NOT silently complete what the statement leaves open. A date with no year is kept as
  said; the world MAY settle the year from the statement's tense and the time it was told, and
  when that doesn't settle it, it raises a question instead of guessing. The same holds for a
  name that fits two people.

### `ask(question) -> text`

One specific question about the user's life, answered from everything the world holds.

- `question` — one question, in words. Required.
- Returns the answer in words, as the question asked it — not in the world's own terms (no
  class names, relation types or ids).
- When the world does not know, it MUST say so in the answer. It MUST NOT guess.
- Where the answer rests on something unsettled, the answer SHOULD say so ("Porto, though an
  earlier note says Lisbon").
- It MUST NOT change what the world holds.

`context` is broad and unasked — what bears on this message. `ask` is narrow and deliberate —
the one thing the host needs.

### `questions(limit=5) -> text`

What the world is unsure of and would like the user to settle: two Annas that may be one person,
two dentists both recorded as current.

- `limit` — the most questions the host will take. Optional, 5 if not given; the world MUST NOT
  return more.
- Returns the questions as a list (above), or exactly `Nothing to ask.` when there are none.
- It MUST NOT change what the world holds.
- The host asks the user at a natural pause, not in the middle of their task, and `tell`s the
  answer back as an ordinary statement that names what it settles ("Anna Lee and Anna from the
  gym are the same person").

### `search_memory(query, limit=10) -> text`

The entries the world holds that bear on a query, as they were told — not an answer.

- Returns a list (above) of entries, most relevant first, at most `limit`, each
  `- #<number> · <time told> · <source>: <the words>`, or exactly `nothing`. An entry is whole:
  the 300-character bound of a list item does not cut it.
- Where two entries disagree, both come back; the larger number is the later one. The world MAY
  say which still holds; it MUST NOT leave one out because it was replaced.
- It MUST NOT change what the world holds.

### `forget(what, now=None) -> text`

Takes out what the user wants forgotten: `what` in words ("Anna's old phone number"), or entry
numbers from `search_memory` ("#12, #14"), which are taken exactly.

- Returns the entries taken out, as a list in `search_memory`'s form, or exactly
  `Nothing was forgotten.` The host shows the user what went, so a wrong one can be told again.
- A forgotten entry goes to a bin: no reader sees it (`context`, `ask`, `search_memory`, any
  image), and only `forgotten` lists it. After a set time (30 days by default, by the world's
  clock) it is deleted for good, and so is everything the world held because of it. Its number
  is never given to another entry.
- A correction is not a forgetting: "Anna moved to Porto" is a `tell`, and the earlier entry
  stays as what held before.
- The request is kept: one new entry, source `forget`, dated `now` (the agent's, else the
  world's clock), saying that the user asked and how many entries went, in `what`'s words. So
  `what` names what to forget by what it is ("the storage unit move with Darren"), not by the
  detail to be dropped; "what did I ask you to drop?" is answered from it. A request is never
  taken by a later `forget` in words, only by its number.
- Whatever else a world holds of the same words goes to the same bin: a world that keeps the
  messages it heard takes out the sentences that said what was forgotten, and the answer lists
  them too.

### `forgotten() -> text`

What is in the bin: each forgotten entry as it was told, when it was forgotten, the words of the
request, and the day after which it is deleted for good — or exactly
`Nothing was forgotten in the last N days.` So the user can always see what they asked to drop
in that time. Nothing in the bin comes back by itself; to have it again, it is told again.

## Transport

The same four calls over two transports. An implementation MUST serve both.

**MCP** (streamable HTTP, path `/mcp`): tools named `context`, `tell`, `ask`, `questions`, `search_memory`, `forget`, `forgotten`, `add_memory` with the
parameters above. The server's `instructions` SHOULD tell the agent what the memory is — the
place everything about the user is kept — not only when to call it (see the measurements below).

**HTTP**, for what can't speak MCP — an agent's hooks, a proxy, a script:

| Route | Body (JSON) | Response (text/plain) |
|---|---|---|
| `POST /context` | `{"message": "...", "limit": 10}` | as `context` |
| `POST /tell` | `{"text": "...", "source": "..."}` | as `tell` |
| `POST /ask` | `{"question": "..."}` | as `ask` |
| `GET /questions?limit=5` | — | as `questions` |
| `POST /search_memory` | `{"query": "...", "limit": 10}` | as `search_memory` |
| `POST /forget` | `{"what": "...", "now": "..."}` | as `forget` |
| `GET /forgotten` | — | as `forgotten` |
| `POST /add_memory` | `{"text": "...", "source": "..."}` | as `tell` |
| `GET /health` | — | `{"ok": true, ...}` |

Bound to anything but localhost, every request except `/health` MUST carry
`Authorization: Bearer <token>`. A failure is an HTTP error status with a plain-text reason, or an
MCP tool result that says in words what failed — never an opaque error.

## Not in the contract

- **The world's object model.** `describe_world`, `run(code)` and the rest of
  `terraweaver/server.py` are a second door for agents strong enough to use them. An agent that
  knows only the four calls MUST get the full use of the world.
- **When the host is reminded.** Whether the agent calls the world on its own or is pushed by a
  hook is the adapter's business, below.
- **Who the user is.** One world serves one person; which world a host reaches is its
  configuration (the URL), not a parameter of any call.

## Connecting an agent

From weakest to strongest guarantee. Measured with `benchmarks/check_agent.py`, Claude Code on Haiku
as host, against the baseline: two fresh sessions per run, facts said in passing in the first and
needed in the second.

| Level | What it takes | aside | buried |
|---|---|---|---|
| MCP only | the server's URL | 2/3 | 0/5 |
| + a skill that says what the memory is | a skill or system-prompt text | 5/5 | 5/5 |
| + hooks and a mode | `adapters/claude_code/plugin` | 3/3 | 3/3 |

`aside`: allergy and a daughter's school date after an everyday request. `buried`: a father's
knee surgery mentioned as an apology inside a coding task. Few runs on one model: these show
direction, not rates.

What made the difference was the description of the skill — always in the agent's context — not
its body, which was never opened. Saying what the memory *is* ("the system where everything
about the user is kept; anything directly about the user goes through it, including what is said
in passing") moved `buried` from 0/5 to 5/5. Any agent's adapter should carry that sentence where
the agent always sees it: a skill description, a system prompt, MCP `instructions`.

For Claude Code the plugin adds a mode: `/personal` enters the user's personal world for the
session, `/personal off` leaves it, `adapters/claude_code/claude-personal` starts in it. In the
mode, a hook puts `context` beside every message; out of it, a hook refuses `tell`.

## Implementations

| | Where | Conforms | Behind the four calls |
|---|---|---|---|
| Baseline | `memory/journal.py`, port 7100 | yes, except `context` is not fast (seconds) | a text file; Haiku reads all of it |
| The world | — | not yet: needs a front serving the four calls | the record, identity, time, questions |

The baseline is what the world is measured against: same agent, same calls, same scenarios. The
world's effect is whatever it does beyond a text file and a model reading it.

**Checking an implementation:** `tests/test_baseline.py` for the calls themselves (`--live` for
the model-backed ones), `benchmarks/check_agent.py` for an agent using them. Both are written
against the baseline today and need a `--url` to run against any server.

## Open

- **Secrets on the way in.** `context` receives every message whole, pasted keys included. The
  adapter SHOULD strip secrets in code before anything leaves the machine; nothing does yet.
- **Work.** Whether a project deadline or "prefers tabs" is about the user's life. Today the host
  skips both. If the world wants them, the description has to name them.
- **Questions with handles.** An answer to a question comes back as a plain statement today. If
  matching it to the question proves unreliable, `questions` gets ids and `tell` an optional
  `answers=<id>`.
- **A proxy.** For agents with no hooks and no skills, the world could sit in front of the model
  API and call `context` and `tell` itself — the only connection that needs nothing from the agent.
