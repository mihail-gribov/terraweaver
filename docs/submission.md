# Devpost submission — texts to paste

## Name
TerraWeaver

## Tagline (one line)
A personal memory for any agent that answers what a long life history asks: what happened when, how many times, how it stands now, and where we left off — on NVIDIA Nemotron via Nebius Token Factory.

## Track
Personal AI

## Built with
python, mcp, claude-code, nvidia-nemotron, nebius-token-factory, tavily, fastembed

---

## About the project (Project Story)

### What inspired it

Every assistant I use forgets what I said in passing — or remembers it in its own words. "Up to 400" goes into memory without the fact that it was the budget for the vacuum; "she" without who she is. The usual fix is a memory *tool*: the agent decides what to write and when, and it mostly doesn't. So you end up dictating facts to your assistant, and it still decides alone what is worth keeping about you.

I wanted the opposite: a memory that is **active**. It hears the conversation by itself, keeps what you say about your life in your own words, works on it while you are away, and when the agent needs something, gives facts with the words they stand on — never decisions made for you.

### What it does: the tasks it solves

TerraWeaver solves one class of tasks well: **a long personal history where the answer needs every fact that bears on it, its day, or its latest value.** Putting the whole history into the prompt stops working there, by size and by attention. A memory has to scale without losing what was said.

1. **What happened, and when.** "What did I do in the garden two weeks ago?" Every event the user mentions is kept with the day it happened, so "two weeks ago" finds "I planted 12 tomato saplings", not the gardening app mentioned the same week.
2. **How many — all of them.** "How many pieces of jewellery did I get in the last two months?" The answer gets every event of the matter across sessions, not the twelve entries most alike to the question.
3. **How it stands now.** "Which TV did we take in the end?" New lies over old, each layer dated: the Samsung chosen first, then the LG after the blinds went up. The old choice stays, marked as overridden.
4. **Where we left off.** A new session, a month later: "I want a soundbar for the living-room TV." Nobody asks the memory. It puts the matter the message goes on with beside it, and the agent answers for the LG C4 it now knows is on the wall.
5. **Facts for the agent's choice.** "Find me a concert…" The memory gathers over the web and judges each candidate against each of the user's conditions. It gives facts and limits; the choice stays with the agent and the user.

Measured on LongMemEval_S (~115k tokens of history a question): on counting across sessions, temporal reasoning and knowledge updates, the memory scores **[seed-1 numbers]** against **[…]** for the same model with the whole history in its prompt, and **[…]** for the ceiling (only the sessions that hold the answer). Judged by Claude Sonnet; questions from a seed not used during development.

How it hears and keeps:
- **Hears everything, decides nothing for the agent.** A Claude Code plugin passes every message to the memory's `say`. The agent has one door of its own, `ask`.
- **Keeps the user's words, made to stand alone.** A gate says whether a message tells anything personal. Nemotron Super rewrites it using only the agent's message before it: "up to 400" becomes "My budget for the vacuum is up to 400". The agent's message is then dropped.
- **Texts are the flesh, a skeleton over them.** Each entry is read as soon as it is kept, beside the conversation, into the entities it names, the plain links between them (spouse, friend, works at — or any other under its own name), what the user says they did, have, like or plan with its day, and the topics the user keeps coming back to, layered and dated. Every link stands on the entry's own words, checked by code. The skeleton finds; the answer is made from the texts.
- **Protects.** Secrets are withheld before any model sees them. A web query that names a person from the memory is refused.

### How I built it

- **Two doors over MCP** (`memory/server.py`): `say(messages)` and `ask(question)`, plus an HTTP `/say` for hooks. The plugin's MCP config sends `X-Personal-Hooks: on`, so the server refuses a second copy of a message the hooks already passed.
- **Nemotron as both LLM and decision model** (`terraweaver/nemotron.py`). Closed questions — personal or not? the same question as before? does this quote say that? — are answered from the first token's `top_logprobs`: one token, a probability instead of a guess, both option orders read to cancel the first-letter bias, temperatures calibrated per mode on public datasets (BoolQ, FEVER, ARC, ANLI and more).
- **Each model where it pays.** Nano 30B-A3B for hundreds of small closed questions; Super 120B-A12B for reading and rewriting; Ultra 550B-A55B where a single call decides a lot — the program that solves a task. Roles are bound in one file and moved by an environment variable.
- **A journal in plain Markdown** the user can read, append-only, with the user's words beside every rewrite. Everything else is derived from it and rebuilt from it: the graph (`memory/graph.py`) keeps mentions, links and every version of every topic as JSON lines, with indexes, so the reader of one entry is shown a bounded few topics and entities however large the memory grows.
- **Measured, not guessed.** Scripted dialogues run a real Claude Code host over several sessions and judge the answers; every behaviour change and the number behind it is in `docs/decisions.md`.

