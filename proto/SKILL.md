---
name: personal-memory-code
description: The user's personal memory — the system where everything about the user is kept. Anything directly about the user goes through it, always — who they are, the people in their life, health, plans and dates, home, work commitments, preferences, what happened — including things said in passing in the middle of an unrelated task. Save such facts the moment they come up with the memory's `run` tool, naming the people, places and events as variables; look things up before answering anything that could depend on who the user is.
---

# Personal memory, by code

The memory's `run(code, now)` tool runs Python in which you name what the user talks about and
say what is true of it. Variables last between your runs in this conversation, so a person you
made once is `anna` from then on. Pass `now` with every run: the current date and time as you know
them (`"2026-10-15T14:30"`), which is when the facts were said.

```python
anna = entity("Anna", "Anna is the user's sister.", kind="person")   # kind: any word, optional
olga = entity("Olga")
anna.say("Anna moved from Lisbon to Porto in September 2026.")
link(anna, olga, "Anna and Olga work together at Brightwork.", as_="colleague")
event("Anna's wedding", "Anna marries Tom on 2027-06-12 in Porto.", when="2027-06-12", who=[anna, tom])
print(anna.about())                     # every entry about Anna, as told
```

| Call | What it is |
|---|---|
| `entity(name, text=None, kind=None)` | a person, place, thing; `text` is a first fact about it |
| `event(name, text, when=None, who=[...])` | something that happened or will |
| `link(a, b, text, as_=None)` | what joins two things; `as_` is any word for it |
| `x.say(text)` | a fact about one thing |
| `x.about()` | what the memory holds about it |
| `same(a, b)` / `different(a, b)` | your answer when the memory asks who is who |
| `thing("t3")` | a thing the memory holds, by its id |

Every call that says something takes `source=`: `"conversation"` (the default) for what the user
said, otherwise a file, a page, "email from Olga, 2026-10-09".

**The text is the fact.** Name the words as you like — `kind`, `as_`, the names — the memory
sorts them out. What it cannot sort out is a sentence that does not stand alone: every text names
what it is about ("Anna moved…", not "she moved…"), with absolute dates, as the user said it.
Changes as changes: "Anna moved from Lisbon to Porto", not only "Anna lives in Porto".

**The memory may ask you.** A run's answer can end with "The memory asks:" — most often whether a
new `Anna` is one it already holds. Answer in your next run with `same(...)` or `different(...)`
as the question gives them; if you cannot tell from the conversation, leave it, and the memory
will ask the user.

**Reading.** The other tools stay: `context` with the user's message before answering anything
about their life, `ask` for one specific thing, `search_memory` for the entries themselves,
`forget` when the user asks for something to be forgotten (it waits in a bin, and `forgotten`
lists it until it is deleted for good), `questions` at a natural pause.

**Tasks.** For anything that needs gathering, comparing or choosing — "pick me a robot vacuum",
"what's that concert my wife mentioned, and when could we go", "what did we spend on the car this
year" — call `task(text)` with the task in the user's words. Don't restate what the memory knows
(budget, wishes, who the people are): it adds that itself. It takes a few minutes. The memory
gives facts, not decisions: its answer is what was found, how each candidate stands on the user's
limits and wishes (met, not known, NOT met, with the words each stands on), what was ruled out,
and the user's own limits and wishes as they said them. The decision is yours, made with the
user: choose from that answer, say why in its terms, and name nothing it does not hold.

What not to keep: passwords, keys, card numbers; details of the task at hand that say nothing
about the user's life; what the memory just gave you back.
