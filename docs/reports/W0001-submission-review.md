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

---

## 2. Consistency — where a module breaks the conventions the rest follows

### 2.1 MEDIUM — Names of the thing: "world", "baseline", "proto", "terraweaver", "memory"
- `memory/journal.py:1-17` "The baseline world … Nothing here imports terraweaver"; `memory/models.py:1-10` "the models the world works with … Every client is `terraweaver/nemotron.py`" (no such path); `memory/solve.py:33` "You are the world"; `memory/tools.py:1`, `memory/model.py:1-17` (an agent-facing API — `entity`, `event`, `same`, `different` — that no agent calls any more); `MCPServer("personal-world")` `journal.py:39`; `memory/__init__.py:4-10` lists seven modules and omits nine (`solve`, `tools`, `programs`, `parse`, `model`, `cleaner`, `ttl`, `refresh`, `trace`); README's diagram box "world: things · values · links" names the engine removed in `063818d`.
- **Why.** A reviewer reads the docstrings first; they describe two earlier systems. **Fix.** One pass over module docstrings: the thing is "the memory"; `__init__.py` lists every module in one line each; README diagram: "graph: topics · portraits · the user's world".

### 2.2 MEDIUM — Error handling: 29 broad `except Exception`, each with its own direction
- Model unreachable → `confirm_forget` returns **True** (`server.py:49-50`, "the reader's choice stands"), `_sort` returns **0.0** (`listen.py:272-277`, "unanswered is not a search"), `about(WORTH)` returns **1.0** (`graph.py:447-449`, "read it"), but `parts_of` returns **0.0** (`graph.py:491-493`, "unasked is not a part"), `holds` **0.0** (`parse.py:76`), `_useful` **False**, `chance_that` **0.0**, `goes_on` **1.0 or 0.0 by entries** (`graph.py:933-935`), `_beat` **pass** (`server.py:111`, S110). Every one is annotated `# noqa: BLE001` with a reason, which is good practice; what is missing is one stated rule. Suggested rule, already followed by most: *when a model cannot be asked, keep and do not act* — so `confirm_forget` should return False (an unconfirmed entry is not taken out; the user's confirmation step still follows, but this is the one place the fallback leans toward deleting). Put the rule in `docs/decisions.md` and make `server.py:50` follow it.
- `journal.py:269` re-raises without `from` (B904); `solve.py:197` catches everything around `exec` of model-written code (see §3.9).

### 2.3 MEDIUM — Tests: one convention, five copies, one exception
- `check()` is defined in `tests/test_graph.py:18`, `test_intake.py:18`, `test_journal.py:19`, `test_listen.py:20` (same body) and `test_nemotron.py:17` (two parameters, no detail); `tests/test_refresh.py` uses bare `assert` and its own `for name, f in globals()` loop, so a failure there shows as a traceback, not a `FAIL` line, and `--only`/`--live` conventions do not apply. `tests/test_journal.py:4-5` docstring still names `tests/test_baseline.py`. `tests/test_intake.py:85` uses a path relative to the cwd (`experiments/results/13_dialogues`), silently skipped from another directory. Module-level code in `test_nemotron.py` runs at import.
- **Fix.** Either one `tests/common.py` with `check`/`failures`/`main(checks)` (deletes ~60 lines) — or pytest with `-m live` for the model-backed cases, which `run_all.py` then becomes `pytest -q`. The hand-rolled runner is a stated choice (`run_all.py:3-5`); the exception is `test_refresh.py`, which should at least use `check`.

### 2.4 MEDIUM — Logging and printing
- Logger names in two styles: `"listen"`, `"baseline"` vs `"memory.graph"`, `"memory.refresh"` (`listen.py:34`, `journal.py:37`, `graph.py:46`, `refresh.py:26`). `solve.run` **prints** the program text, its output and the answer to stdout (`solve.py:167, 211, 227`) while running inside the server process on a worker thread — the server's stdout becomes the solver's console; `Tools(log=print)` and `cleaner.clean(log=print)` default to `print` too. `journal._token_factory` logs token counts at INFO per call (`:241`), Nemotron logs none (writes a file instead).
- **Fix.** `log = logging.getLogger(__name__)` everywhere; `solve`/`tools`/`cleaner` log at INFO/DEBUG; `print` only in `main()` functions.

### 2.5 LOW — Timestamps in four shapes, all naive
- `"%Y-%m-%d %H:%M:%S"` (`journal.py:325`, `trace.py:25`, `listen.py:117, 251`), `isoformat(timespec="seconds")` (`journal.py:452`, `programs.py:91`, `refresh.py:135`), `isoformat(timespec="minutes")` (clients), `datetime.now().date().isoformat()` (`tools.py:477`). Every `datetime.now()` is naive and compared with days the agent told (`graph.py:923`). Choose `isoformat(timespec="seconds")` and one `now()` helper in `memory/trace.py` or `memory/__init__.py`.

### 2.6 LOW — The `source` of an entry
- `"the user"` (`listen.py:293`), `"conversation"` (`journal.py:289, 297`), `"forget"` (`journal.py:436`), a URL or `"text"` (`parse.py:176, 180`), `"world"` session (`tools.py:99`). Readers key on `heading.endswith(" · forget")` (`journal.py:402`). Make the set explicit: `SOURCES = ("the user", "forget")` and drop the rest with §1.3.

### 2.7 LOW — Half-injected dependencies in `Listener`
- `listen.py:63-65` takes `base` **and** `keep`, `context`, `ask` (which are `base._keep`, `base.context`, `base.ask`), then calls `self.base._read`, `self.base._entries`, `self.base._memory`, `self.base.choose_forget`, `self.base.take_forget` directly (`:217, 462, 465, 481`). Tests stub some through the parameters and some through the module. Pass `base` only (or a small protocol class) and drop the three callables.

### 2.8 LOW — Configuration: two prefixes, two names for one thing, four `var/` roots
- `TERRAWEAVER_*` (server side) vs `PERSONAL_*` (plugin side); `--name` (`server.py:194`) vs `--memory` (`solve.py:257`, `cleaner.py:43`) for the same directory; `var/baseline/`, `var/memory/`, `var/solve/`, `var/programs/`. `TAVILY_API_KEY` is required by default but never checked at start (see §4 B10). A `memory/config.py` with a frozen dataclass read once from `os.environ` and argparse.

### 2.9 LOW — Style drift: line length, one-letter names, `wait` that is never read
- No lint config in the repository; 29 lines over 120 chars in `graph.py`, 17 in `tools.py`; `l` as a variable name 48 times (E741, 25 in `graph.py`), ambiguous beside `1`. The `wait` parameter is threaded through `Listener.say`, `_heard`, `ask`, `_gather` (`listen.py:86, 106, 123, 134, 443`) and `server.http_say:124` and never read: the hook's "answers at once" is true because `say` never gathers, not because of `wait`. Delete it. Add `[tool.ruff]` with `line-length = 120`, `select = ["E", "F", "B", "UP", "I"]`.

---

## 3. Modern Python (3.13) — what a 2026 reviewer flags

### 3.1 MEDIUM — No `pyproject.toml`; the package is reached through `sys.path` hacks
- `requirements.txt` lists `mcp`, `openai`, `fastembed`; the code imports `numpy` (`search.py:76`, `listen.py:386`), `uvicorn` and `starlette` (`journal.py:30-34`, `server.py:120…`) directly — transitive dependencies relied on without a pin. No `requires-python`, though the code uses 3.10+ syntax throughout and the ticket says 3.13. `sys.path.insert(0, …)` in six tests, `scripts/replay.py:19, 23`, `benchmarks/scenarios.py:33`, `experiments/14_longmemeval/run.py`. No lint/format config.
- **Fix.** A 25-line `pyproject.toml`: `[project]` with `requires-python = ">=3.13"`, the six dependencies, `[project.scripts] memory-server = "memory.server:main"`, `[tool.ruff]`; `pip install -e .` and delete the nine `sys.path` lines.

### 3.2 MEDIUM — Records are `dict`s with string keys; two dataclasses in the whole package
- Mentions, links, topic versions, portraits, aliases (`graph.py`, read as `l["from"]`, `t["entries"]`, `r["of"]` in ~40 places), jobs and interests (`listen.py`, `job["future"]`, `j["asked"]`), web rows (`refresh.py`), programs' runs (`programs.py`), page dicts (`tools.py`). Typed: `intake.Read` (dataclass), `graph.Part` (NamedTuple), `benchmarks.longmemeval.Session/Instance` (dataclasses). Wrong annotation: `graph.py:500` `_keep_reading(...) -> None` returns `(links, versions)` (`:584`). Callables typed as `None` defaults (`reader=None`, `embed=None`, `decide=None`, `progress=None`, `judge`).
- **Fix.** `TypedDict` for what is read from JSON lines (`Link`, `Mention`, `TopicVersion`, `Portrait`, `WebRow`) — zero runtime change, catches the `-> None`; `@dataclass(slots=True)` for `Job`/`Interest` in `listen.py`; `Callable[[str, dict], float]` on the injected functions.

### 3.3 MEDIUM — asyncio and threads mixed, with blocking work on the loop
- The MCP server runs on an event loop; the graph reads on a daemon thread (`graph.py:347`), the refresher on a thread per topic (`refresh.py:117`), gatherings on a thread (`listen.py:327`) bridged with `concurrent.futures.Future` + `asyncio.wrap_future` (`:451`); `ThreadPoolExecutor` in `graph.py:494, 646`, `parse.py:130`, `programs.py:71`, `tools.py:564`; `threading.Lock` taken on the loop (`listen.py:120, 340`; `graph.rebuild()` from `server.forgot:34`). `journal.writing` is an `asyncio.Lock` and protects nothing written from threads (`tools.Journal.keep`).
- **Blocking:** `journal._for` (`:143-149`) calls `narrow` = `Search.find` synchronously inside `async def context/ask/search_memory` (`:278, 341, 355`): BM25 over every entry plus a fastembed query embedding, and on the first call the ONNX model load (seconds), run on the event loop — every concurrent request stalls. `Graph.recall` is wrapped in `to_thread` (`listen.py:173`), the search is not.
- **Fix today.** Make `_for` async and `picked = set(await asyncio.to_thread(narrow, question))` (3 lines). Later: one rule — model and CPU work in threads, state changes on the loop — and `asyncio.Lock` only where every writer is a coroutine.

### 3.4 MEDIUM — Module-level mutable globals as the configuration surface
- `journal.py:50-54, 135-140, 368-371` (`facts`, `model`, `narrow`, `graph_facts`, `graph_recall`, `on_forget`, `confirm_forget`, `_nebius`, `keep_forgotten`) patched by `server.main` and by tests; `global` in `server.py:192`, `journal.py:231, 534`, `trace.py:18` (6 × PLW0603); `models._held`; `search`/`graph`/`listener` module globals in `server.py:24-25, 57`. The tests show the cost: `tests/test_listen.py:82-96` has to set four module attributes before constructing a `Listener`.
- **Fix.** A `Journal` class holding `facts`, `narrow`, hooks (constructed once in `server.main`, once in `journal.main`); `trace.Trace(path)` instance; `server` state in a small `App` dataclass. This is the same change as §1.4.

### 3.5 MEDIUM — Dead code (a reviewer sees it before anything else)
- `tools.py:496-512` `_known` imports `memory.world`, which does not exist: **(verified)** every task logs `the image could not be read (ModuleNotFoundError…)` and takes the fallback; `tools.py:626-655` `_from_image` and `_image_used` are therefore unreachable. `model.py`: `heard`, `check_heard`, `forget_heard`, `heard_candidates`, `settle`, `_ask_who`, `forgot`, `namespace`, `asked`/`kept` lists, `_sentences`, `_specifics`, `_STARTERS`, `_bare_number`, `_same_name` — no caller outside the file (~170 lines). `nemotron.py:249` `Reader = Nemotron`; `Nemotron.tfu/scale/answer/ask` (the "Jev shape", `:200-245`) unused in the product; `nemotron.MODEL`/`TERRAWEAVER_DECISION`; `journal.questions` tool (`:470-474`) and the `claude` CLI path (`:249-271`) on the memory server; `server.http_say` reads `source` (`:122-123`) which `listen.say` drops; `Listener.say(wait=)` (§2.9); `experiments/` holds one runner that depends on `benchmarks/` by path. ruff: unused imports `parse.py:21` (`sys`), `parse.py:23` (`Path`), `tools.py:24` (`asyncio`); `tools.py:331` f-string without placeholders.
- **Fix today.** Delete the `tools.py` dead branches (also §1.1) and the three unused imports; `ruff check --select F --fix`. The rest with §1.1.

### 3.6 LOW — 39 imports inside functions
- `server.py` 14, `listen.py` 13 (`json` ×3, `concurrent.futures.Future` ×2, `memory.models.role` ×5, `memory.graph.LOOKING`, `memory.intake.intake` ×2, `numpy`), `search.py` 2, `nemotron.py` 2, others 1 each. Justified: `fastembed`, `numpy`, `openai` (heavy, optional in tests), `starlette.responses` if the intent is to keep the module importable without the server. Not justified: `json`, `Future`, `role`, `LOOKING`, `WINDOW`, `Read`/`read`. The `role` imports exist so tests can patch `memory.models.role` after import (`tests/test_listen.py:109`) — inject the judge into `Listener` instead (§2.7) and import at the top.

### 3.7 LOW — Module size
- `graph.py` 1,024 lines: one class with 40 methods, a 70-line prompt, the `PARTS` table, and the recall formatting. `tools.py` 749 (object model for programs + Tavily + Shelf + ranking). `journal.py` 601 (prompts, file format, model clients, MCP tools, HTTP routes, bearer-token auth, CLI). Suggested cuts: `graph/{parts.py (PARTS, GROUPS, CLASSES, Part), store.py (load/append/index/rebuild), reading.py (_read_next, _keep_reading, _classify, prompt), world.py (world_of, _filled, world_lines), recall.py (recall, facts_for, _known_of)}`; `journal.py` → library + `baseline.py` (§1.4); `tools.py` goes with §1.1.

### 3.8 LOW — Typing and syntax details
- `from __future__ import annotations` only in `nemotron.py:22`, unneeded on 3.13; `typing.Callable` (`model.py:22`) → `collections.abc.Callable` (UP035); `zip()` without `strict=` 11 × (B905; the pairs in `graph.py:495, 497` and `parse.py:132` are length-coupled by construction, so `strict=True` documents it); `hasattr(self, "_used")` lazy attribute (`tools.py:111`) → set in `__init__`; `sys._getframe` walk to name the calling step (`nemotron.py:51-57`) — pass `step=` or use a `contextvars.ContextVar` set by the caller; `open(...)` instead of `Path.open` in `intake.py:173`, `nemotron.py:61`, `programs.py:90, 113`; `glob.glob` in `sources.py:40` → `Path.glob`. `pathlib` is otherwise used consistently and well.

### 3.9 MEDIUM — `exec` of model-written code with full builtins
- `solve.py:196` `exec(compiled, dict(namespace))`. The system prompt asks for "nothing but Python's standard library" (`:54`) and the error hint says "the program has these names and no others" (`:200`), but nothing enforces either: `import os, shutil` works, and the retry prompt (`:215`) feeds the model text that came from web pages (`printed` includes what `parse` read), so an injected page can steer the rewrite into code that runs on the user's machine next to the journal. No timeout on the program either (a `while True` blocks the gathering thread and the agent's `ask` forever).
- **Fix.** Smallest: `exec(compiled, {"__builtins__": SAFE_BUILTINS, **namespace})` with `SAFE_BUILTINS` = builtins minus `__import__`, `open`, `exec`, `eval`, `compile`, `input`, `breakpoint`; pre-import `datetime`, `re`, `json`, `math` into the namespace since programs need them. Better: a subprocess with `timeout=`. Or §1.1, which removes the program altogether.

