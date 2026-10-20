"""The proto's things and sentences, said into a terraweaver world, and read there.

The proto settles which things there are (the agent's variables, `same`/`different`); what each
one is and what joins them is the world's to read, and it can: `portraits` reads a class from what
was said about a thing, `formalise` reads a typed link from the words said of two. So every entry
of the journal is said into a world beside it, through the host's own door (`runtime.run`, with
the things bound, never named):

    an entry about one thing     a.describe(text)
    an entry about two or more   world.relate(a, b, text), the first with each of the others

and the world's reading runs over it at a close (`read`), with the engineer and picker the server
gives itself. Which world entity is which proto thing, and which bare link came from which entry,
is kept in `mirror.json`: the structure finds, and the texts are still the answer.

    .venv/bin/python -m proto.world <run dir>      # mirror a run's journal, read it, print the image
"""
import json
import logging
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CORE = ROOT / "ontology" / "core"
KEY = "proto"
log = logging.getLogger("proto.world")
# The world's logs: what was run and what was read, where a forgotten thing's name is scrubbed too.
LOGS = {"runs", "readings"}
# Entries said in one run: a run is stopped after ten seconds.
CHUNK = 15


class Mirror:
    def __init__(self, where: Path):
        from terraweaver import authoring, ontology
        from terraweaver.runtime import WorldRuntime

        self.where = Path(where)
        self.where.mkdir(parents=True, exist_ok=True)
        specs = ontology.load_specs(CORE, grown_dir=self.where / "grown")
        self.rt = WorldRuntime(str(self.where / "world.db"), specs=specs, selves=False, home=self.where)
        authoring.install(self.rt.world, self.where / "grown")
        state = self.where / "mirror.json"
        held = json.loads(state.read_text()) if state.exists() else {}
        # proto group (its smallest thing id) -> world entity id; entry -> what it became
        self.entities: dict[str, str] = held.get("entities", {})
        self.said: dict[str, dict] = held.get("said", {})

    def _save(self) -> None:
        (self.where / "mirror.json").write_text(json.dumps({"entities": self.entities, "said": self.said},
                                                           ensure_ascii=False, indent=1))

    # --- saying ------------------------------------------------------------------------------

    def sync(self, structure, held: dict[int, str]) -> dict:
        """Say every held entry not yet said. Returns counts, and the errors the world gave."""
        groups = {}
        for t in structure._things().values():
            group = structure.one_with(structure.thing("q", t["thing"]))
            groups[t["thing"]] = min(group, key=lambda i: int(i[1:]))
        names = {t["thing"]: t["name"] for t in structure._things().values()}
        todo = []
        for r in structure.records:
            n = r.get("entry")
            # Not a request to forget: it is about the memory, not about its things, and read as
            # a fact it became "Bathroom exhaust fan —RequestedRemovalOf→ BrightFix" (C01).
            if r.get("as") == "forget":
                continue
            if n in held and str(n) not in self.said and r.get("about"):
                about = list(dict.fromkeys(groups.get(t, t) for t in r["about"]))
                todo.append((n, held[n], about))
        if not self.rt.sessions.get(KEY) or self.rt.sessions[KEY].task_id is None:
            self.rt.start_task(KEY, "record what the user's personal memory was told, entry by entry",
                               "recording")
        errors = []
        for i in range(0, len(todo), CHUNK):
            chunk = todo[i:i + CHUNK]
            bound, lines = {}, []
            session = self.rt.session(KEY)
            for group in dict.fromkeys(g for _, _, about in chunk for g in about):
                var = f"g_{group}"
                if group in self.entities:
                    # Bound as the thing itself, never found again by name: which one it is was
                    # settled by the proto, and identity read from words is what no pass repairs.
                    session.namespace[var] = self.rt.store.load(self.entities[group], self.rt.classes)
                else:
                    lines.append(f"{var} = Thing.identify(name={names[group]!r})[0]")
                bound[group] = var
            # Which entity each group is, printed before anything is said: a line that fails
            # later leaves the rest of the block in the world, and the mapping with it.
            lines.append("print(" + repr("|".join(bound)) + ", " +
                         ", ".join(f"{v}.id" for v in bound.values()) + ", sep='\\n')")
            for n, text, about in chunk:
                one = bound[about[0]]
                if len(about) == 1:
                    lines.append(f"{one}.describe({text!r})")
                else:
                    lines += [f"world.relate({one}, {bound[o]}, {text!r})" for o in about[1:]]
            got = self.rt.run("\n".join(lines), KEY)
            if not got.get("ok"):
                errors.append(str(got.get("error"))[:300])
            out = [line for line in (got.get("output") or "").splitlines() if line.strip()]
            if out and out[0] == "|".join(bound):
                for group, entity in zip(bound, out[1:]):
                    self.entities.setdefault(group, entity)
            for n, _, about in chunk:
                self.said[str(n)] = {"about": [self.entities.get(g) for g in about]}
        self._save()
        return {"said": len(todo), "entities": len(self.entities), "errors": errors}

    # --- reading -----------------------------------------------------------------------------

    def read(self, seconds: float | None = None) -> dict:
        """The world's own reading of what is unread: typed links, then classes."""
        from terraweaver import formalise, outside, portraits

        world = self.rt.world
        if not os.environ.get("NEBIUS_API_KEY"):
            return {"read": "no engineer: NEBIUS_API_KEY is not set"}
        world.engineer = outside.Nemotron(ttl=120)
        world.better = outside.Nemotron(outside.NEMOTRON_SENIOR, ttl=180)
        world.jev = None
        if os.environ.get("TYPESAFE_API_KEY"):
            # Asked once before it is relied on: a picker that refuses every call (402) leaves
            # every reading unread, where the engineer standing in would have read them.
            try:
                jev = outside.Jev()
                jev.choose("Rome is a city in Italy.", "Which of these is Rome?",
                           {"City": "a city", "Person": "a person"})
                world.jev = jev
            except Exception as wrong:  # noqa: BLE001 - without a picker the engineer chooses
                log.warning("no picker, the engineer chooses: %r", wrong)
        links = formalise.formalise(self.rt, world.engineer, seconds=seconds)
        classes = portraits.formalise(world, world.engineer, limit=10_000, jev=world.jev,
                                      seconds=seconds)
        return {"links": {k: v for k, v in links.items() if k != "read"}, "classes": classes}

    # --- forgetting ------------------------------------------------------------------------

    def forget(self, taken: list[tuple[int, str]]) -> dict:
        """Take what these entries said out of the world, for good.

        The world keeps what was said ("a relation the person stated is not retractable"), and
        for everything else it should; a user asking for something to be forgotten is the one
        thing that overrides it. The words are in many places — the texts, the statements, the
        comments, the log of every run's code, the readings — so they are scrubbed from every
        text column there is, not from the places known today. What the world built only on them
        goes too: a link between two things no remaining entry joins, a thing no remaining entry
        is about. Then the file is vacuumed, so the words are not left in its free pages."""
        conn = self.rt.store.conn
        texts = [t for _, t in taken if t.strip()]
        scrubbed = 0
        for table, column in _text_columns(conn):
            for text in texts:
                for form in {text, repr(text)[1:-1]}:
                    cur = conn.execute(f'UPDATE "{table}" SET "{column}" = replace("{column}", ?, \'\') '
                                       f'WHERE instr("{column}", ?) > 0', (form, form))
                    scrubbed += cur.rowcount
        for n, _ in taken:
            self.said.pop(str(n), None)
        # What still stands on a remaining entry: its things, and its pairs.
        alive = {e for said in self.said.values() for e in said["about"] if e}
        pairs = {frozenset((said["about"][0], other)) for said in self.said.values()
                 for other in said["about"][1:] if said["about"][0] and other}
        erased = []
        for link in self._links():
            ends = frozenset((link["subject"], link["object"]))
            if ends <= set(self.entities.values()) and ends not in pairs:
                erased.append(link["id"])
        names = []
        for group, entity in list(self.entities.items()):
            if entity not in alive:
                erased.append(entity)
                del self.entities[group]
                try:
                    names.append(self.rt.store.load(entity, self.rt.classes).display_name())
                except Exception:  # noqa: BLE001 - gone already
                    pass
        # A thing erased is still named in the world's logs — the code of the runs that said
        # it, the readings that typed its links. Logs only: elsewhere a name may be someone's
        # who is still here.
        for table, column in _text_columns(conn):
            if table in LOGS:
                for name in names:
                    scrubbed += conn.execute(f'UPDATE "{table}" SET "{column}" = replace("{column}", ?, \'(forgotten)\') '
                                             f'WHERE instr("{column}", ?) > 0', (name, name)).rowcount
        for instance in erased:
            _erase(conn, instance)
            self.rt.store.forget(instance)
        conn.commit()
        conn.execute("VACUUM")
        self._save()
        left = sum(conn.execute(f'SELECT count(*) FROM "{t}" WHERE instr("{c}", ?) > 0', (text,)).fetchone()[0]
                   for t, c in _text_columns(conn) for text in texts)
        return {"scrubbed": scrubbed, "erased": len(erased), "left": left}

    def _links(self) -> list[dict]:
        """Every link standing between two of the world's entities, bare or typed."""
        from terraweaver.formalise.look import words_for

        out = []
        for name in ["Related"] + [w for w, _, _ in words_for(self.rt.world)]:
            try:
                links = self.rt.world.all(name, limit=None)
            except Exception:  # noqa: BLE001 - a word with no class yet
                continue
            for link in links:
                a = getattr(getattr(link, "subject", None), "id", None)
                b = getattr(getattr(link, "object", None), "id", None)
                if a and b:
                    out.append({"id": link.id, "type": name, "subject": a, "object": b,
                                "ended": getattr(link, "valid_until", None) is not None})
        return out

    # --- the image ---------------------------------------------------------------------------

    def image(self) -> dict:
        """What the world made of it: each mirrored thing's class, and the typed links among them."""
        from terraweaver.formalise.look import words_for

        world = self.rt.world
        mine = {entity: group for group, entity in self.entities.items()}
        things = {}
        for group, entity in self.entities.items():
            try:
                held = self.rt.store.load(entity, self.rt.classes)
            except Exception:  # noqa: BLE001 - moved or merged since
                continue
            things[group] = {"name": held.display_name(), "class": type(held).__name__}
        links = []
        for name, _, _ in words_for(world):
            for link in world.all(name, limit=None):
                if getattr(link, "valid_until", None) is not None:
                    continue
                a = getattr(getattr(link, "subject", None), "id", None)
                b = getattr(getattr(link, "object", None), "id", None)
                if a in mine and b in mine:
                    links.append({"type": name, "subject": mine[a], "object": mine[b]})
        return {"things": things, "links": links}


