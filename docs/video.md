# The demo video: 3 minutes, two replays, one voice

Two replays, built from real runs with their traces, each at the speed that fits its slot:

    .venv/bin/python scripts/replay.py benchmarks/runs/demo-recall-birthday-20261030-035627 --speed 1.72
    .venv/bin/python scripts/replay.py benchmarks/runs/demo-recall-jazz-20261030-142413 --speed 1.8

Record each at 1920×1080 (H hides the bar). The timecodes below are of the video; the voice is
English, about 150 words a minute, cut into lines that each start on a moment of the replay.
`<break time="…"/>` is ElevenLabs' pause tag.

| Part | Video | Length |
|---|---|---|
| Intro | title card / the schema | 0:00–0:12 |
| Birthday | replay 1 at 1.72× | 0:12–1:43 |
| Jazz, the web | replay 2 at 1.8× | 1:43–2:45 |
| Close | the schema, the numbers | 2:45–3:00 |

## 0:00 — Intro (title card)

> Your assistant hears your life in passing. Between work questions, you mention a birthday, an
> allergy, a repair. A month later it has forgotten. TerraWeaver is a memory that keeps what
> matters, on NVIDIA Nemotron.

(31 words, ~12 s)

## 0:12 — Birthday (replay 1, at 1.72×)

**0:12** — first day, the calendar talk.
> Left: an ordinary chat with an agent. Right: the memory, every step as this run took it.

**0:16** — "that's my wife Mila's birthday" travels Gate → Resolve → Journal → Personal? → Reader.
> In passing: the eleventh is my wife Mila's birthday. A gate asks, anything to keep? It goes into
> the journal, as said, with its day. A second filter asks, is it about the user's life?
> Then the reader adds it to the user's world. Work talk, fast-forwarded, stops at the filters.

**0:31** — Saturday plans: "Mila hates crowds … a small jazz gig".
> Mila hates crowds, likes small jazz gigs: a line on her portrait.

**0:47** — "yes please" after the agent's question (Thai).
> Here the user only says: yes please. The resolver reads the agent's question before it, and
> keeps what was meant: skip Thai places, Mila is seriously allergic to peanuts.

**0:55** — Lev's party, "something quiet".
> Facts come in fragments, over weeks: something quiet, just the two of them. Each lands as a dated
> layer, and adding one costs the same on the first day as after a year.

**1:14** — Vesna, "just no peanuts, for Mila".
> A mother-in-law arrives. The world knows who she is to the user.

**1:25** — "Now reading" banner. The arrows turn and point back.
> Now the other way. Today: help me plan her birthday evening. The memory searches the journal,
> the people and the topics,

**1:31** — the note flies to the agent; the context popup opens.
> and hands the agent one short note, unseen by the user.

**1:35** — the reply arrives, message by message.
> The date. Quiet, just the two of them. Jazz. No peanuts. And Vesna, who may still be staying.
> Nobody asked it to remember any of this.

(~200 words over 91 s; leave the last seconds of the reply silent)

## 1:43 — Jazz: a topic kept current from the web (replay 2, at 1.8×)

Cues are moments of the replay; set the timecodes when it is recorded.

**1:43** — a month ago: "any good jazz concerts in Belgrade in November?"; the agent: programmes
aren't out yet.
> A month ago, a question nobody could answer yet: jazz in Belgrade, in November. And in passing:
> we used to go to Bitef every week.

**work talk, fast-forwarded** — the standup grumble is kept, then checked and left alone.
> Weeks of work talk go by.

**"Meanwhile: the web ↓"** — the 🌐 bubble, the web's entry in the journal, the topic layer.
> Meanwhile, in the quiet, the memory keeps its topics current. Concerts change; this one is due.
> It searches the web for the user's own question, with no names and nothing private, and keeps
> what matters as the web's entry, never as the user's words. A grumble about work is the user's
> own matter: it never reaches the web.

**"Now reading ←"** — today: "Saturday the 14th is free … any ideas?"
> Today: a free Saturday, any ideas? The topic comes back with what the web added:

**the note, then the reply.**
> Kovacs at Bitef, the fourth and the fifth: not the fourteenth, and the agent says so. Bitef
> first, book early.

(~130 words over 62 s; Tavily for the search, Nemotron for every decision)

## 2:45 — Close (the schema)

> Two doors: what the user says goes in, what the agent asks comes out. Two one-token Nemotron
> filters keep the noise out, Nemotron Super reads what is left, Tavily keeps the topics current,
> and the cost per message stays flat. TerraWeaver: a memory that grows with you.

(42 words, ~15 s)

## Notes

- The pace leaves room: about 2.4 words a second where a line has to land on a moment, less
  elsewhere. If a line runs long, slow that stretch in the edit, not the voice.
- The jazz run's reply calls Kovacs "him" and a saxophonist; Sharon Kovacs is a singer. Keep the
  voice on the dates, or redo the run.