### 3.10 LOW — The secrets filter is broad, and what it drops is gone for good
- `listen.py:45-49`: `[A-Za-z0-9_\-]{32,}` and `(?:\d[ -]?){13,19}` and `pin … is …`. **(verified)** it withholds an ISBN-13, a 32-character URL path segment, any hyphenated phrase of 32+ characters, and "the bowling pin is red" → "the bowling [withheld]". Withheld text never reaches the journal, so the user's fact is lost without a trace of what it was (only "A secret in it was withheld"). Keep the filter, but anchor it: require the long token to be preceded by `=`, `:`, a quote or a space (not `/`), and drop `pin` or require `\bPIN\b` case-sensitive.

---

## 4. Correctness bugs, most severe first

### B1 HIGH (verified) — The memory's notes never reach the agent under the plugin
- `memory/listen.py:92-94`: `say()` takes every pending note (`take_notes()`) at the top of **every** call, including a call carrying only the agent's reply. The plugin's Stop hook posts the reply after every turn (`adapters/claude_code/plugin/hooks/reply_hook.py:44`) and discards the response. **Scenario:** user message → topic is volatile → reply says "Looking on the web" (`graph.py:953`) → agent replies to the user → Stop hook `say(agent)` → 30 s later the refresher's `tell` queues "Found what matters" (`refresh.py:143-147`) → next Stop hook (or the `/notes` poll) drains it into a discarded response → the user's next message gets nothing. Same for `Listener._start`'s "Asked of the memory before" (`listen.py:322-324`). The whole "told with the memory's next answer" design (`refresh.py:9-10`, `decisions.md` 2026-10-30) is dead in the plugin; it works only in `benchmarks/scenarios.py`, which never posts agent-only calls between messages.
- **Fix (1 line).** `remembered = self.take_notes() if any(str(m.get("role") or "user").lower() == "user" and (m.get("text") or "").strip() for m in messages or []) else []`.