### Challenges

- **"We" is not "you and me".** The rewrite once turned "Neither of us likes loud clubs" into "Neither you nor I…" — the model counted the assistant in. A rule plus two examples took it from 15/16 to 32/32 on unseen exchanges.
- **Long prompts invent things.** My first rewrite prompt produced "any model for the about 70 m²…". A short prompt, in the shape that worked on 8B models before, embedded in a three-task frame, went from 8–9 to 13–16 of 16 hand checks.
- **Hooks are subtle.** An `async` Stop hook never reached the memory under `claude -p`; a first message was sometimes passed before the session was marked as personal; and Claude Code's own auto-memory quietly kept a second copy of the user's facts in its files. Each was found by a live run and fixed in code.
- **The memory raced the agent.** It used to search the web for the user's question while the agent asked the same thing in sharper words — two searches for one concert. The fix was a change of idea, not of code: the user's questions mark interests; the agent's `ask` is the only door that gathers.
- **Calibration is per question shape.** The decision model was right on public data and wrong on "are these two words one idea?". Asked instead "does the sentence say *Naomi older brother of Darren*?", it answers 0.01 — so we ask about the claim, not the word pair.

### What I learned

The hard part of personal memory is not storage or retrieval; it is **what to keep and how to say it** so that it still means the same thing a week later. A small, calibrated "yes/no" from logprobs is the most useful primitive I have: cheap enough to ask everywhere, honest enough to set thresholds on. And the right split is clean: the memory gathers, stores, structures and finds; the agent decides, with the user.

### What's next

The tasks not solved yet, each with where it sticks:
- **Suggestions by taste** (LongMemEval's preference questions). The grading is a matter of taste, and the answer step under-uses the user's facts; the fix is to hand the agent "what to take into account" rather than to look for advice.
- **A whole history at once** is read in hours, since each entry sees the topics of those before it. Live, entries come one by one over months; for a bulk import, reading must be parallel by dialogue.
- **Labels.** The decision model sometimes puts a link in the wrong class ("chose" as a preference); the day is sometimes filled where none was said.
- **Identity across dialogues** that can be undone, two "Toms" told apart; forgetting on the user's word; hooks for agents beyond Claude Code.

---

## What was built during the submission period

The repository was started on 2026-09-19, inside the submission period; all code in it was written during the hackathon. It continues the ideas of an earlier project of mine (an agent architecture over an object model, for company data), moved to a person's world and rewritten from scratch.

---

## Feedback on Nebius Token Factory and NVIDIA models

- **`logprobs` / `top_logprobs` on Nemotron made the project.** They turn a 30B model into a calibrated decision model at one output token. Please keep them, document them for every Nemotron, and consider returning more than the top 20.
- **First-letter bias is strong** on Nano-30B-A3B for lettered options (75–79% of yes/no questions went to whichever option came first). Reading both orders fixes it at twice the calls; a note in the docs would save others the discovery.
- **A thinking switch per call** worked well (off for one-token decisions, on with a token budget for the rewrite). Clearer docs on how the thinking budget and `max_tokens` interact would help.
- **Having Nano, Super and Ultra behind one API** let each role take the model it needs by changing one name: Ultra for the single call that writes a program, Nano for the hundreds of yes/no questions.
- **Billing:** a run of ours hit `402 Payment Required` mid-session. An early warning before credits run out, or a soft limit, would avoid losing a run.
- **Embeddings** on Token Factory removed our dependency on a local GPU, which mattered for a judge running on a clean machine.

---

## Links
- Code: https://github.com/mihail-gribov/terraweaver
- Video: (YouTube link)
- Try it: the README's "Run it" section — the memory server and Claude Code with the plugin, two commands.
