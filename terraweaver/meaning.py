"""Finding things by what they mean, not by the words they happen to use.

Most of a world is structured and needs no help: who works where is a relation, when something
happened is a date. But some of it is deliberately free text — a remark about someone, a note on
an idea — and there the world has been reduced to matching words. "Who do I know who works on
batteries" finds nothing when the remark says "does cell chemistry at a startup".

So: an index over what was said, by meaning. Three things about it matter more than the model
behind it.

**It is an index, not a source.** An embedding states nothing, outranks nothing and never reaches
an image. Change the model and the index is rebuilt; the world is exactly as it was. It is the
same relation to the record that images have to statements — a derivation you may throw away.

**It suggests, it does not decide.** Above all, it takes no part in deciding who someone is.
"Anna Petrova" and "Anna Sokolova" sit close together in any embedding, and identity in this
world is settled by names people vouched for and facts that disagree (`assembly.py`), not by
proximity. Meaning may offer a candidate; a rule accepts it.

**It works without a model at all.** The local model is used when it is there; failing that, a
plain deterministic fallback keeps every path working — tests, an offline laptop, a fresh
checkout. Worse answers, never a broken world.
"""
import hashlib
import json
import math
import os
import time
import urllib.error
import urllib.request
from contextlib import contextmanager

from terraweaver.store import run_script

SCHEMA = """
CREATE TABLE IF NOT EXISTS meanings (
    ref TEXT PRIMARY KEY,        -- what this text belongs to: "comment:12", "Person:abc:notes"
    subject TEXT NOT NULL,       -- the entity it is about
    kind TEXT NOT NULL,          -- comment | notes | title
    text TEXT NOT NULL,
    digest TEXT NOT NULL,        -- the text as it was when embedded; changed, it is re-embedded
    model TEXT NOT NULL,
    vector TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_meanings_subject ON meanings(subject);
"""

OLLAMA = os.environ.get("TERRAWEAVER_OLLAMA", "http://localhost:11434")
LOCAL_MODEL = os.environ.get("TERRAWEAVER_EMBEDDING", "bge-m3")
REMOTE_MODEL = os.environ.get("TERRAWEAVER_EMBEDDING_API", "Qwen/Qwen3-Embedding-8B")

# Free-text attributes worth finding by meaning. Names are not here on purpose: a name is for
# identity, and identity is not decided by proximity.
TEXT_ATTRIBUTES = ("descriptions", "title", "value")


class Plain:
    """A deterministic stand-in: character trigrams hashed into a fixed space.

    Not good, and not pretending to be. It exists so that every path works with no model at all —
    a test, an offline machine, a first run — and so that turning the real model on is a change
    in quality, not in whether the thing works."""

    name = "plain"
    size = 256

    def embed(self, texts: list[str]) -> list[list[float]]:
        out = []
        for text in texts:
            vector = [0.0] * self.size
            words = f"  {text.lower().strip()}  "
            for i in range(len(words) - 2):
                slot = int(hashlib.md5(words[i:i + 3].encode()).hexdigest()[:8], 16) % self.size
                vector[slot] += 1.0
            out.append(_unit(vector))
        return out