class Worker:
    """The one thread that holds the world: SQLite is bound to the thread that opened it, and a
    reading takes minutes. It is handed jobs — say what is new, forget — and when nothing has come
    for `quiet` seconds it reads, a minute at a time, so a `forget` never waits long behind it."""

    def __init__(self, where: Path, quiet: float = 30, slice_seconds: float = 60):
        import queue
        import threading

        self.jobs: "queue.Queue" = queue.Queue()
        self.quiet, self.slice = quiet, slice_seconds
        self.last: dict = {}
        self._ready = threading.Event()
        self.thread = threading.Thread(target=self._loop, args=(Path(where),), daemon=True, name="world")
        self.thread.start()
        self._ready.wait()

    def _loop(self, where: Path) -> None:
        import queue

        self.mirror = Mirror(where)
        self.image = self.mirror.image()
        self._ready.set()
        unread = True
        while True:
            try:
                job, args, done = self.jobs.get(timeout=self.quiet)
            except queue.Empty:
                if unread:
                    try:
                        self.last["read"] = got = self.mirror.read(seconds=self.slice)
                        # Done when a slice found nothing left to read.
                        unread = bool(got.get("links", {}).get("typed") or got.get("classes", {}).get("read"))
                        self.image = self.mirror.image()
                    except Exception as wrong:  # noqa: BLE001 - a reading never stops the world
                        log.warning("reading failed: %r", wrong)
                        unread = False
                continue
            try:
                result = getattr(self.mirror, job)(*args)
                self.last[job] = result
                if job == "sync" and result.get("said"):
                    unread = True
                # Kept for the readers, who must not wait behind a reading for it.
                self.image = self.mirror.image()
            except Exception as wrong:  # noqa: BLE001 - said back to whoever waits
                log.warning("%s failed: %r", job, wrong)
                result = {"failed": repr(wrong)}
            if done is not None:
                done.put(result)

    def send(self, job: str, *args, wait: bool = False):
        import queue

        done = queue.Queue() if wait else None
        self.jobs.put((job, args, done))
        return done.get() if wait else None


