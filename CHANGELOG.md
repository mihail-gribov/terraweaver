# Changelog

Versions follow [Semantic Versioning](https://semver.org): `MAJOR.MINOR.PATCH`.

- **PATCH**: a fix; behaviour the docs describe stays the same.
- **MINOR**: something added or changed that a user of the memory notices (a new route, a new rule
  of reading or searching), without breaking what they hold.
- **MAJOR**: a change that breaks a journal, the plugin's contract with the server, or a door
  (`say`, `ask`).

The number lives in `memory/__init__.py` (`__version__`) and in the plugin's `plugin.json`;
`tests/test_version.py` fails when they differ. A release is a git tag `v<version>` on `main`, and
its section below. Change the number in the same commit that changes the behaviour, not later.

## 1.0.0 — 2026-10-30

The submission for the Nebius × NVIDIA Global AI Hackathon, Personal AI track.

- Two doors over MCP: `say` (hooks pass every message of the conversation) and `ask`.
- The intake: a gate, a rewrite that makes a message stand alone from the agent's message before it,
  the user's questions kept as interests.
- A journal in plain Markdown, and a graph read from it in the background: entities, links, topics in
  dated layers, the user's world.
- Search by words and meaning, fused; embeddings local (`fastembed`) or an NVIDIA Nemotron model
  through OpenRouter.
- Topics kept fresh from the web (Tavily): a topic without a web update for a month, hourly at most,
  skipped once the user has not come back to it for three months.
- A Claude Code plugin with the hooks; the scenarios benchmark (43 of 45) and the demo replays.
