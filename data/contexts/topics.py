"""Topic runs: can the journal be cut where the context changes? Truth: the user message a write came from."""
import glob, json, random, re
import numpy as np

ROOT = __import__("pathlib").Path(__file__).resolve().parents[2]
norm = lambda s: " ".join(re.sub(r"[^a-z0-9 ]", " ", s.lower()).split())

def journals():
    """Each run's history, in journal order: (text, vector, message it came from)."""
    out = []
    for f in sorted(glob.glob(f"{ROOT}/experiments/results/13_dialogues/*/run.json")):
        r = json.load(open(f)); mem = f"{ROOT}/var/memory/{r['memory']}"
        try:
            text = open(f"{mem}/facts.md").read()
            vec = {j["n"]: np.array(j["v"]) for j in map(json.loads, open(f"{mem}/vectors.jsonl"))}
        except OSError:
            continue
        entries = {int(m.group(1)): m.group(2).strip() for m in re.finditer(r"^## #(\d+) [^\n]*\n(.*?)(?=\n## #|\Z)", text, re.S | re.M)}
        turns = [t for s in r["history"] for t in s]
        codes = [norm(" ".join(str(c["input"]) for c in t["calls"] if c["tool"] == "run")) for t in turns]
        seq = []
        for n in sorted(entries):
            hit = next((i for i, c in enumerate(codes) if norm(entries[n])[:60] in c), None)
            if hit is not None and n in vec:
                seq.append((entries[n], vec[n] / np.linalg.norm(vec[n]), f"{r['scenario']}{f[-12:-9]}:m{hit}", turns[hit]["say"]))
        out.append(seq)
    return out

def cuts(U, how, th, k=3):
    if how == "adjacent":
        return {i for i in range(len(U) - 1) if U[i] @ U[i + 1] < th}
    # continues: the next entry is near none of the run's last k entries
    out, start = set(), 0
    for i in range(len(U) - 1):
        recent = U[max(start, i - k + 1):i + 1]
        if max(recent @ U[i + 1]) < th:
            out.add(i); start = i + 1
    return out

def f1(pred, true):
    p = sum(any(abs(a - b) <= 0 for b in true) for a in pred) / max(1, len(pred))
    r = sum(any(abs(a - b) <= 0 for a in pred) for b in true) / max(1, len(true))
    return p, r, 2 * p * r / max(1e-9, p + r)

runs = journals()
print("runs:", len(runs), "entries:", sum(map(len, runs)), "messages:", sum(len({x[2] for x in s}) for s in runs))
# each run on its own: a real journal, its own messages in order
for how in ("adjacent", "continues"):
    for th in (0.45, 0.5, 0.55, 0.6, 0.65, 0.7):
        P = R = 0; tp = fp = fn = 0
        for s in runs:
            U = np.array([x[1] for x in s]); lab = [x[2] for x in s]
            true = {i for i in range(len(s) - 1) if lab[i] != lab[i + 1]}
            pred = cuts(U, how, th)
            tp += len(pred & true); fp += len(pred - true); fn += len(true - pred)
        p, r = tp / max(1, tp + fp), tp / max(1, tp + fn)
        print(f"{how:9s} th {th:.2f}: precision {p:.2f} recall {r:.2f} F1 {2*p*r/max(1e-9,p+r):.2f}  (cuts {tp+fp}, true {tp+fn})")

th = 0.60
print(f"\nat {th}, messages joined (no cut between two messages):")
for s in runs:
    for i in range(len(s) - 1):
        sim = s[i][1] @ s[i + 1][1]
        if s[i][2] != s[i + 1][2] and sim >= th:
            print(f"  {sim:.2f} {s[i][3][:55]!r} + {s[i+1][3][:55]!r}")
print(f"\nat {th}, cut inside one message:")
for s in runs:
    for i in range(len(s) - 1):
        sim = s[i][1] @ s[i + 1][1]
        if s[i][2] == s[i + 1][2] and sim < th:
            print(f"  {sim:.2f} [{s[i][3][:40]!r}] {s[i][0][:50]!r} | {s[i+1][0][:50]!r}")
