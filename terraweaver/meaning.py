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
import urllib.error
import urllib.request

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

# Free-text attributes worth finding by meaning. Names are not here on purpose: a name is for
# identity, and identity is not decided by proximity.
TEXT_ATTRIBUTES = ("notes", "description", "title", "value")


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


def embedder():
    """The best available, without ceremony: the local model if it answers, else the fallback."""
    try:
        urllib.request.urlopen(f"{OLLAMA}/api/tags", timeout=1).read()
        return Ollama()
    except (urllib.error.URLError, OSError, ValueError):
        return Plain()


class Meanings:
    def __init__(self, store, model=None):
        self.store = store
        self.model = model or embedder()
        run_script(store.conn, SCHEMA)
        store.conn.commit()

    # --- keeping the index up to date ---

    def refresh(self, world, limit: int = 500) -> int:
        """Embed what has changed since last time. Returns how many texts were done."""
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
        return len(due)

    def forget(self) -> None:
        """Drop the index. It is a derivation; rebuilding costs time and nothing else."""
        self.store.conn.execute("DELETE FROM meanings")

    # --- asking ---

    def like(self, world, text: str, limit: int = 5, kind: str | None = None) -> list:
        """What in this world reads like that, best first: (entity, the text, how close)."""
        self.refresh(world)
        wanted = self.model.embed([text])[0]
        scored = []
        for subject, row_kind, said, raw in self.store.conn.execute(
                "SELECT subject, kind, text, vector FROM meanings WHERE model = ?", (self.model.name,)):
            if kind and row_kind != kind:
                continue
            scored.append((_close(wanted, json.loads(raw)), subject, said))
        scored.sort(reverse=True)
        out = []
        for score, subject, said in scored[:limit]:
            try:
                out.append((self.store.load(subject, world.classes), said, round(score, 3)))
            except KeyError:
                continue
        return out

    def similar(self, world, entity, limit: int = 5) -> list:
        """Whatever else reads like what is said about this one."""
        mine = [row[0] for row in self.store.conn.execute(
            "SELECT text FROM meanings WHERE subject = ?", (entity.id,))]
        if not mine:
            return []
        found = self.like(world, " ".join(mine), limit=limit + 4)
        return [hit for hit in found if hit[0].id != entity.id][:limit]

    # --- what there is to index ---

    def _texts(self, world):
        for comment in world.comments.search(limit=5000, any_time=True):
            if comment.about is not None and comment.text:
                yield f"comment:{comment.id}", comment.about.id, "comment", comment.text
        for class_name, cls in world.classes.items():
            names = [a["name"] for a in cls._spec["attributes"]
                     if a["name"] in TEXT_ATTRIBUTES and "derived" not in a]
            if not names:
                continue
            for entity in world.all(class_name, limit=None, history=True):
                for name in names:
                    said = getattr(entity, name, None)
                    if isinstance(said, str) and len(said.strip()) > 8:
                        yield f"{class_name}:{entity.id}:{name}", entity.id, name, said.strip()


def _digest(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()[:16]


def _unit(vector: list) -> list:
    length = math.sqrt(sum(value * value for value in vector)) or 1.0
    return [value / length for value in vector]


def _close(one: list, other: list) -> float:
    return sum(a * b for a, b in zip(one, other))
