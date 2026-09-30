# Development setup

Everything needed to get the development environment back after a reboot.

## Quick start

    cd ~/Projects/terraweaver
    scripts/dev.sh start        # world server (LAN, 7000) + MCP Inspector (7001)
    scripts/dev.sh status
    scripts/dev.sh stop

`start` prints the Inspector link with its token. Logs: `scripts/dev.sh logs` (files in `var/`).

## One-time setup

Prerequisites: [uv](https://docs.astral.sh/uv/), Node.js + npm (for the Inspector), the `claude`
CLI (for host scenarios), optionally Ollama (local embeddings).

    uv venv .venv
    uv pip install --python .venv/bin/python -r requirements.txt
    npm install -g @modelcontextprotocol/inspector
    scripts/patch-inspector.sh      # again after every Inspector upgrade

`.env` (not committed) holds the keys:

    NEBIUS_API_KEY=...     # Nebius Token Factory: Nemotron models and embeddings
    TAVILY_API_KEY=...     # later, for research

Nothing loads `.env` automatically. The world server and the scenarios don't need the keys yet;
the older exp01 experiments and direct Nemotron calls do — export them first:
`set -a; . ./.env; set +a`.

The LAN token for the world server is generated on first start into `.terraweaver-token`
(not committed), or taken from `TERRAWEAVER_TOKEN`.

## Ports

| Port | What |
|---|---|
| 7000 | World server, MCP at `/mcp` |
| 7001 | MCP Inspector web UI |
| 7002 | MCP Inspector sandbox |
| 7010–7029 | Scenario runs: one world server per run process |
| 11434 | Ollama (local models; its own default port) |

The machine's LAN address is detected automatically (`LAN_IP=... scripts/dev.sh start` to
override). Currently 192.168.1.39.

## World server

    .venv/bin/python -m terraweaver.server                   # localhost:7000, no token
    .venv/bin/python -m terraweaver.server --host 0.0.0.0 --allow-origin http://192.168.1.39:7001
    .venv/bin/python -m terraweaver.server --rebuild         # rebuild the world from its fixture

The world lives in `worlds/job_search.db`; an empty database is built from the `job_search`
fixture. `REBUILD=1 scripts/dev.sh start` rebuilds on start.

Bound to the LAN, every request except `/health` needs `Authorization: Bearer <token>`, or
`?token=<token>` in a browser URL. Debug endpoints:

    GET  /health
    GET  /debug/runs?limit=20&session=…     what hosts ran, saw and changed
    GET  /debug/sessions                    namespaces per session
    GET  /debug/export                      the whole world as plain JSON
    POST /debug/reset                       rebuild the world from its fixture

## MCP Inspector

Started by `scripts/dev.sh start`, bound to the LAN address and already pointed at the world with
the token and `x-terraweaver-session: inspector`. It is opened from other machines over plain
http, where browsers don't provide `crypto.randomUUID`; `scripts/patch-inspector.sh` adds a
polyfill (`tools/inspector-uuid-polyfill.js`). Without it the UI fails with "crypto.randomUUID is
not a function".

## Connecting Claude Code to the world

    claude mcp add --transport http terraweaver http://127.0.0.1:7000/mcp \
      --header "x-terraweaver-session: claude-code" \
      --header "Authorization: Bearer $(cat .terraweaver-token)"

The session header names the namespace; without it all windows of one client share one.

## Tests

No model needed; they need the venv (tldextract). All of them, one command, one process each:

    .venv/bin/python tests/run_all.py            # 27 scripts, about 20 seconds
    .venv/bin/python tests/run_all.py -q         # one line per script
    .venv/bin/python tests/run_all.py --only relations

A script counts as failed if it exits non-zero **or** prints a line beginning `FAIL` — several of
them report a failed check and still exit 0, which is how a loop over four of them used to read as
a passing suite. One script on its own is still just `.venv/bin/python tests/test_relations.py`.

## Host scenarios

A real agent (Claude Code) works on the world; see `scenarios/run.py` for the file format.

    .venv/bin/python scenarios/run.py s06                    # one scenario, world mode
    .venv/bin/python scenarios/run.py --baseline s06         # same, Claude Code on its own tools
    .venv/bin/python scenarios/run.py --model haiku --level hard
    scripts/compare.sh --model haiku                         # hard pool, both modes, in parallel

Each run starts its own world server with a throwaway database, so the development world is
never touched. Results: `experiments/results/scenarios/`. One run measures nothing — repeat
before drawing conclusions.

## Local embeddings (optional)

    ollama pull qwen3-embedding:8b     # the same model as on Token Factory

Ollama serves an OpenAI-compatible `/v1/embeddings` on port 11434. For the contest, embeddings
come from Nebius Token Factory (`Qwen/Qwen3-Embedding-8B`).

## Older experiments

    .venv/bin/python run_scenarios.py        # exp01 agent in-process, Nemotron via Token Factory
    .venv/bin/python experiments/repeat_runs.py 3
