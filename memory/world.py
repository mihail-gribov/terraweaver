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

    .venv/bin/python -m memory.world <run dir>      # mirror a run's journal, read it, print the image
"""
import json
import logging
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CORE = ROOT / "ontology" / "core"
KEY = "proto"
log = logging.getLogger("memory.world")
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
        # What the journal was read into, in the quiet: values and links, each with the entry its
        # quote stands in. A cache of the journal, never written to on intake (`read_journal`).
        self.from_journal = _load(self.where / READ, {"entries": [], "things": {}, "values": [], "links": []})
        # The structure and the journal as the last sync had them, for reading in the quiet.
        self.structure, self.held = None, {}

    def _save(self) -> None:
        (self.where / "mirror.json").write_text(json.dumps({"entities": self.entities, "said": self.said},
                                                           ensure_ascii=False, indent=1))

    # --- saying ------------------------------------------------------------------------------

    def sync(self, structure, held: dict[int, str]) -> dict:
        """Say every held entry not yet said. Returns counts, and the errors the world gave."""
        self.structure, self.held = structure, dict(held)
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
        from terraweaver import decision, formalise, outside, portraits

        world = self.rt.world
        if not os.environ.get("NEBIUS_API_KEY"):
            return {"read": "no engineer: NEBIUS_API_KEY is not set"}
        world.engineer = outside.Nemotron(ttl=120)
        world.better = outside.Nemotron(outside.NEMOTRON_SENIOR, ttl=180)
        world.jev = decision.picker()
        if world.jev is None:
            log.warning("no picker, the engineer chooses")
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
        self._forget_read({n for n, _ in taken})
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

    # --- reading the journal into values and links ---------------------------------------------

    def read_journal(self, reader=None, judge=None, seconds: float | None = None) -> dict:
        """Read what the journal said, in journal order, into values and links with their quotes.

        The proto's things say *that* something was said about them; what it said — an age, a
        price, who is whose sister — is in the words, and is read here, in the quiet, the way a
        mind consolidates. Entries that follow each other are read together, because what joins
        two things is said across sentences; a cut by size is bridged by showing the reader the
        entries just before it, and what the image already knows of the things named, as context
        it does not read from. `memory.parse.read` proposes and checks each value and link twice
        (the quote is in the text, by code; the quote says the claim, by the judge); each one kept
        here carries the entry its quote stands in, so a forgotten entry takes it away. A later
        entry can end what an earlier one said ("Rachel left"), so links read before are asked
        about again when new entries touch them.

        Nothing is written on intake: this is the image of the journal, rebuilt from it, and the
        journal stays the truth.
        """
        import time

        if self.structure is None or not self.held:
            return {}
        if reader is None:
            from memory.parse import read as reader
        if judge is None:
            from memory.models import role
            judge = role("judge")
        began, done = time.monotonic(), set(self.from_journal["entries"])
        unread = sorted(n for n in self.held if n not in done)
        order = sorted(self.held)
        tally = {"entries": 0, "values": 0, "links": 0, "dropped": 0, "asked": 0, "ended": 0}
        for chunk in _chunks(unread, self.held):
            if seconds is not None and time.monotonic() - began > seconds:
                break
            texts = {n: self.held[n] for n in chunk}
            text = "\n\n".join(texts.values())
            groups = _groups(self.structure, self.held)
            before = [n for n in order if n < chunk[0]][-CONTEXT_ENTRIES:]
            context = "\n\n".join(part for part in (
                self._known(text, groups),
                "Entries before these, already read:\n" + "\n".join(self.held[n] for n in before) if before else "",
            ) if part)
            got = _read(reader, text, context)
            earlier = [l for l in self.from_journal["links"] if l["entry"] < chunk[0]]
            named: dict[str, str | None] = {}
            for t in got.get("things") or []:
                named[t["name"]] = self._who(t["name"], t.get("kind"), text, groups, judge, tally)
            for t in got.get("things") or []:
                who = named.get(t["name"])
                for attr, v in (t.get("values") or {}).items():
                    # A quote only the context holds is not this chunk's to read: None, dropped.
                    entry = _entry_of(v.get("quote", ""), texts)
                    if who and entry is not None:
                        self.from_journal["values"].append({"thing": who, "attr": attr, "value": v.get("value"),
                                                    "quote": v.get("quote"), "entry": entry})
                        tally["values"] += 1
            for link in got.get("links") or []:
                a, b, entry = named.get(link.get("from")), named.get(link.get("to")), _entry_of(link.get("quote", ""), texts)
                if a and b and a != b and entry is not None:
                    says = link.get("says") or f"{link.get('from')} {link.get('as') or 'related to'} {link.get('to')}"
                    holds, sure = _holds(judge, text, says)
                    self.from_journal["links"].append({"subject": a, "object": b, "type": str(link.get("as") or "related"),
                                               "says": says, "quote": link.get("quote"), "entry": entry,
                                               "holds": holds, "sure": sure})
                    tally["links"] += 1
            tally["ended"] += self._recheck(earlier, texts, groups, judge)
            tally["dropped"] += len(got.get("dropped") or [])
            self.from_journal["entries"] = sorted(set(self.from_journal["entries"]) | set(chunk))
            self._prune()
            tally["entries"] += len(chunk)
            _dump(self.where / READ, self.from_journal)
        tally["left"] = len([n for n in self.held if n not in set(self.from_journal["entries"])])
        return tally

    def _names_of(self, thing: str, groups: dict) -> set[str]:
        """The keys a thing of the image goes by in words: its names, and "I" for the user."""
        if thing in groups:
            keys = set(groups[thing]["keys"])
        else:
            keys = {_key(self.from_journal["things"].get(thing, {}).get("name", ""))} - {""}
        return keys | ({"i", "me", "my"} | self._users() if keys & self._users() else set())

    def _known(self, text: str, groups: dict) -> str:
        """What the image already holds of the things this text names, and of the user: a line each,
        so the reader names them the same way and ties "my team", "our office" to them."""
        said = f" {_key(text)} "
        names = {g: h["name"] for g, h in groups.items()} | {r: t["name"] for r, t in self.from_journal["things"].items()}
        kinds = {g: h["kind"] for g, h in groups.items()} | {r: t.get("kind") for r, t in self.from_journal["things"].items()}
        lines = []
        for thing in names:
            keys = self._names_of(thing, groups)
            if not (keys & self._users()) and not any(f" {k} " in said for k in keys):
                continue
            ties = [l for l in self.from_journal["links"] if thing in (l["subject"], l["object"]) and l.get("holds") != "ended"]
            about = "; ".join(f"{names.get(l['subject'], '?')} {l['type'].replace('_', ' ')} {names.get(l['object'], '?')}"
                              for l in ties[-KNOWN_LINKS:])
            also = sorted(set(self.from_journal.get("user_names") or []) - {_key(names[thing])}) if keys & self._users() else []
            lines.append(f"- {names[thing]}" + (f" (the user, also called {', '.join(also)})" if also else "")
                         + (f" — {kinds[thing]}" if kinds.get(thing) else "") + (f"; {about}" if about else ""))
        return ("Already known — name these the same way:\n" + "\n".join(lines[:KNOWN_THINGS])) if lines else ""

    def _recheck(self, earlier: list[dict], texts: dict, groups: dict, judge) -> int:
        """Links read from earlier entries, asked again where the new ones touch them.

        "My manager is Rachel" read last week holds until "Rachel left Brightwork" today: neither
        chunk alone says the manager link ended. A link is asked again when a new entry names both
        its ends, or names one of them with a sign of change in it; the user alone is too often
        named, so then a word of the link's own is wanted too ("my manager is now Tom"). The
        judge sees when the link was said and the entries told after it. Returns how many ended.
        """
        ended = 0
        for l in earlier:
            if l.get("holds") == "ended":
                continue
            ends = [self._names_of(l["subject"], groups), self._names_of(l["object"], groups)]
            own = {w for w in _key(l["type"]).split() if len(w) > 2 and w not in TYPE_STOP}
            touched = []
            for n, t in texts.items():
                said = f" {_key(_words_of(t))} "
                hit = [any(f" {k} " in said for k in keys) for keys in ends]
                users = [bool(keys & self._users()) for keys in ends]
                change = bool(CHANGE.search(_words_of(t)))
                by_name = [h and not u for h, u in zip(hit, users)]
                if all(hit) or (change and (any(by_name) or (any(hit) and any(f" {w}" in said for w in own)))):
                    touched.append(n)
            if not touched:
                continue
            # One later entry at a time, beside the entry that said it (both carry their dates):
            # several at once, the Nano read "Rachel left" beside the Olga entries at 0.56, alone
            # at 0.83; and the first entry is what tells "Olga used to be my manager" is not Rachel.
            first = self.held.get(l["entry"], "")
            question = (f"Do the later entries say that \u00ab{l['says']}\u00bb no longer holds \u2014 that this "
                        f"link, between these two, ended or was replaced?")
            for n in touched:
                try:
                    p = judge.noul(f"Earlier:\n{first}\n\nLater:\n{texts[n]}", question,
                                   "yes, it ended or was replaced", "no, or they do not say")["p"]["yes"]
                except Exception as wrong:  # noqa: BLE001 - unasked is not ended
                    log.warning("recheck %r: %r", l["says"], wrong)
                    continue
                if p >= ENDS:
                    l["holds"], l["sure"], l["ended_in"] = "ended", round(p, 3), n
                    ended += 1
                    break
        return ended

    def _who(self, name: str, kind, text: str, groups: dict, judge, tally: dict) -> str | None:
        """The proto thing a name read is, or a thing of the image's own. Never a merge by name.

        One thing holds the name: it is that one. Several could be (two Annas, "Darren" and
        "Darren Liu"): a closed question to the judge, with "none of these" among the options, and
        only a clear answer binds. A name nobody holds is a thing the world read, kept apart.
        """
        k = _key(name)
        if k in self._users():
            return self._user(groups)
        exact = [g for g, h in groups.items() if k in h["keys"]]
        words = set(k.split())
        close = exact + [g for g, h in groups.items() if g not in exact
                         and any(words and (words <= set(n.split()) or set(n.split()) <= words) for n in h["keys"])]
        if len(close) == 1 and exact:
            return exact[0]
        # A person no thing holds by that exact name may be the user ("Alex", next to an event
        # "Alex starts as data engineer at Brightwork" that only shares the word).
        if not exact and self._is_the_user(name, kind, text, judge, tally):
            return self._user(groups)
        if not close:
            return self._read_thing(name, kind)
        options = [(g, f"{groups[g]['name']}" + (f" ({groups[g]['kind']})" if groups[g]["kind"] else "")
                    + (f" — {groups[g]['said'][:160]}" if groups[g]["said"] else "")) for g in close[:20]]
        options.append((NOBODY, f"none of these — {name} is someone or something else"))
        tally["asked"] += 1
        try:
            got = judge.choice(text[-4000:], f"In this text, who or what is \u00ab{name}\u00bb?", options)
        except Exception as wrong:  # noqa: BLE001 - unasked is unbound, not merged
            log.warning("who is %r: %r", name, wrong)
            return None
        best = got.get("choice")
        if best and best != NOBODY and got["p"].get(best, 0) >= SURE:
            return best
        return self._read_thing(name, kind) if best == NOBODY else None

    def _users(self) -> set[str]:
        """The names the user goes by: "the user", "I", and the names the judge said were theirs."""
        return USER | set(self.from_journal.get("user_names") or [])

    def _user(self, groups: dict) -> str:
        """The user, always one thing: the host's thing for them if it has one, else the image's own."""
        mine = [g for g, h in groups.items() if h["keys"] & self._users()]
        return min(mine, key=lambda g: int(g[1:]) if g[1:].isdigit() else 0) if mine else self._read_thing("the user", "person")

    def _is_the_user(self, name: str, kind, text: str, judge, tally: dict) -> bool:
        """Whether a person's name nobody holds is the user's own. The host writes "the user" and
        "Alex" for one person (var/memory/dialogue-colleagues-20261027-191432), and every link then
        hung off two things. Asked once per name; a yes is kept, so the name binds from then on."""
        if kind and "person" not in str(kind).lower():
            return False
        tally["asked"] += 1
        try:
            p = judge.noul(text[-4000:], f"Is \u00ab{name}\u00bb the user themself \u2014 the person whose memory "
                           f"this is, called \"the user\" or \"I\" in these entries?",
                           "yes, the same person", "no, someone else")["p"]["yes"]
        except Exception as wrong:  # noqa: BLE001 - unasked is someone else, kept apart
            log.warning("is %r the user: %r", name, wrong)
            return False
        if p < USER_SURE:
            return False
        self.from_journal.setdefault("user_names", []).append(_key(name))
        return True

    def _read_thing(self, name: str, kind) -> str:
        rid = f"r:{_key(name).replace(' ', '-')}"
        self.from_journal["things"].setdefault(rid, {"name": name, "kind": kind or None})
        return rid

    def _forget_read(self, numbers: set) -> None:
        """What was read from a forgotten entry goes with it, and a read thing nothing stands on."""
        self.from_journal["values"] = [v for v in self.from_journal["values"] if v["entry"] not in numbers]
        self.from_journal["links"] = [l for l in self.from_journal["links"] if l["entry"] not in numbers]
        self.from_journal["entries"] = [n for n in self.from_journal["entries"] if n not in numbers]
        for l in self.from_journal["links"]:
            # An ending told only in a forgotten entry is not told any more.
            if l.get("ended_in") in numbers:
                l["holds"] = "unsaid"
                l.pop("ended_in")
        self._prune()
        _dump(self.where / READ, self.from_journal)

    def _prune(self) -> None:
        """Read things nothing stands on are not kept: a name met only in the context, or forgotten."""
        alive = {v["thing"] for v in self.from_journal["values"]} | {e for l in self.from_journal["links"] for e in (l["subject"], l["object"])}
        self.from_journal["things"] = {r: t for r, t in self.from_journal["things"].items() if r in alive}

    # --- the image ---------------------------------------------------------------------------

    def image(self) -> dict:
        """What the world made of the journal, written to `image.json` for readers outside the server.

            things  {group: {"name", "class", "source": "host" | "read", "user"?}}
            links   [{"type", "subject", "object", "entry", "says", "source": "world" | "read", "quote"?}]
            values  {group: {attr: [{"value", "entry", "quote"}]}}

        `host` things are the agent's own (proto groups); `read` ones the world read and nobody
        named. `world` links are the bare links typed by `formalise`, standing on the latest entry
        that joined the two; `read` links are read from the words, with their quote. Several values
        of one attribute stay a list, in entry order: which holds now is the reader's call.
        """
        from terraweaver.formalise.look import words_for

        world = self.rt.world
        mine = {entity: group for group, entity in self.entities.items()}
        things = {}
        for group, entity in self.entities.items():
            try:
                held = self.rt.store.load(entity, self.rt.classes)
            except Exception:  # noqa: BLE001 - moved or merged since
                continue
            things[group] = {"name": held.display_name(), "class": type(held).__name__, "source": "host"}
            if _key(held.display_name()) in self._users():
                things[group]["user"] = True
        # Every thing the host named is in the image, said of or not ("Marco in sales" with no entry
        # about him never reaches the world), and a thing the world has not placed yet — only links
        # said of it, nothing for `portraits` to read — keeps the kind the host gave it.
        for group, h in (_groups(self.structure, self.held) if self.structure else {}).items():
            kind = (h["kind"] or "").title().replace(" ", "")
            t = things.setdefault(group, {"name": h["name"], "class": kind or "Thing", "source": "host",
                                          **({"user": True} if h["keys"] & self._users() else {})})
            if t["class"] == "Thing" and kind:
                t["class"] = kind
        for rid, t in self.from_journal["things"].items():
            things.setdefault(rid, {"name": t["name"], "class": (t.get("kind") or "thing").title().replace(" ", ""),
                                    "source": "read", **({"user": True} if _key(t["name"]) in self._users() else {})})
        links = []
        for name, _, _ in words_for(world):
            for link in world.all(name, limit=None):
                a = getattr(getattr(link, "subject", None), "id", None)
                b = getattr(getattr(link, "object", None), "id", None)
                if a in mine and b in mine:
                    entry = max((int(n) for n, said in self.said.items() if {a, b} <= set(said["about"])), default=None)
                    until = getattr(link, "valid_until", None)
                    since = getattr(link, "valid_from", None)
                    links.append({"type": name, "subject": mine[a], "object": mine[b], "entry": entry,
                                  "says": _words_of(self.held.get(entry, "")) if entry else "", "source": "world",
                                  # An ended link is kept, marked: "left" and "used to be" end a link.
                                  "holds": "ended" if until is not None else "now",
                                  **({"from": str(since)} if since else {}), **({"until": str(until)} if until else {})})
        for l in self.from_journal["links"]:
            links.append({"type": l["type"], "subject": l["subject"], "object": l["object"], "entry": l["entry"],
                          "says": l["says"], "quote": l["quote"], "source": "read",
                          "holds": l.get("holds", "unsaid"), **({"ended_in": l["ended_in"]} if "ended_in" in l else {})})
        values: dict = {}
        for v in sorted(self.from_journal["values"], key=lambda v: v["entry"]):
            values.setdefault(v["thing"], {}).setdefault(v["attr"], []).append(
                {"value": v["value"], "entry": v["entry"], "quote": v["quote"]})
        image = {"things": things, "links": links, "values": values}
        _dump(self.where / IMAGE, image)
        return image


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
                        # First what the journal says — values, links and their quotes — then
                        # what the world types of it: classes and typed links.
                        if os.environ.get("NEBIUS_API_KEY"):
                            got = self.mirror.read_journal(seconds=self.slice)
                            if got.get("entries"):
                                self.last["read_journal"] = got
                                self.image = self.mirror.image()
                                continue
                        if not ontology():
                            unread = False
                            self.image = self.mirror.image()
                            continue
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


READ, IMAGE = "read.json", "image.json"
# Names the user goes by, in the journal and in what is read from it.
USER = {"the user", "user", "i", "me", "myself", "the user s"}
NOBODY = "none of these"
# How sure the judge must be that a name is the user's own before every link of it is the user's.
USER_SURE = 0.75
# How sure the judge must be that a name read is a thing the memory holds before it is bound to it.
SURE = 0.6
# One reading's text: consecutive entries, cut where it would run past what the reader is shown.
CHUNK_CHARS = 12000
# What the reader is shown beside it: the entries just before, and what is known of the things named.
CONTEXT_ENTRIES, KNOWN_THINGS, KNOWN_LINKS = 3, 30, 2
# Words that say something changed; a link read before is asked about again where they meet its ends.
CHANGE = re.compile(r"\b(left|leav\w*|quit|moved?|sold|bought|now|no longer|used to|anymore|any more|former\w*|"
                    r"ex|new|became|become|stopped|ended|changed|replaced|joined|retired|divorced|broke up|instead|"
                    r"since|until|anymore)\b", re.I)
# How sure a later entry must be read to end a link read earlier: a yes/no question, one later
# entry at a time. On demo-people, three readings, the Nano gave "Rachel left Brightwork" against
# "Rachel is the user's manager" 0.78-0.82; every wrong pair (the Olga entries, "Rachel left"
# against the user's or Anna's place at Brightwork) 0.39-0.65. The three-way question had an
# Olga entry end Rachel's link at 0.60-0.64, and several entries at once read 0.56.
ENDS = 0.75
TYPE_STOP = {"of", "at", "to", "the", "has", "is", "for", "with", "in", "on", "and", "by"}


def ontology() -> bool:
    """Whether the world also types what it holds: `formalise` (typed links) and `portraits`
    (classes). Off unless TERRAWEAVER_ONTOLOGY=1: the solver reads the read links and the host's
    kinds, so the typing costs minutes and calls for nothing it uses (2026-10-27)."""
    return os.environ.get("TERRAWEAVER_ONTOLOGY", "").strip().lower() in {"1", "true", "yes", "on"}


def _load(path: Path, default):
    return json.loads(path.read_text()) if path.exists() else default


def _dump(path: Path, data) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=1))


def _key(name: str) -> str:
    return " ".join("".join(c if c.isalnum() else " " for c in str(name).lower()).split())


def _words_of(entry_line: str) -> str:
    """The words of a journal line (`- #n · time · source: words`), without its heading."""
    return entry_line.partition(": ")[2] or entry_line


def _groups(structure, held: dict) -> dict:
    """Each proto group by its smallest thing id: its name, the names its members go by, its kind,
    and the first thing said about it — what the judge is shown to tell two of one name apart."""
    things = structure._things()
    group_of, out = {}, {}
    for t in things.values():
        members = structure.one_with(structure.thing("q", t["thing"]))
        g = min(members, key=lambda i: int(i[1:]) if i[1:].isdigit() else 0)
        group_of[t["thing"]] = g
        h = out.setdefault(g, {"name": things[g]["name"] if g in things else t["name"], "keys": set(),
                               "kind": None, "said": ""})
        h["keys"].add(_key(t["name"]))
        h["kind"] = h["kind"] or t.get("kind")
    for r in structure.records:
        if r.get("entry") in held:
            for t in r.get("about") or []:
                h = out.get(group_of.get(t))
                if h is not None and not h["said"]:
                    h["said"] = _words_of(held[r["entry"]])
    return out


def _chunks(unread: list[int], held: dict) -> list[list[int]]:
    """Unread entries in journal order, consecutive ones together, cut by size.

    Not by session: the session is the client's name ("claude-code" for every conversation), so
    it groups nothing. What is said together is said one entry after another.
    """
    out, chunk, size = [], [], 0
    for n in unread:
        if chunk and (n != chunk[-1] + 1 and any(chunk[-1] < m < n for m in held) or size + len(held[n]) > CHUNK_CHARS):
            out.append(chunk)
            chunk, size = [], 0
        chunk.append(n)
        size += len(held[n]) + 2
    return out + ([chunk] if chunk else [])


def _read(reader, text: str, context: str) -> dict:
    """The reader over the new entries, with the context beside them where it takes one, and in
    front of them where it does not (a quote from the context is then dropped by its entry)."""
    import inspect

    try:
        takes = "context" in inspect.signature(reader).parameters
    except (TypeError, ValueError):
        takes = False
    if takes:
        return reader(text, want="", source="the user's memory", fields=None, context=context)
    if context:
        text = (f"{context}\n\nRead only the new entries below; what is above is context, already read.\n"
                f"New entries:\n{text}")
    return reader(text, want="", source="the user's memory", fields=None)


HOLDS = [("now", "yes — as the text tells it, this still holds"),
         ("ended", "no — the text says it ended, or that it was so only before (left, used to be, former)"),
         ("unsaid", "the text does not say whether it still holds")]


def _holds(judge, text: str, says: str, asked: bool = False) -> tuple[str, float]:
    """Whether a link read still holds, as the text tells it: a closed question to the judge.

    A link is not two facts when it ends: "Rachel left Brightwork" ends Rachel's place there, and
    "Olga used to be my manager" is a manager link that ended. So the read link carries `holds`,
    and a reader takes the ended ones as history, not as now.
    """
    try:
        got = judge.choice(text[-4000:], says if asked else f"\u00ab{says}\u00bb \u2014 does this still hold?", HOLDS)
    except Exception as wrong:  # noqa: BLE001 - unasked is unsaid
        log.warning("holds %r: %r", says, wrong)
        return "unsaid", 0.0
    best = got.get("choice") or "unsaid"
    sure = round(float(got.get("p", {}).get(best, 0.0)), 3)
    # An ending taken on a lean would hide a link that holds; below SURE it is left unsaid.
    return (best if best != "ended" or sure >= SURE else "unsaid"), sure


def _entry_of(quote: str, texts: dict) -> int | None:
    """The entry a quote stands in: the latest whose words hold it, or None if none does."""
    from memory.parse import words

    w = words(quote)
    hits = [n for n, t in texts.items() if w and w in words(t)]
    return max(hits) if hits else None


def image_of(world_dir) -> dict:
    """The image as the server last wrote it, for a reader outside the server (`python -m memory.solve`):
    `image_of(var/memory/<memory>/world)`. Built from the world directly when no server has written it."""
    path = Path(world_dir) / IMAGE
    if path.exists():
        return json.loads(path.read_text())
    return Mirror(world_dir).image()


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
    from memory import journal as base
    from memory import server
    from memory.model import Structure

    run = Path(sys.argv[1])
    base.facts = run / "facts.md"
    structure = Structure(run / "structure.jsonl", base._keep, server.held)
    held = server.held()            # with their numbers and dates, as the reader is shown them
    mirror = Mirror(run / "world")
    print("said:", mirror.sync(structure, held), flush=True)
    if "--say-only" not in sys.argv:
        while (got := mirror.read_journal()).get("entries"):
            print("read the journal:", got, flush=True)
        if ontology():
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
