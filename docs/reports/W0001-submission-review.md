# W0001 — Submission review of `v1.0` (`15694aa`)

Review only; no production code was changed. Reviewed 2026-10-30 on branch `v1.0` at `15694aa`.
Suite: `python3 tests/run_all.py` in a fresh Python 3.13.17 venv from `requirements.txt` → **6 of 6 scripts pass in 7 s**.
Bugs marked **(verified)** were reproduced offline with stub models; the rest are read from the code with an exact scenario.

## Summary

**Fix before submitting today (each is a few lines):**
1. **Notes never reach the agent under the plugin.** `Listener.say` drains `notes` on every call, and the Stop hook's agent-only `say` discards the response (`memory/listen.py:92`, `reply_hook.py:44`). Every "Looking on the web … found" and every finished gathering is lost. Take notes only when a user message is in the call.
2. **Two promises in the README are not true on this branch.** The memory server still serves the baseline's `/tell`, `/add_memory`, `/forget`, `/debug/facts` (bypassing gate, secrets filter and confirm; `memory/server.py:130`), and the web-query privacy guard reads a store the server never writes, so a query naming Mila or Olga is not refused (`memory/tools.py:517`). Filter the routes; feed the guard from the graph's people.
3. **The restored solver reads a user memory that is always empty.** `Tools._known` imports the removed `memory.world` and falls back to `structure.jsonl`, which nothing writes: `user_memory.describe()` says "none", `the_user()` raises, and `user_memory.add_from_texts` writes duplicate entry numbers into the user's journal (`memory/tools.py:496`, `:406`). Delete `_known`/`_from_image`/`add_from_texts` and have `describe()` return the graph's world text.

**Can wait (after the deadline):** fold the two web paths into one (§1.1); split `journal.py` into library and baseline server (§1.4); one Nemotron client for every call (§1.5); make `forget` reach `heard.jsonl`/`trace.jsonl` (§4 B5); fix the rebuild race and the lost web layers (§4 B6); `pyproject.toml`, typed records, pytest (§3).

---

## 1. One way to do each thing — duplicated functionality and data paths

Ranked by how much they cost. For each: both places, which stays, what goes.

### 1.1 HIGH — Two web paths, two readers of pages, two stores for what was found
- **Where.** (a) `memory/refresh.py:64-155` — a topic the user comes back to is searched on Tavily (`tools.tavily`), the reader summarises the pages, the judge says whether it matters, the finding is a topic layer in the graph (`graph.add_to_topic`, `memory/graph.py:899`) and a row in `graph/web.jsonl`. (b) `memory/solve.py:110-231` with `tools.py`, `programs.py`, `parse.py`, `model.py`, `cleaner.py`, `ttl.py`, `classes.json` — the agent's `ask` with "find" ≥ 0.5 (`memory/listen.py:134-136`) runs a model-written program over `Shelf`/`Structure`/`Journal`, pages read by `parse.read`, findings kept in `var/memory/<name>/collections/<slug>/{facts.md,structure.jsonl,used.json}`, programs in `var/programs/`, runs in `var/solve/`.
- **Size.** The chain is 1,896 lines, 37 % of `memory/` (5,180 lines), with its own journal format parser, its own TTL and cleaner, its own structured store, and a program registry. `refresh.py` is 155 lines, tested (`tests/test_refresh.py`), and native to the graph. Nothing in the chain is tested.
- **What overlaps.** Searching (one shared function, `tools.tavily`, good), reading pages into facts (`refresh.FOUND` prompt vs `parse.READ` + decision-model checks), remembering what was found (topic layer vs `Shelf`), freshness (`refresh.STALE` 7 days vs `tools.FRESH` 3 days vs `ttl.TTL` 90 days), what to tell the agent (`Refresher.tell` vs `Listener._start` note), privacy of queries (`refresh.QUERIES` "never a name" by prompt vs `Tools._private` by code, see §4 B2). `--engine` is honoured by the solver (ait-search, `tools.py:531`) and ignored by the refresher (always Tavily, `refresh.py:67`).
- **Which stays.** The refresher's shape: question or topic → queries → Tavily → reader → judge → a layer in the graph, told with the next answer. The `ask` door keeps its "find" branch but calls that same function with the question as the topic text, and returns the finding (and keeps it as a layer when the judge says it matters).
- **What goes.** `solve.py`, `programs.py`, `parse.py`, `model.py`, `cleaner.py`, `ttl.py`, `classes.json`, and all of `tools.py` except `tavily()` (move it to `memory/web.py`, so `refresh.py` stops importing `model.py`/`parse.py`/`classes.json` for one function). Also `var/programs/`, `var/solve/`, `collections/`.
- **Today's smallest change** (the deletion above is too large for the deadline): remove `Tools._known`/`_from_image`/`_image_used` (`tools.py:496-512, 626-655`) and `UserMemory.add_from_texts` (`tools.py:406-408`); make `UserMemory.describe()` and `the_user()` read the graph (`graph.world_lines(USER)`, `graph.portrait_lines`) passed in from `server.solve()`; pass the graph's people to `Tools` for `_private()`. About 60 lines deleted, 10 added.

