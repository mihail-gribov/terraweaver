# Library

Papers kept locally because we refer back to them. One line per paper: file, what it is, why it is here.

- `2609.15779-evoontology.pdf` — Chong, Zhang, Fan, Du (Renmin U.), *EvoOntology: A Self-Evolving
  Ontology Layer for Data Agents*, arXiv 2609.15779, 14 Sep 2026. Code: https://github.com/ruc-datalab/EvoOntology.
  An ontology served as an MCP server (schema / content / tool layers) that a data agent queries at
  runtime; a builder agent grounds every entry in a probe query; an evolution loop makes typed,
  single-level edits (content, tool or schema) and keeps one only if a paired evaluation on a
  held-out set, same backbone and budget, beats the parent by a margin. Kept for: the acceptance
  gate as the model for our crystallisation step (a recurring shape becomes a type only if the host
  answers better with it), the finding that reshaping how the ontology is exposed (tool layer)
  gave 57% of the gain, the evidence that a static semantic layer pasted into the prompt hurts
  (−15 pts on Claude-Sonnet-5) while the same content behind tools helps, and the episodic-memory
  baseline (+6.3) losing to typed structure (+20.0) — a citation for docs/landscape.md.
- `Harness as a Language- A Minimalist Agent Framework With Maximal Expressivity.pdf` — Li, Liu,
  Vukelic et al. (MIT CSAIL), arXiv 2609.26891, 22 Sep 2026. Code: https://github.com/jaz-lang/jaz.
  JAZ: one primitive `invoke`, a code-mode agent loop with recursive subagents where everything the
  model sees (prompt, tools, its own REPL history `__history__`) is a REPL variable. Prompt-only, it
  beats Letta on StuLife far recall (70% vs 62%, half the cost) by delegating to a subagent with the
  full history passed by reference and grepping it; beats ACE on AppWorld self-improvement (74% vs
  70%). Read 2026-09-27; changes nothing for us. Kept for: the ablation (same loop without prompt
  and history as variables: 70% → 32%) as measured support for our host API rule that the host
  works with variables, not name strings; the evaluation protocol in App. C.1 (prompt split into
  method-agnostic `instructions` and task-agnostic `guidance`, n=3/6 runs with SE, cache control
  when measuring cost). Not applicable: its "pass by reference, don't paraphrase" lesson — the
  host's retelling is what resolves "she" and "this city" for the world; and its "memory emerges
  from the loop" thesis is about the agent's inside — we are an extension the agent calls, and
  such an agent is a possible host whose in-episode history does not outlive the episode.
