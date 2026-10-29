"""Cut a labelled history into contexts by the embedding gap, and link each fragment to where it began."""
import sys
import numpy as np
from fastembed import TextEmbedding
sys.path.insert(0, sys.argv[1]); from history import SESSIONS


model = TextEmbedding("BAAI/bge-small-en-v1.5")
rows = [(s, lab, text) for s, (_, entries) in enumerate(SESSIONS) for lab, text in entries]
U = np.array(list(model.embed([t for _, _, t in rows]))); U /= np.linalg.norm(U, axis=1, keepdims=True)
lab = [l for _, l, _ in rows]; ses = [s for s, _, _ in rows]
true = {i for i in range(len(rows) - 1) if lab[i] != lab[i + 1]}
print(f"{len(rows)} entries, {len(SESSIONS)} sessions, {len(true)} context changes "
      f"({sum(ses[i] == ses[i+1] for i in true)} inside a session); "
      f"{sum(ses[i] != ses[i+1] and lab[i] == lab[i+1] for i in range(len(rows)-1))} context goes on across a session")

def cut(th, k=1):
    out, start = set(), 0
    for i in range(len(U) - 1):
        if max(U[max(start, i - k + 1):i + 1] @ U[i + 1]) < th:
            out.add(i); start = i + 1
    return out

sims = np.array([U[i] @ U[i + 1] for i in range(len(U) - 1)])
print(f"similarity at a context change: median {np.median(sims[list(true)]):.2f}, max {sims[list(true)].max():.2f}; "
      f"within a context: median {np.median(np.delete(sims, list(true))):.2f}, min {np.delete(sims, list(true)).min():.2f}")
for k in (1, 2):
    for th in (0.55, 0.6, 0.65, 0.7):
        pred = cut(th, k); tp = len(pred & true)
        p, r = tp / max(1, len(pred)), tp / len(true)
        print(f"  last {k}, th {th:.2f}: precision {p:.2f} recall {r:.2f} F1 {2*p*r/max(1e-9,p+r):.2f}")

print("\nwithin-context gaps below 0.6:")
for i in range(len(U) - 1):
    if i not in true and sims[i] < 0.6:
        print(f"  {sims[i]:.2f} [{lab[i]}] {rows[i][2][:55]!r} | {rows[i+1][2][:55]!r}")
print("context changes above 0.6:")
for i in sorted(true):
    if sims[i] >= 0.6:
        print(f"  {sims[i]:.2f} {lab[i]}->{lab[i+1]}: {rows[i][2][:55]!r} | {rows[i+1][2][:55]!r}")

# linking: each true fragment that goes on a context, to the most similar earlier fragment
bounds = [0] + [i + 1 for i in sorted(true)] + [len(rows)]
frags = [(lab[a], U[a:b].mean(0) / np.linalg.norm(U[a:b].mean(0)), a, b) for a, b in zip(bounds, bounds[1:])]
hits = []
for j, (l, v, a, b) in enumerate(frags):
    earlier = frags[:j]
    if any(e[0] == l for e in earlier):
        best = max(earlier, key=lambda e: e[1] @ v)
        hits.append(best[0] == l)
        if best[0] != l:
            print(f"  linked wrong: {l} {rows[a][2][:50]!r} -> {best[0]} {rows[best[2]][2][:50]!r}")
print(f"\nfragment linked to an earlier fragment of its context: {sum(hits)}/{len(hits)}")

# over-cut, then join: fine fragments, each joined to the most similar earlier context if near enough
def contexts(th_cut, th_join):
    cuts_ = sorted(cut(th_cut)); bounds = [0] + [i + 1 for i in cuts_] + [len(rows)]
    ctx, of = [], [0] * len(rows)   # ctx: list of mean vectors
    for a, b in zip(bounds, bounds[1:]):
        v = U[a:b].mean(0); v /= np.linalg.norm(v)
        sims_ = [c @ v for c in ctx]
        if sims_ and max(sims_) >= th_join:
            j = int(np.argmax(sims_)); members = [i for i in range(a) if of[i] == j] + list(range(a, b))
            m = U[members].mean(0); ctx[j] = m / np.linalg.norm(m)
        else:
            j = len(ctx); ctx.append(v)
        for i in range(a, b):
            of[i] = j
    return of

def pairs(of):
    tp = fp = fn = 0
    for i in range(len(rows)):
        for j in range(i + 1, len(rows)):
            same, got = lab[i] == lab[j], of[i] == of[j]
            tp += same and got; fp += got and not same; fn += same and not got
    p, r = tp / max(1, tp + fp), tp / max(1, tp + fn)
    return p, r, 2 * p * r / max(1e-9, p + r)

print(f"\ncontexts over the whole history ({len(set(lab))} true), pairs of entries in one context:")
for th_cut in (0.6, 0.7):
    for th_join in (0.6, 0.65, 0.7, 0.75, 0.8):
        of = contexts(th_cut, th_join); p, r, f = pairs(of)
        print(f"  cut <{th_cut}, join >={th_join}: {len(set(of))} contexts, precision {p:.2f} recall {r:.2f} F1 {f:.2f}")
of = contexts(0.7, 0.75)
for j in sorted(set(of)):
    print(f"  context {j}: " + ", ".join(f"{l}×{n}" for l, n in sorted({l: sum(1 for i in range(len(rows)) if of[i]==j and lab[i]==l) for l in set(lab)}.items(), key=lambda x:-x[1]) if n))
