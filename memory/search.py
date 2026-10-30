"""Finding the entries a question needs: by words and by meaning, fused.

Every reader of the memory (`ask`, `context`) used to hand the whole journal to a model. That holds
while the journal is small and fails as it grows. So two channels each rank the entries, and the
ranks are fused (reciprocal rank fusion):

- **words** — BM25 over the entries' texts;
- **meaning** — cosine over embeddings (bge-small, local, through fastembed), each entry
  embedded once and kept beside the journal.

What the question names — people, things — the graph finds (`memory/graph.py`). What comes out
here is entry numbers; the texts are what the answer is made of.
"""
import hashlib
import json
import math
import os
import re
from collections import Counter
from pathlib import Path

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


class OpenRouterEncoder:
    """The same two calls as fastembed's `TextEmbedding`, over OpenRouter's embeddings API.

    For a machine with no room for a local model. Vectors are normalised, since the search ranks
    by a dot product. The model is `TERRAWEAVER_EMBED_MODEL`; the vectors kept beside a journal
    belong to one model, so a journal is not switched between encoders.
    """
    BATCH = 64

    def __init__(self):
        from openai import OpenAI
        self.model = os.environ.get("TERRAWEAVER_EMBED_MODEL", "nvidia/nemotron-3.5-embed-1b:free")
        self.client = OpenAI(base_url="https://openrouter.ai/api/v1", api_key=os.environ["OPENROUTER_API_KEY"],
                             max_retries=5)

    def embed(self, texts):
        texts = list(texts)
        for i in range(0, len(texts), self.BATCH):
            batch = self.client.embeddings.create(model=self.model, input=texts[i:i + self.BATCH])
            for item in sorted(batch.data, key=lambda d: d.index):
                v = item.embedding
                norm = math.sqrt(sum(x * x for x in v)) or 1.0
                yield [x / norm for x in v]

    query_embed = embed


class Search:
    def __init__(self, entries, vectors: Path, model: str = "BAAI/bge-small-en-v1.5"):
        """`entries()` gives {number: text} of what is held; the vectors are kept at `vectors`."""
        self.entries, self.vectors_path, self.model_name = entries, vectors, model
        self._model = None
        self._vectors: dict[int, tuple[str, list[float]]] = {}
        if vectors.exists():
            for line in vectors.read_text().splitlines():
                if line.strip():
                    r = json.loads(line)
                    self._vectors[r["n"]] = (r["hash"], r["v"])

    # --- the channels ----------------------------------------------------------------------

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

    def find(self, question: str, limit: int = 12, channels=("words", "meaning")) -> list[int]:
        """The fused ranking, cut at `limit`."""
        ranked = {"words": self.by_words, "meaning": self.by_meaning}
        score: Counter = Counter()
        for name in channels:
            for rank, n in enumerate(ranked[name](question)):
                score[n] += 1 / (RRF_K + rank)
        return sorted(score, key=lambda n: (-score[n], -n))[:limit]

    # --- embeddings, kept beside the journal ------------------------------------------------

    def _encoder(self):
        if self._model is None:
            if os.environ.get("TERRAWEAVER_EMBEDDINGS") == "openrouter":
                self._model = OpenRouterEncoder()
            else:
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