### B2 HIGH (verified) — The web-query privacy guard is a no-op
- `memory/tools.py:517-530`: `_private()` reads `self.memory.things()` → `var/memory/<name>/structure.jsonl`, which the server never writes (§1.2). On a server-made memory holding "My wife Mila … My manager Olga is at Lumen", `_private()` is `set()` and `web.search_pages("concerts Mila Olga Lumen Belgrade")` is not refused. README ("a web query that names a person from the memory is refused") and `tools.py:12` state the opposite. The refresher relies on the prompt alone (`refresh.py:41-42`).
- **Fix (≈6 lines).** `server.solve()` passes `names = {e for e, k in graph.kinds.items() if k in ("person", "organisation", "organization", "company")}` into `solving.run(..., private=names)` → `Tools(private=…)`; `_private()` returns that set (plus the people the user's `PARTS` links name, `graph._filled(USER)`). Apply the same check in `Refresher._refresh` before calling `self.search`.

### B3 HIGH (verified) — The baseline's write and debug routes are live on the memory server
- `memory/journal.py:484-531` registers `/tell`, `/add_memory`, `/forget`, `/search_memory`, `/context`, `/forgotten`, `/questions`, `/debug/facts`; `memory/server.py:130-131` removes only `/ask`. `/tell` writes without the gate, the rewrite or `SECRETS` (`listen.py:149`); `/forget` forgets with no confirmation (`listen.py:461-482` is bypassed); `/debug/facts` returns the whole journal. On localhost any process can call them; on `--host 0.0.0.0` anyone with the bearer token. **Fix (1 line)** after `server.py:131`: keep only `{"/say", "/ask", "/interests", "/world", "/settle", "/notes", "/health"}`. Properly: §1.4.

### B4 MEDIUM (verified) — Duplicate entry numbers and ungated text in the user's journal
- `memory/tools.py:406-408` `UserMemory.add_from_texts` → `parse.keep` → `Structure.said` → `tools.Journal.keep` (`:77-83`) appends to the user's `facts.md` with a number computed from entries loaded when the task began. Server keeps `#3` during the task; the program writes a second `#3`. `forget #3` then takes the wrong one or both; `search.drop`, `graph.read_upto` and the vectors key on the number. The text (a web page's claims about a named person) enters the journal with `source=<url>`, outside the gate and the secrets filter. **Fix:** delete `add_from_texts` from `UserMemory` (the manual stops advertising it automatically).