class Ollama:
    """Whatever model is served locally — bge-m3 by default, which handles several languages."""

    def __init__(self, model: str = LOCAL_MODEL, host: str = OLLAMA):
        self.name, self.host = model, host

    def embed(self, texts: list[str]) -> list[list[float]]:
        request = urllib.request.Request(
            f"{self.host}/api/embed",
            data=json.dumps({"model": self.name, "input": texts}).encode(),
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(request, timeout=60) as answer:
            return [_unit(v) for v in json.loads(answer.read())["embeddings"]]


class Nebius:
    """The same model for everyone, over the API — for a machine with nothing installed on it.

    Which vectors a world holds is recorded per row and every read filters by it, so moving
    between here and the local model rebuilds the index rather than mixing two spaces. That is
    what makes this a choice about quality and not about correctness.
    """

    def __init__(self, model: str = REMOTE_MODEL):
        self.name = model

    def embed(self, texts: list[str]) -> list[list[float]]:
        from terraweaver import llm

        answer = llm.client().embeddings.create(model=self.name, input=texts)
        return [_unit(item.embedding) for item in sorted(answer.data, key=lambda d: d.index)]


# How long the meaning checks inside one host run may wait, *in total*. The run is stopped after
# ten seconds, so anything in it that talks to the outside has to be bounded — and bounded once
# for the whole run rather than once per call, which is the mistake this codebase has already made
# and fixed at the close (`runtime.READING_AT_THE_CLOSE`). Measured 2026-09-30: with a deadline of
# 1.5 s per call, one `world.define` still cost 6 s, because a define asks four or five times.
# Past the budget the meaning check is simply not done, the word is left for the pass that runs at
# the close where nothing is waiting, and the spelling check — which is free — still answers.
INLINE_SECONDS = 2.0
_SPENDING_UNTIL: float | None = None


@contextmanager
def spending(seconds: float = INLINE_SECONDS):
    """One budget for every meaning check inside this run. Nested calls join the outermost."""
    global _SPENDING_UNTIL
    if _SPENDING_UNTIL is not None:
        yield
        return
    _SPENDING_UNTIL = time.monotonic() + seconds
    try:
        yield
    finally:
        _SPENDING_UNTIL = None


def left_to_spend(asked: float | None) -> float | None:
    """What is left of the run's budget, or `asked` when nothing set one. 0 means stop asking."""
    if _SPENDING_UNTIL is None:
        return asked
    return max(0.0, _SPENDING_UNTIL - time.monotonic())


# Vectors a worker finished after its caller stopped waiting, by (model, the text's digest). A
# plain dict: a worker only ever sets a key and the calling thread only reads and then writes the
# value down itself, so nothing here touches the database off its own thread.
_LANDED: dict = {}


def within_seconds(seconds: float | None, work):
    """Run `work()` and give up on it after `seconds`. None means it did not answer in time.

    Only ever a network call: nothing that touches this world's connection is run here, because a
    connection belongs to the thread that made it. The worker is left to finish on its own — an
    embedding already asked for is paid for either way — and what is bounded is the *waiting*.
    """
    import concurrent.futures

    seconds = left_to_spend(seconds)
    if seconds is not None and seconds <= 0:
        return None                     # the run has spent what it had; ask at the close instead
    pool = concurrent.futures.ThreadPoolExecutor(max_workers=1)
    try:
        return pool.submit(work).result(timeout=seconds)
    except Exception:  # noqa: BLE001 - not answering in time is an outcome, not a failure
        return None
    finally:
        pool.shutdown(wait=False)


_CHOSEN = None


def embedder():
    """The API first, the local model only when it is asked for, the stand-in last.

    **The world needs no card of its own.** The engineer is on Token Factory, the picker is on
    TypeSafe, and this is on Nebius — a world is reached over an API and so is everything it
    reaches. A local model was preferred here because it costs nothing and answers in
    milliseconds, and the price of that preference was measured on 2026-09-28: another of the
    author's runs filled the card, Ollama stayed up while every `/api/embed` answered
    `do load request: … EOF`, and the world wrote two 455-fact worlds with **no meaning index at
    all** — 0 rows where the world that scored 81% had 495. The behaviour of the world depended
    on what else happened to be on the machine, invisibly, and a judge running this on a clean
    machine has no Ollama at all.

    So the API is the way, and the local model is an optimisation somebody turns on
    (`TERRAWEAVER_OLLAMA_FIRST=1`) when they know the card is theirs. Either way it is asked to
    embed and not asked whether it is alive: a server that is up and cannot load its model is
    exactly the case that cost the measurement.
    """
    # Asked once per process: the answer cannot change while it runs, and asking it per world
    # opened put a network call in front of every test.
    global _CHOSEN
    if _CHOSEN is not None:
        return _CHOSEN
    wanted = [Ollama, Nebius] if os.environ.get("TERRAWEAVER_OLLAMA_FIRST") else [Nebius, Ollama]
    for which in wanted:
        if which is Nebius and not os.environ.get("NEBIUS_API_KEY"):
            continue
        try:
            asked = which()
            asked.embed(["ready?"])
            _CHOSEN = asked
            return asked
        except Exception:  # noqa: BLE001 - anything at all means this is not the one to use
            continue
    _CHOSEN = Plain()
    return _CHOSEN


# How many of an entity's texts have a say when it is scored as a whole. All of them compete;
# the strongest few decide. One is too few — a single short text carries an entity in on noise,
# and short texts are the noisiest (a one-word text scores 0.355 against things it has nothing
# to do with, where a ten-word one scores 0.276). All of them is too many — averaging everything
# said about a person describes nobody.
TOP_TEXTS = 3
# How much the other texts count next to the closest one. Enough that two matching texts beat
# one, little enough that one strong match still beats a pile of vaguely related ones. A plain
# average of the top few is unfair to whoever has fewer texts, and it showed: it put the wrong
# person first once in six.
BACKING = 0.35
# How many texts are looked at at all before they are grouped into entities. Matching against
# the closest few in the world rather than against everything is what keeps a weak resemblance
# from becoming an answer just because nothing better was asked for.
POOL = 50


class Meanings:
    def __init__(self, store, model=None):
        self.store = store
        self.model = model or embedder()
        # What the index was last brought up to date at, per connection: the record's write count.
        self._fresh_at: dict[int, int] = {}
        run_script(store.conn, SCHEMA)
        store.conn.commit()

    # --- keeping the index up to date ---

    def refresh(self, world, limit: int = 500) -> int:
        """Embed what has changed since last time. Returns how many texts were done.

        Skipped outright when nothing has been said since the last refresh. The embedding was
        already incremental — a digest per text — but *finding out* what to embed walks every
        class of the world twice, and that walk ran on every `like()`, `entities()` and
        `similar()` (docs/code-review-2026-09-30.md 2.4). Everything it reads is derived from the
        statements, so the record's own write count is the honest witness.
        """
        mark = getattr(getattr(world, "facts", None), "writes", None)
        if mark is not None and self._fresh_at.get(id(world.store.conn)) == mark:
            return 0
        wanted = list(self._texts(world))[:limit]
        known = {ref: (digest, model) for ref, digest, model in self.store.conn.execute(
            "SELECT ref, digest, model FROM meanings")}
        due = [(ref, subject, kind, text) for ref, subject, kind, text in wanted
               if known.get(ref) != (_digest(text), self.model.name)]
        for batch in range(0, len(due), 32):
            chunk = due[batch:batch + 32]
            vectors = self.model.embed([text for _, _, _, text in chunk])
            for (ref, subject, kind, text), vector in zip(chunk, vectors):
                self.store.conn.execute(
                    "INSERT OR REPLACE INTO meanings (ref, subject, kind, text, digest, model, "
                    "vector) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (ref, subject, kind, text, _digest(text), self.model.name, json.dumps(vector)))
        self.store.conn.commit()
        if mark is not None:
            self._fresh_at[id(world.store.conn)] = mark
        return len(due)

    def vectors_for(self, refs_and_texts: list[tuple[str, str]], within: float | None = None) -> dict[str, list]:
        """Vectors for these (ref, text) pairs, embedding only what is new or has changed.

        The index as a cache, which is what it is. `twins()` and `classes_like()` re-embedded
        every class name and description on every `define` — a network call proportional to the
        vocabulary, inside a host's ten-second run (docs/code-review-2026-09-30.md 3.4.3, 3.3.15).
        Here the ones already known cost nothing and a new word costs one text.
        """
        known = {ref: (digest, model, raw) for ref, digest, model, raw in self.store.conn.execute(
            "SELECT ref, digest, model, vector FROM meanings")}
        out, due, landed = {}, [], []
        for ref, text in refs_and_texts:
            held = known.get(ref)
            if held and held[0] == _digest(text) and held[1] == self.model.name:
                out[ref] = json.loads(held[2])
                continue
            # Embedded by a worker that ran past an earlier caller's deadline: it is here now, and
            # this thread — which owns the connection — is the one to write it down.
            arrived = _LANDED.get((self.model.name, _digest(text)))
            if arrived is not None:
                out[ref] = arrived
                landed.append((ref, text, arrived))
            else:
                due.append((ref, text))
        for ref, text, vector in landed:
            self._keep(ref, text, vector)
        model = self.model
        for batch in range(0, len(due), 32):
            chunk = due[batch:batch + 32]

            def embed(chunk=chunk):
                # Runs on the worker. What it computes lands in `_LANDED` whether or not anybody is
                # still waiting for it — so a slow embedder is paid for once, not on every run.
                # Measured 2026-10-02: without this, a worker past the deadline computed the whole
                # vocabulary and threw it away, the index never warmed while the embedder was
                # slower than the budget, and the world's own reading spent its first hour at 1.7 s
                # a run with eighteen timeouts against 0.16 s and none once it was warm.
                got = model.embed([t for _, t in chunk])
                for (_, text), vector in zip(chunk, got):
                    _LANDED[(model.name, _digest(text))] = vector
                return got

            # The embedding is a network call and is the only thing bounded. Everything below runs
            # on this thread: the connection belongs to it, and writing to SQLite from a worker is
            # not a saving, it is a different bug.
            vectors = within_seconds(within, embed) if within else embed()
            if vectors is None:
                break                      # out of time: what is cached is what the caller gets
            for (ref, text), vector in zip(chunk, vectors):
                out[ref] = vector
                self._keep(ref, text, vector)
        if due or landed:
            self.store.conn.commit()
        return out

    def _keep(self, ref: str, text: str, vector: list) -> None:
        self.store.conn.execute(
            "INSERT OR REPLACE INTO meanings (ref, subject, kind, text, digest, model, "
            "vector) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (ref, ref, "word", text, _digest(text), self.model.name, json.dumps(vector)))

    def vector_of(self, text: str, within: float | None = None) -> list | None:
        """One text's vector, not kept: what a caller is asking *about*. None if it timed out."""
        got = (within_seconds(within, lambda: self.model.embed([text]))
               if within else self.model.embed([text]))
        return got[0] if got else None

    def forget(self) -> None:
        """Drop the index. It is a derivation; rebuilding costs time and nothing else."""
        self.store.conn.execute("DELETE FROM meanings")
        self._fresh_at.clear()        # and the mark saying it was up to date, which it is not

    # --- asking ---

    def like(self, world, text: str, limit: int = 5, kind: str | None = None,
             any_time: bool = False) -> list:
        """What in this world reads like that, best first: (entity, the text, how close).

        Reads as everything else does — what holds now. A description that was ended is still
        indexed, because it was said and the record keeps it, but it does not answer until
        any_time=True asks for it. Otherwise "what reads like a bakery" would keep returning a
        shop that closed, with nothing in the answer to say so.
        """
        self.refresh(world)
        wanted = self.model.embed([text])[0]
        holding = None if any_time else self._holding(world)
        scored = []
        for ref, subject, row_kind, said, raw in self.store.conn.execute(
                "SELECT ref, subject, kind, text, vector FROM meanings WHERE model = ?",
                (self.model.name,)):
            if kind and row_kind != kind:
                continue
            if holding is not None and ref.startswith("text:") and ref not in holding:
                continue
            if row_kind == "word":
                continue      # a cached class or type word, not something said about an entity
            scored.append((_close(wanted, json.loads(raw)), subject, said))
        scored.sort(reverse=True)
        out = []
        for score, subject, said in scored[:limit]:
            try:
                out.append((self.store.load(subject, world.classes), said, round(score, 3)))
            except KeyError:
                continue
        return out

    def entities(self, world, text: str, limit: int = 5, how: str = "mean",
                 any_time: bool = False) -> list:
        """Which entities read like that, best first: (entity, how close, the nearest text).

        An entity is not one text but several, so there are two honest ways to score it and
        they answer different questions. `how="mean"` takes the average of everything said
        about it — what is this one *generally* like — and is steadier when the texts all
        circle the same thing. `how="best"` takes its closest single text — does this one have
        anything to do with X — and is sharper when they don't: a person who does cell
        chemistry and keeps bees is not, on average, much like either.

        Either way the nearest text comes back with the score, so an answer can say which
        sentence it matched on rather than only whose it was.
        """
        self.refresh(world)
        wanted = self.model.embed([text])[0]
        holding = None if any_time else self._holding(world)
        vectors: dict = {}
        for ref, subject, said, raw in self.store.conn.execute(
                "SELECT ref, subject, text, vector FROM meanings WHERE model = ?", (self.model.name,)):
            if holding is not None and ref.startswith("text:") and ref not in holding:
                continue
            vectors.setdefault(subject, []).append((said, json.loads(raw)))
        # Only the closest texts in the whole world are considered, not every text there is.
        # An entity whose best match is mediocre never enters the answer at all, which is where
        # most of the noise came from — and it is the same work either way, since the texts are
        # scored before they are grouped.
        pool = max(POOL, limit * 10)
        ranked = sorted(((score, subject, said) for subject, texts in vectors.items()
                         for said, score in ((t, _close(wanted, v)) for t, v in texts)),
                        reverse=True)[:pool]
        kept: dict = {}
        for score, subject, said in ranked:
            kept.setdefault(subject, []).append((said, score))
        scored = []
        for subject, texts in kept.items():
            each = texts  # already in order, and already the closest ones in the world
            best_text, best = each[0]
            if how == "best":
                score = best
            elif how == "mean":
                mine = [v for said, v in vectors[subject]]
                middle = _unit([sum(values) / len(mine) for values in zip(*mine)])
                score = _close(wanted, middle)
            else:  # "all": the closest text decides, the rest of them have a say
                rest = [score for _, score in each[1:TOP_TEXTS]]
                backing = sum(rest) / len(rest) if rest else best
                score = (best + BACKING * backing) / (1 + BACKING)
            scored.append((score, subject, best_text))
        scored.sort(reverse=True)
        out = []
        for score, subject, said in scored[:limit]:
            try:
                out.append((self.store.load(subject, world.classes), round(score, 3), said))
            except KeyError:
                continue
        return out

    def similar(self, world, entity, limit: int = 5) -> list:
        """Whatever else reads like what is said about this one.

        Scored on the average of everything said about each one, which is the right question
        here: "who is generally like her" has no threshold to pass, and a person is more than
        her closest single sentence. Where there *is* a threshold — world.where(like=...) — the
        closest text is used instead, because an average pulls the irrelevant up over the line
        (measured: half again as many strangers above 0.5).
        """
        self.refresh(world)
        mine = [row[0] for row in self.store.conn.execute(
            "SELECT text FROM meanings WHERE subject = ?", (entity.id,))]
        if not mine:
            return []
        found = self.entities(world, " ".join(mine), limit=limit + 4, how="mean")
        return [(other, said, score) for other, score, said in found if other.id != entity.id][:limit]

    # --- what there is to index ---

    def _holding(self, world) -> set:
        """The names of the texts that hold right now — what an ordinary read may answer with."""
        from terraweaver import texts as texts_module

        return {row["ref"] for row in texts_module.search(world, limit=20000)}

    def _texts(self, world):
        # Remarks are not listed here. Every remark's text is stated as one more `descriptions`
        # with the period the remark holds for, so it arrives below from the texts table, with
        # its validity. Listed here as well it was indexed twice: every hit came back twice and
        # ate the caller's `limit`, and the second copy was named `comment:N`, which `_holding`
        # does not filter, so a remark that had expired went on answering `like()`
        # (docs/code-review-2026-09-30.md 3.4.7).
        #
        # Lists of texts come from the texts table, where each one has a name made from the
        # text itself. That name survives a rebuild and survives its neighbours being removed,
        # so a vector is re-made when the text changes and not when the list shifts around.
        from terraweaver import ontology, texts as texts_module

        whose = {}
        for class_name, cls in world.classes.items():
            if not ontology.dated_lists(cls._spec):
                continue
            for entity in world.all(class_name, limit=None, history=True):
                whose[getattr(entity, "subject_id", None) or entity.id] = entity.id
        for row in texts_module.search(world, any_time=True, limit=20000):
            entity_id = whose.get(row["subject"])
            # A slot may hold several tellings — descriptions usually do — and each one is its
            # own text: two people describing someone differently is two things to find them by,
            # not one blurred average.
            if entity_id and worth_embedding(row["text"]):
                yield row["ref"], entity_id, row["slot"], row["text"].strip()
        for class_name, cls in world.classes.items():
            names = [a["name"] for a in cls._spec["attributes"]
                     if a["name"] in TEXT_ATTRIBUTES and "derived" not in a
                     and a["name"] not in ontology.dated_lists(cls._spec)]
            if not names:
                continue
            for entity in world.all(class_name, limit=None, history=True):
                for name in names:
                    said = getattr(entity, name, None)
                    if isinstance(said, str) and worth_embedding(said):
                        yield f"{class_name}:{entity.id}:{name}", entity.id, name, said.strip()


def worth_embedding(text: str) -> bool:
    """Whether a text is long enough for a vector to mean anything.

    A word or two carries almost no context, and the model gives it a high score against
    anything: measured on bge-m3, a one-word text sits at 0.36 against subjects it has nothing
    to do with, where a ten-word one sits at 0.28. Indexing those spends time on the texts most
    likely to mislead. They are also the ones that need it least — a tag is found by its name
    (world.where(tagged=...)) and a short phrase by its words (world.where(mentions=...)).
    """
    words = str(text or "").split()
    return len(words) >= 3 and len(" ".join(words)) >= 12


def _digest(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()[:16]


def _unit(vector: list) -> list:
    length = math.sqrt(sum(value * value for value in vector)) or 1.0
    return [value / length for value in vector]


def _close(one: list, other: list) -> float:
    return sum(a * b for a, b in zip(one, other))
