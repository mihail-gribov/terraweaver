# 03 — Visualising the main scenario

Started 2026-10-04 by the user.

## The question

How should the demo scenario, "where to go on Saturday", be shown in the video, so that a viewer
sees what the world does that a plain memory store does not: what the person said, what the world
made of it, and what the host answered from it.

## What it runs against

The real world from the base (`ontology.base_specs` + `WorldRuntime(fixture=None)`), driven through
the doors a host goes through. A visualisation reads the record; it never holds data of its own.

## How

The scenario is not built yet (it is due Oct 10–16), so the material is written the way
`experiments/story` writes it: steps of what the person said and the code an ideal host writes,
replayed into a fresh base world. No model is called; a replay costs nothing and is the same
every time, which a video needs.

    saturday.py   the steps: said, host code, and for the answer steps the question asked
    trace.py      replays the steps into a base world and dumps, after each step, what the
                  record holds: entities, links with their periods, what was superseded, open
                  questions, the code that ran — results/trace-<commit>.json
    views/        one HTML page per variant, each reading only the trace

## Variants

- **A. Chat and graph.** The conversation on the left, the world's graph on the right; a step
  adds nodes and links, a superseded link fades, an open question pulses on what it is about.
- **B. Said → record → image.** Three columns: the sentence, the statements it became (with
  their source), the objects assembled from them. Shows that the world formalises, not stores.
- **C. Timeline.** The links laid on time: who is free when, what happened last time, what
  holds now. The demo's question is a question about time.
- **D. Two worlds.** The research world of candidates beside the person's world; criteria flow
  from the person's world into the filter, and only the choice and why cross back.
- **E. Host code.** The script the host ran, with each line lit as the world answers it.

## What would count as an answer

To be agreed before the first run.

## Runs

None yet.