### B5 MEDIUM — `forget` does not reach `heard.jsonl`, `trace.jsonl`, `interests.jsonl`
- `take_forget` (`journal.py:416-442`) empties the entry from `facts.md` and the hooks drop vectors and rebuild the graph (`server.py:28-35`). Nothing touches `heard.jsonl` (every message as heard, agent replies included, `listen.py:111-121`), `trace.jsonl` (`gate.said`, `kept.text`, `recall.gathered` carry the full text, `listen.py:153, 294, 221`), or `interests.jsonl`. **Scenario:** "forget everything about Mila" → confirmed → `grep -c Mila var/memory/main/{heard,trace}.jsonl` still finds every sentence, for ever. `trace.py:6` says "Secrets never reach it"; forgotten facts do. The agent's replies, which the design says are "never kept" (`listen.py:19-21, 99-102`), are kept verbatim in `heard.jsonl` with no way to remove them.
- **Fix.** In `server.forgot`, rewrite the three files dropping lines whose `entry`/`kept.entry` is among the taken numbers or whose text contains a taken entry's text; or make both logs opt-in (`--trace`) and say so in the README's privacy paragraph. At minimum, say it in the README today.

### B6 MEDIUM — `graph.rebuild()` races the reader and loses the web layers
- (a) `server.forgot:33-34` calls `rebuild()` (deletes every graph file under the lock, `graph.py:404-411`) while the worker thread may be between `self.reader(...)` and `_keep_reading` (`graph.py:463-473`, outside the lock). The worker then appends mentions/links/topics for entry *n* to the fresh files and sets `read_upto = n` (`:480-482`) → entries 1…n−1 are never re-read until another rebuild. `self._vectors` is not cleared either (`:341`), so cached topic vectors keyed `(topic_id, version)` now describe other topics (ids restart at 1).
- (b) Layers added by the refresher (`refresh.py:141-142` → `add_to_topic`) exist only in `topics.jsonl`, which `rebuild` deletes; they are not in the journal, so they are not rebuilt. `web.jsonl` survives with topic ids that now point to different topics, so the 7-day stale check (`refresh.py:101-103`) is applied to the wrong topic.
- (c) Cost: one forgotten entry re-reads every entry through three models (judge WORTH, judge parts, reader) — at 300 entries, hours, while `facts_for` waits on `self.wait()` (`graph.py:869`).
- **Fix.** Today: a `self.generation` counter incremented in `rebuild`; `_read_next` discards its reading when the generation changed; clear `_vectors`; have `_load` re-apply `web.jsonl` rows with `kept: true` by topic **name**. Later: drop only rows whose `text`/`entries` include the taken numbers and re-read just those entries' dialogue.

