"""Finding the entries a question needs: by structure, by words and by meaning, fused.

Every reader of the memory (`ask`, `context`, `search_memory`) used to hand the whole journal to a
model. That holds while the journal is small and fails as it grows; and on FactConsolidation the
structure alone found every gold fact in 3.6 texts a question, against 462. But a question does
not always name a thing — "my bathroom fan" named none the structure held as a name — so three
channels each rank the entries, and the ranks are fused (reciprocal rank fusion):

- **structure** — the things the question names, their entries first, then the entries of the
  things they share an entry with (one hop);
- **words** — BM25 over the entries' texts;
- **meaning** — cosine over embeddings (bge-small, local, through fastembed), each entry
  embedded once and kept beside the journal.

What comes out is entry numbers; the texts are what the answer is made of.
"""
import hashlib
import json
import math
import re
from collections import Counter
from pathlib import Path

# Words of a thing's name that name nothing on their own: "the user" is in every entry.
_GENERIC = set("""the user user's users a an of and at in on for to my me i mr mrs ms""".split())
_STOP = set("""a an the and or but of to in on at for with by from is are was were be been it its this
that these those he she they we you i me my your his her their our them him us as if so not no do does
did has have had will would can could should about into than then there here what which who whom
when where why how all any some just also very""".split())
RRF_K = 60


def _tokens(text: str) -> list[str]:
    words = re.findall(r"[a-z0-9$]+(?:'[a-z]+)?", text.lower())
    out = []
    for w in words:
        w = re.sub(r"'s$", "", w)
        if w in _STOP or len(w) < 2:
            continue
        out.append(w[:-1] if len(w) > 4 and w.endswith("s") and not w.endswith("ss") else w)
    return out


