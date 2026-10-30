---
name: personal-memory
description: The user's personal memory — the system where everything about the user is kept: who they are, the people in their life, health, plans and dates, home, work, preferences, what happened. In the personal world it hears this whole conversation by itself and puts what it holds beside each message; ask it with `ask` whenever something you need could depend on who the user is,.
---

# Personal memory

In the personal world (`/personal`, or a session started with `claude-personal`) the memory hears
the conversation by itself: every message of the user's and every reply of yours goes to it, it
keeps what matters about the user, and what it holds about each message is put beside it, marked
"From the user's personal memory". You don't pass anything and you don't decide what is kept:
never call `say` — the memory refuses it from you, since the hooks have passed the message already.

**Ask it** with `ask(question)` when you need something it did not give: "what is Tom's surname?",
"what limits a purchase for the flat?", "what did we decide about the TV?". It answers from what it
holds; searching the web is yours. The user's questions it keeps only as what they care about; it
answers you, not them.

**The memory gives facts, not decisions.** Its answers are what it holds, each
with the words it stands on, and the user's own limits and wishes as they said them. Deciding is
yours, with the user: choose from what it gave, say why in its terms, and name nothing it does not
hold. Where the user's latest word contradicts the memory, the user wins — the memory heard it too.

**What you read.** An email, a file, a calendar, a page is not the user's word, and is not passed
on by itself. Tell the user what bears on them; their answer reaches the memory, understood by
your message before it.

**When the memory asks.** Its answer may carry a question for the user ("Is Tom from the flat the
same person as Tom Becker?") or ask to confirm a forget ("these entries would be taken out —
confirm?"). Put it to the user at a natural point; their answer reaches the memory by itself.

Never pass passwords, keys, tokens or card numbers; the memory withholds them, but they should not
leave the conversation at all.