### B7 MEDIUM — A pending forget is dropped silently
- `listen.py:471-480`: `_confirm` sets `waiting_forget = None` before asking; on p < 0.5 it returns `""` and the message proceeds normally. **Scenario:** memory proposes entries → agent asks the user → user writes "wait, which ones were about her flat?" → hook passes it → judge says not a confirmation → proposal gone, no word → user says "yes, go ahead" → kept as an entry ("yes, go ahead" after an agent message is rewritten and may pass the gate), nothing forgotten. **Fix:** keep `waiting_forget` unless the judge says the user declined (a second `noul` "did the user say not to?"), and when it is dropped, return "The forget was not confirmed and is dropped; ask again to forget."

### B8 MEDIUM — `_purge` rewrites the bin from every thread; a forgotten entry can vanish from both file and bin
- `journal.py:128-130`: `_memory()` calls `_purge()`, which reads the bin, filters, and **rewrites** it (`:161-168`) whenever any binned row is older than `keep_forgotten`. `_memory()` is called from the graph thread (`server.py:222` → `graph.py:440`, on every reading and every `recall`), from `Search.entries` on the loop and in `to_thread`, and from `take_forget` on the loop. **Scenario:** one row in the bin is 31 days old; the graph thread is inside `_purge` (has read, has not written) when the loop runs `take_forget` → `_to_bin` appends the new row (`:445-452`) → the graph thread writes its filtered list → the appended row is gone, and `facts.md` was already rewritten without the entry: the entry is nowhere, the case `:426-427` says cannot happen. **Fix:** purge once at startup and once per day from the loop (or inside `writing`), never in `_memory()`; also saves a file parse per call.

