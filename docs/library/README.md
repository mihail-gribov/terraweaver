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