### 1.2 HIGH — Two structured stores of the user's memory in one directory
- **Where.** `var/memory/<name>/graph/` (mentions, links, topics, portraits, aliases, world.json; `memory/graph.py`) and `var/memory/<name>/structure.jsonl` + `collections/` (`memory/tools.py:101-102`, `memory/model.py:65`). The solver reads only the second (`tools.py:393-404`), which the server never writes. **(verified:** on a server-made memory `user_memory.describe()` → "kinds: none / values: none", `all_items("person")` → 0 items, `the_user()` → `StopIteration`, which the program loop reports as a failed attempt.)
- **Why it matters.** Every program is told "What the user's memory holds as structure: none" (`solve.py:153`) and cannot answer "who are my colleagues" from links, which is the solver's own example (`tools.py:4-5`). The graph already holds exactly that (`world_of`, `_filled`).
- **Keep** the graph. **Goes:** `structure.jsonl` for the user's memory and `model.Structure` as a view of it. Collections may keep their own files until §1.1 removes them.

### 1.3 HIGH — Three parsers and two writers of the `facts.md` format
- **Where.** `memory/journal.py:171-179` (`_entries`) and `:317-326` (`_keep`); `memory/tools.py:65-93` (`Journal.__init__`, `keep`, `drop`); `memory/model.py:268-276` (`heard_messages`). All split on `"## #"` and partition on `" · "` separately.
- **Why it matters.** `tools.Journal.keep` numbers from entries loaded at task start and appends to the same `facts.md` the server writes to, without the journal's lock or gate. **(verified:** server keeps #3 while a task runs, then `user_memory.add_from_texts(page)` writes a second `#3`.) Two entries with one number break `forget #3`, the graph's `read_upto`, and the vectors' keys. The page text also enters the user's journal unseen by `SECRETS` and the gate, with `source=<url>`.
- **Keep** `journal._entries`/`_keep`. **Goes:** `UserMemory.add_from_texts` (3 lines, closes the hole today); later `tools.Journal` and `model.heard_messages` with §1.1. If `Journal` must stay for collections, parse through `journal._entries(path.read_text())`.

### 1.4 HIGH — `journal.py` is both the baseline server and the memory's library
- **Where.** `memory/server.py:20` imports it as `base` and then patches module globals (`:213, :218, :224-225, :231`), removes every MCP tool at runtime (`:253-254`), replaces the instructions through a private attribute (`:255`), and removes one HTTP route by filtering another private attribute (`:130-131`). The other eight baseline routes stay registered: **(verified)** the memory server serves `/add_memory, /ask, /context, /debug/facts, /forget, /forgotten, /health, /interests, /notes, /questions, /say, /search_memory, /settle, /tell, /world`.
- **Why it matters.** `/tell` and `/add_memory` write to the journal with no gate and no secrets filter; `/forget` forgets without the user's confirmation; `/debug/facts` returns the whole journal; all reachable by any local process, and on `--host 0.0.0.0` by anyone with the token. The "two doors" of the README are two MCP doors over fifteen HTTP ones. Also two MCP server identities: `MCPServer("personal-world")` (`journal.py:39`) is the memory's server.
- **Keep** the journal functions (`_entries`, `_keep`, `choose_forget`, `take_forget`, `_read`, the prompts). **Goes:** the module-level `@server.tool()`/`@server.custom_route` registrations move into `def baseline(server)` called only from `journal.main()`, so `server.py` builds its own `MCPServer` and registers only `say`/`ask` and its six routes. **Today:** after `server.py:131`, keep only routes whose path is in `{"/say","/ask","/interests","/world","/settle","/notes","/health"}` — one line.