def _text_columns(conn) -> list[tuple[str, str]]:
    """Every column of every table that can hold words."""
    out = []
    for (table,) in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'"):
        if table.startswith("sqlite_"):
            continue
        for row in conn.execute(f'PRAGMA table_info("{table}")'):
            if (row[2] or "").upper() in ("TEXT", ""):
                out.append((table, row[1]))
    return out


def _erase(conn, instance: str) -> None:
    """Every row about this instance, in every table that names an instance."""
    for (table,) in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'").fetchall():
        columns = {row[1] for row in conn.execute(f'PRAGMA table_info("{table}")')}
        for column in ("subject", "entity_id", "instance_id", "subject_id", "object_id"):
            if column in columns:
                conn.execute(f'DELETE FROM "{table}" WHERE "{column}" = ?', (instance,))


def main() -> int:
    """Mirror a proto run's journal into a world beside it, read it, and print what it made."""
    sys.path.insert(0, str(ROOT))
    from baseline import server as base
    from proto import server
    from proto.model import Structure

    run = Path(sys.argv[1])
    base.facts = run / "facts.md"
    structure = Structure(run / "structure.jsonl", base._keep, server.held)
    held = {n: text for n, _, text in base._entries(base._memory())}
    mirror = Mirror(run / "world")
    print("said:", mirror.sync(structure, held), flush=True)
    if "--say-only" not in sys.argv:
        print("read:", mirror.read(), flush=True)
    image = mirror.image()
    (run / "world_image.json").write_text(json.dumps(image, ensure_ascii=False, indent=1))
    for group, t in sorted(image["things"].items(), key=lambda kv: kv[1]["class"]):
        print(f"  {t['class']:18} {t['name']}")
    for link in image["links"]:
        print(f"  {image['things'].get(link['subject'], {}).get('name')} --{link['type']}--> "
              f"{image['things'].get(link['object'], {}).get('name')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
