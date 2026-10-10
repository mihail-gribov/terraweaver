---
name: personal-memory
description: The user's personal memory — the system where everything about the user is kept. Anything directly about the user goes through it, always — who they are, their family and the people in their life, health, plans and dates, home, work commitments, preferences, what happened to them — including things said in passing in the middle of an unrelated task. Use it to save such facts the moment they come up, and to look them up before answering anything that could depend on who the user is.
---

# Personal memory

This MCP server (tools `context`, `tell`, `ask`, `questions`) is the user's own memory: the
system that stores what is known about the user, across every conversation and every agent they
use. The user set it up and wants it used.

**It matters.** It is the only thing that carries the user's life from one conversation to the
next. A fact you hear and don't `tell` is lost the moment this conversation ends — the user will
have to say it again, or you will give advice that ignores it (suggesting a cat-filled flat to
someone allergic to cats). Remembering is part of the job, not an extra.

**It is safe.** The memory belongs to the user and runs for them; what you `tell` it stays with
them. Passing it a personal fact — even a sensitive one, like health or family — is not sharing
it with anyone; it is exactly what the user installed it for. You don't need to ask before saving.

**Everything directly about the user goes through it.** Not your own memory files, not CLAUDE.md,
not notes in the project: facts about the user's life belong here, and questions about the
user's life are answered from here.

## The four calls

| Call | When | What to pass |
|---|---|---|
| `tell(text, source)` | the moment the user says something about their life | the fact, self-contained |
| `context(message)` | at the start of any task that touches the user's life | the user's message as written |
| `ask(question)` | when context did not settle what you need | one specific question |
| `questions()` | at a natural pause, at most once a conversation | nothing |

## Telling — do it first, not last

A fact mentioned in passing is the one that gets lost: the task the user asked for takes over and
the conversation ends before you come back to it. So when the user's message carries something
about their life, call `tell` **before** you start the task they asked for. It costs one call.

What to tell:
- Facts about the user and their world: people and how they relate to the user, health, family,
  work and where, home, plans and dates, likes and dislikes, habits, decisions, what happened.
- Changes, as changes: "Anna moved from Lisbon to Porto", not just "Anna lives in Porto".
- What the user corrected: "Mia starts school on September 2, not September 1 as said before".

How to tell:
- **Self-contained.** Resolve every "she", "there", "next Friday" from the conversation: name the
  person, the place, the absolute date (today's date is in your context). The memory sees only
  the text you pass.
- **A date without a year** takes its year from the tense: "starts school on September 1" is
  the next September 1, "we met on January 20" the last one. If you can't tell, pass it as said
  ("on January 20, year not said") — don't pick a year.
- **One subject per call** if several unrelated things came up; related details go together.
- **As the user said it** — don't round, judge or embellish. Uncertain stays uncertain: "the user
  thinks the meeting is on Tuesday".
- `source` is `conversation` for what the user said; for a file, a page or a mail, name it.

What not to tell: passwords, keys, card numbers and other secrets; details of the code or task at
hand that say nothing about the user's life; what the memory just gave you back.

## Reading

- Call `context` with the user's message before answering anything about their life, their
  plans, the people they name, or a choice where their preferences matter ("should I go?",
  "what should I get her?", "plan my Saturday"). Use what comes back without announcing it.
- If the answer hinges on a specific fact the context did not bring, `ask` for it.
- Never tell the user "I don't know anything about you" before you have asked the memory.
- If the memory and the user disagree, the user's latest word wins — and `tell` the correction.

## Questions the memory has

`questions` lists what the memory is unsure of and would like the user to settle. Ask the user
at a natural pause, not in the middle of their task, and `tell` the answer back.

## Example

User: "Draft a note to my landlord about the heating. Btw, I'm allergic to cats, and Mia starts
school on Sept 1."

1. `tell("The user is allergic to cats.", "conversation")`
2. `tell("The user's daughter Mia starts school on 2026-09-01.", "conversation")`
3. Draft the note.