class Search:
    def __init__(self, structure, entries, vectors: Path, model: str = "BAAI/bge-small-en-v1.5", image=None):
        """`structure` is the proto's index; `entries()` gives {number: text} of what is held;
        `image()`, if given, what the world read of it (`memory.world.Mirror.image`)."""
        self.structure, self.entries, self.vectors_path, self.model_name = structure, entries, vectors, model
        self.image = image
        self._model = None
        self._vectors: dict[int, tuple[str, list[float]]] = {}
        if vectors.exists():
            for line in vectors.read_text().splitlines():
                if line.strip():
                    r = json.loads(line)
                    self._vectors[r["n"]] = (r["hash"], r["v"])

    # --- the channels ----------------------------------------------------------------------

    def named(self, question: str) -> list[str]:
        """Things the question names: the whole name, or a word of it of four letters or more."""
        said = question.lower()
        words = set(_tokens(question)) | set(re.findall(r"[a-z0-9']+", said))
        found = []
        for t in self.structure._things().values():
            name = t["name"].lower()
            if re.search(r"(?<!\w)" + re.escape(name) + r"(?!\w)", said):
                found.append(t["thing"])
                continue
            parts = [w for w in re.findall(r"[a-z0-9']+", name) if len(w) >= 4 and w not in _GENERIC]
            if any(w in words or (w.endswith("s") and w[:-1] in words) for w in parts):
                found.append(t["thing"])
        return found + [t for t in self.read_as(words) if t not in found]

    def read_as(self, words: set[str]) -> list[str]:
        """Things the question reaches through what the world read: a class it names ("my
        friends" — Friend), or a kind of link ("his girlfriend" — GirlfriendOf, both ends)."""
        image = self.image() if self.image else None
        if not image:
            return []

        def said(word: str) -> bool:
            parts = [w.lower() for w in re.findall(r"[A-Z][a-z]+|[a-z]+", word)]
            parts = [w for w in parts if len(w) >= 4 and w not in _STOP]
            return bool(parts) and any(w in words or w + "s" in words or (w.endswith("s") and w[:-1] in words)
                                       for w in parts)
        out = [g for g, t in image["things"].items() if t["class"] != "Thing" and said(t["class"])]
        for link in image["links"]:
            if said(link["type"]):
                out += [link["subject"], link["object"]]
        return list(dict.fromkeys(out))

    def by_structure(self, question: str) -> list[int]:
        held = self.entries()
        named, hosts = set(), self.structure._things()
        for thing in self.named(question):
            # A thing the world read and the host never named ("r:…") is in the image only: it is
            # reached through the image's links. Looked up in the host's structure, it failed every
            # search and every ask (2026-10-27).
            named |= self.structure.one_with(self.structure.thing("q", thing)) if thing in hosts else {thing}
        if not named:
            return []
        rows = [r for r in self.structure.records if r.get("entry") in held]
        image = self.image() if self.image else None
        for link in (image or {}).get("links", []):
            if link.get("entry") in held:
                rows.append({"entry": link["entry"], "about": [link["subject"], link["object"]]})
        direct = Counter()
        for r in rows:
            direct[r["entry"]] = max(direct[r["entry"]], len(named & set(r["about"])))
        near = set()
        for r in rows:
            if named & set(r["about"]):
                near |= set(r["about"])
        near -= named
        hop = {r["entry"] for r in rows if near & set(r["about"])} - {n for n, c in direct.items() if c}
        first = sorted((n for n, c in direct.items() if c), key=lambda n: (-direct[n], -n))
        return first + sorted(hop, reverse=True)

    def by_words(self, question: str) -> list[int]:
        held = self.entries()
        docs = {n: _tokens(text) for n, text in held.items()}
        if not docs:
            return []
        avg = sum(len(d) for d in docs.values()) / len(docs)
        df = Counter(w for d in docs.values() for w in set(d))
        scores = {}
        for n, d in docs.items():
            tf, score = Counter(d), 0.0
            for w in set(_tokens(question)):
                if w in tf:
                    idf = math.log(1 + (len(docs) - df[w] + 0.5) / (df[w] + 0.5))
                    score += idf * tf[w] * 2.2 / (tf[w] + 1.2 * (0.25 + 0.75 * len(d) / avg))
            if score:
                scores[n] = score
        return sorted(scores, key=lambda n: (-scores[n], -n))

    def by_meaning(self, question: str) -> list[int]:
        held = self.entries()
        if not held:
            return []
        self._embed(held)
        import numpy as np
        q = np.array(next(iter(self._encoder().query_embed([question]))))
        scores = {n: float(np.dot(q, self._vectors[n][1])) for n in held if n in self._vectors}
        return sorted(scores, key=lambda n: -scores[n])

    # --- fused --------------------------------------------------------------------------------

    def find(self, question: str, limit: int = 12, channels=("structure", "words", "meaning"),
             whole: bool = True) -> list[int]:
        """The fused ranking, cut at `limit`; with `whole`, every entry about a thing the question
        names comes first, beyond the limit. "Summarise everything about Darren" needs all of
        Darren's thirty entries, and twelve fused ones lost 7 of 31 MemOps probes the whole
        journal answered. What the question does not name, the words and meaning find."""
        ranked = {"structure": self.by_structure, "words": self.by_words, "meaning": self.by_meaning}
        score: Counter = Counter()
        for name in channels:
            for rank, n in enumerate(ranked[name](question)):
                score[n] += 1 / (RRF_K + rank)
        fused = sorted(score, key=lambda n: (-score[n], -n))
        if not (whole and "structure" in channels):
            return fused[:limit]
        named = self.about_named(question)
        return named + [n for n in fused if n not in set(named)][:limit]

    def about_named(self, question: str) -> list[int]:
        """Every held entry about a thing the question names (and things settled the same)."""
        held, group, hosts = self.entries(), set(), self.structure._things()
        for thing in self.named(question):
            group |= self.structure.one_with(self.structure.thing("q", thing)) if thing in hosts else {thing}
        image = self.image() if self.image else None
        read = [{"entry": l["entry"], "about": [l["subject"], l["object"]]}
                for l in (image or {}).get("links", []) if l.get("entry") is not None]
        return sorted({r["entry"] for r in [*self.structure.records, *read]
                       if r.get("entry") in held and group & set(r["about"])}, reverse=True)

    # --- embeddings, kept beside the journal ------------------------------------------------

    def _encoder(self):
        if self._model is None:
            from fastembed import TextEmbedding
            self._model = TextEmbedding(self.model_name)
        return self._model

    def _embed(self, held: dict[int, str]) -> None:
        """Embed what is new or changed since last time; an entry's vector is kept by its text's
        hash, so a forgotten number never reads with another's vector."""
        if set(self._vectors) - set(held):
            self.drop(set(self._vectors) - set(held))
        todo = [(n, text, hashlib.sha1(text.encode()).hexdigest()[:16]) for n, text in held.items()
                if self._vectors.get(n, ("",))[0] != hashlib.sha1(text.encode()).hexdigest()[:16]]
        if not todo:
            return
        vectors = list(self._encoder().embed([" ".join(text.split()) for _, text, _ in todo]))
        self.vectors_path.parent.mkdir(parents=True, exist_ok=True)
        with self.vectors_path.open("a") as file:
            for (n, _, h), v in zip(todo, vectors):
                self._vectors[n] = (h, [float(x) for x in v])
                file.write(json.dumps({"n": n, "hash": h, "v": self._vectors[n][1]}) + "\n")

    def drop(self, numbers) -> None:
        """Delete these entries' vectors from disk: a vector says much of what its text said, so a
        forgotten entry's goes with it."""
        for n in numbers:
            self._vectors.pop(n, None)
        self.vectors_path.parent.mkdir(parents=True, exist_ok=True)
        self.vectors_path.write_text("".join(json.dumps({"n": n, "hash": h, "v": v}) + "\n"
                                             for n, (h, v) in sorted(self._vectors.items())))