### B9 MEDIUM — Token usage is undercounted
- `journal._token_factory` (`:236-243`) and `solve.py:178` bypass `nemotron._spent`, so `TERRAWEAVER_USAGE`/`scripts/usage.py` and the shares in `docs/decisions.md` omit `ask` (thinking, 12 k tokens), `context`, `FIT` and the programmer's call — the largest calls. **Fix:** §1.5.

### B10 MEDIUM — Search runs on the event loop
- `journal._for:148` → `Search.find` → `by_meaning` → `_embed`/`_encoder()` (`search.py:94-114`): the first call loads the fastembed ONNX model on the loop; every call runs BM25 over all entries there. Every other coroutine (the hook's `/say`, `/notes`, MCP) stalls. Concurrent `Search._embed` from the loop and the graph thread also both see the same new entries as "todo" and both append them to `vectors.jsonl` (duplicates; harmless on reload). **Fix:** §3.3 (3 lines), and a `threading.Lock` around `_embed`.

### B11 MEDIUM — `TAVILY_API_KEY` is never checked; the default engine then fails per topic
- `server.py:205` checks `NEBIUS_API_KEY` only; `tools.tavily:50` raises `KeyError` at search time, caught in `refresh.py:149-152`. With the default `--engine tavily` and no key, every volatile topic tells the agent "Looking on the web" and then "failed; nothing was found", and every `ask` with "find" goes through the whole programmer round-trip to fail at the first search. **Fix:** at start, `if args.engine == "tavily" and not os.environ.get("TAVILY_API_KEY"): raise SystemExit(...)` or set `args.engine = "off"` with a warning.

### B12 LOW (verified) — A user message containing `## #` truncates the kept entry
- `listen.py:149` collapses whitespace but keeps the text; `journal._keep:325` appends it; `_entries:174` splits on `"## #"`. A pasted note "here is my note: ## #1 Fix the login bug ## #2 Ship it" is kept and read back as entry text "here is my note:" — the rest is unreadable to every reader and the graph. Claude Code users paste markdown. **Fix:** parse with a line-anchored regex `^## #(\d+) · ` (`re.MULTILINE`) and escape `"## #"` → `"## \#"` on write, or store one JSON line per entry.

### B13 LOW — `recall` decides "the dialogue is over" by the machine clock
- `graph.py:921-924` compares `datetime.now()` with the last entry's told day. When the agent passes `now` (benchmarks, demos, a hook with a date), the last dialogue is always "over", so the current talk's topics are not among the sure candidates. **Fix:** pass `now` from `Listener._heard` into `recall(message, numbers, now)`.

### B14 LOW — A forget request in a message drops the message's other content
- `listen.py:155-157` returns after `_prepare_forget` whenever a `memory` request is found: "Mila moved to Porto, and please forget her old number" keeps nothing of the move, and any `know` question in it is not kept as an interest. **Fix:** fall through after appending the proposal.

### B15 LOW — Gathering delivered twice (theoretical race)
- `listen.py:298-328` starts the thread before `_gather:450` marks the job delivered; if `_solve` raises at once (missing key, bad path), `work()` both sets the exception (returned to the agent) and queues a "Looking into … failed" note. **Fix:** `job["delivered"] = True` in `_start` when `by == "agent"`, before starting the thread.

### B16 LOW — `refresher` referenced outside the branch that defines it
- `server.py:229` defines `refresher` only when `--engine` is not `off` and the graph is on; `:249` reaches it through a `getattr` guard. Works, but a change to either condition raises `UnboundLocalError` at startup. Define `refresher = None` before the branch.

### B17 LOW — `http_say` reads a `source` it drops; `say` advertises `now` the HTTP hook never sends
- `server.py:122-123` builds `{"source": …}` which `listen.say` ignores; `context_hook.py:32` never passes `now`, so every entry kept through the plugin is dated by the server's clock, which is right only while the hook runs on the same machine. Drop `source`; have the hook send `now`.

### B18 LOW — Lambda in a loop binds late (`graph.py:536-537`)
- `animal = lambda e: … to … l["quote"]` captures loop variables (B023). Harmless today because it is called inside the same iteration (`:538`), but a later use outside the loop would read the last link. Pass `to` and `quote` as default arguments.

---

## How the review was done

Read every file under review; ran `tests/run_all.py` (6/6); ran `ruff check --select F,B,UP,E7,E9,PLW0603,PLC0415,S110,BLE001` over `memory adapters scripts benchmarks tests` (3 unused imports, 1 placeholder-less f-string, 1 unbound-loop lambda, 6 `global`s, 39 imports in functions, 48 `l` names, 11 `zip` without `strict`); reproduced B1, B2, B3, B4, B12 and the dead `memory.world` import offline with stub models (script kept out of the repository). `benchmarks/runs/` and `docs/` were read only as the record of why.