### 1.5 MEDIUM — Two clients to the same endpoint, two models configs, two usage logs
- **Where.** `memory/journal.py:228-246` (`AsyncOpenAI`, model from `--model`, logs tokens with `log.info`) and `memory/nemotron.py:104-116` (`OpenAI` per role, `_spent` writes `TERRAWEAVER_USAGE`). The reader model is set in `models.ROLES["reader"]` (`models.py:21`) and again as the `--model` default (`server.py:197`); `TERRAWEAVER_READER` changes one, not the other. `solve.py:178-183` calls `programmer.client.chat.completions.create` directly, bypassing `Nemotron.say` and `_spent` too.
- **Why it matters.** `scripts/usage.py` and the token shares quoted in `docs/decisions.md` ("reader 40 % of tokens") omit the memory's biggest calls: `ask` (thinking, `max_tokens=12000`), `context`, and `FIT` all go through `journal._read`. The `haiku`-via-`claude` path (`journal.py:249-271`) is dead in the memory server, which demands `NEBIUS_API_KEY` regardless (`server.py:205`).
- **Keep** `Nemotron`. **Goes:** `_token_factory`, `_nebius`, `_claude`; `journal._read` becomes `await asyncio.to_thread(role("reader").say, "", prompt, room=..., thinking=thinking)`; drop `--model` from `server.py` (roles are the config).

### 1.6 MEDIUM — Prompts kept two ways
- **Where.** `memory/intake/prompts/*.txt` with a README saying "every prompt, one file each", read by `intake.prompt()`; inline string constants in `listen.py:51-57, 487-504`, `graph.py:186-252`, `refresh.py:31-61`, `journal.py:60-106`, `solve.py:33-100`, `parse.py:27-60`.
- **Fix.** Pick one. The files are the better convention for a project that measures prompts (`docs/decisions.md` records prompt changes by date); move the inline ones under `memory/prompts/` and reuse `intake.prompt()`/`question()`.

### 1.7 MEDIUM — Program registry and run folders are global, memories are per name
- **Where.** `memory/programs.py:26` (`var/programs/`), `memory/server.py:240` (`var/solve/`), vs `var/memory/<name>/` for everything else. A program learnt on a demo or benchmark memory is proposed for `main` (`programs.find`, `:53-74`), and `cleaner.clean` expires all memories' programs on any task.
- **Fix.** `Programs(where / "programs")`, `out = where / "solve" / stamp` (two lines) — or §1.1.

### 1.8 LOW — Three cosine/embedding helpers
- `memory/search.py:76-79` (numpy dot over stored vectors), `memory/graph.py:703-706` (pure-Python cosine), `memory/listen.py:383-388` (numpy, normalised). Keep one `embed(texts)`/`cosine(a, b)` in `search.py`; graph and listener get it injected already (`server.py:223, :246`).

### 1.9 LOW — JSON-out-of-prose extracted four times
- `intake/intake.py:117`, `refresh.py:126`, `parse.py:105`, `solve.py:127` each do `json.loads(said[said.find("{"):said.rfind("}") + 1])` with different `except` lists; `Nemotron.json()` (`nemotron.py:140-149`) exists for this. Use it (or a `memory.nemotron.json_of(text)` where the call is not through `say`).

### 1.10 LOW — `_told` written twice
- `journal.py:309-314` and `listen.py:285-289` parse the agent's `now` the same way. Call `base._told`.

### 1.11 LOW — Same-question judgment in three places
- `intake/prompts/same_question.txt` (is the extracted question the user's), `listen.py:42` thresholds + `listen.py:413-416` inline prompt (is this a repeat), `programs.py:62-65` (same kind of task). Two share the name `SAME_QUESTION` with different meanings (`intake.py:52`, `listen.py:42`). Rename the listener's to `REPEAT`, `REPEAT_MAYBE`.

### 1.12 LOW — Client helpers copied across scripts
- `call()` + the 60-step wait-for-server loop + `ROOT`: `scripts/demo_recall.py:170-201`, `scripts/demo_world.py:50-97`, `benchmarks/scenarios.py:222-275`, `experiments/14_longmemeval/run.py:83`; a fifth `call` in `adapters/claude_code/plugin/hooks/common.py:28` (that one must stay stdlib-only). `ROOT = Path(__file__).resolve().parents[1]` appears in 10 files. One `memory/client.py` with `call(port, path, body)` and `wait_up(port)`; `ROOT` in `memory/__init__.py`.

### 1.13 LOW — Two environment variables for the decision model
- `nemotron.py:30` `TERRAWEAVER_DECISION` is only the default of `Nemotron(model=…)`, which `models.role` always overrides with `TERRAWEAVER_JUDGE` (`models.py:40`). Delete `MODEL`/`TERRAWEAVER_DECISION`.

### 1.14 LOW — Freshness as three constants
- `refresh.STALE` 7 d, `tools.FRESH` 3 d, `ttl.TTL` 90 d, `journal.keep_forgotten` 30 d, `listen.FRESH_JOB` 3 d ("as fresh as `tools.FRESH`", but a separate number). One `memory/limits.py` or keep two (how long a web fact holds; how long the bin holds) once §1.1 is done.
