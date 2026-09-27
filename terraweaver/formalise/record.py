"""What each reading cost and how it ended, kept so the shape of it can be seen.

One reading is a loop: the engineer writes lines, the check puts each claim in them to the picker,
a refusal goes back, three goes at most. Everything that happens is already in the trace
`formalise_one` returns — and nothing kept it. `runtime._read_what_was_said` reduces the traces to
`len(traces)` at the close, and `catch_up` prints the tallies, so a run could say how many links
were typed and nothing at all about how many goes it took, where the goes went, or how sure the
check was when it refused.

That is the wrong thing not to know. A tally of one number per run cannot tell "typed on the first
go" from "typed on the third after two refusals", and the two are different systems. Nor can it
tell a check that refuses at 0.61 from one that refuses at 1.0 — the first is the threshold doing
its work and the second is a claim that really is not in the words.

So: one row per reading, in the world's own store, and a distribution read back out of it. The rows
are the world's, not the agent's — nothing here is offered at a host's door.
"""
import json
from collections import Counter
from datetime import datetime, timezone

from terraweaver.store import run_script

SCHEMA = """
CREATE TABLE IF NOT EXISTS readings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    link_id TEXT,
    read_at TEXT,
    words TEXT,                  -- what the host said about the link
    goes INTEGER,                -- how many times lines were written for it
    went TEXT,                   -- done / gave up / not borne out by the words / …
    kind TEXT,                   -- the word it ended up under, if any
    defined INTEGER,             -- whether that word was made for it here
    seconds REAL,
    verdicts TEXT,               -- every claim the check judged, with how sure it was
    found TEXT,                  -- the word the look already had for this, if it had one
    looked INTEGER               -- whether the look could be asked at all
);
CREATE INDEX IF NOT EXISTS idx_readings_link ON readings(link_id);
"""


def _columns(conn) -> None:
    """Columns added after the table was first made, for a world that has rows already.

    `CREATE TABLE IF NOT EXISTS` does nothing to a table that exists, so a new column has to be
    asked for by name or the insert fails silently and the measurement quietly stops.
    """
    have = {row[1] for row in conn.execute("PRAGMA table_info(readings)")}
    for column, kind in (("found", "TEXT"), ("looked", "INTEGER")):
        if column not in have:
            conn.execute(f"ALTER TABLE readings ADD COLUMN {column} {kind}")


def keep(world, link, trace: dict, seconds: float) -> None:
    """Write down one reading. Never what stops a reading being reported."""
    try:
        run_script(world.store.conn, SCHEMA)
        _columns(world.store.conn)
        verdicts = [one for about in trace.get("checked", []) for one in about.get("claims", [])]
        world.store.conn.execute(
            "INSERT INTO readings (link_id, read_at, words, goes, went, kind, defined, seconds, "
            "verdicts, found, looked) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (getattr(link, "id", None), datetime.now(timezone.utc).isoformat(),
             trace.get("words", "")[:400], len(trace.get("wrote", [])), trace.get("went", ""),
             trace.get("kind"), 1 if trace.get("defined") else 0, round(seconds, 2),
             json.dumps(verdicts), trace.get("found"),
             1 if (trace.get("look") or {}).get("asked") else 0))
        world.store.conn.commit()
    except Exception:  # noqa: BLE001 - a reading is not lost because its measurement was
        return


def distribution(world) -> dict:
    """The shape of every reading this world has had: goes, endings, verdicts, seconds.

    Read from the rows and not from one run, because the question is about the system and not
    about this afternoon.
    """
    run_script(world.store.conn, SCHEMA)
    _columns(world.store.conn)
    rows = world.store.conn.execute(
        "SELECT goes, went, kind, defined, seconds, verdicts, words, found, looked "
        "FROM readings").fetchall()
    if not rows:
        return {"readings": 0}
    goes = Counter(row[0] for row in rows)
    went = Counter(row[1] or "(nothing said)" for row in rows)
    verdicts: Counter = Counter()
    sure_when_refused = []
    for row in rows:
        for one in json.loads(row[5] or "[]"):
            verdicts[one.get("verdict", "?")] += 1
            if one.get("verdict") not in (None, "says_so"):
                sure_when_refused.append(float(one.get("sure") or 0))
    seconds = sorted(float(row[4] or 0) for row in rows)
    typed = [row for row in rows if row[2]]
    # The words as the host said them, because a reading of one word and a reading of a sentence
    # are not the same task and the totals hide which of them this world is made of.
    in_words = Counter("one word" if len((row[6] or "").split()) < 2 else "several" for row in rows)
    return {
        "readings": len(rows),
        "typed": len(typed),
        "made the word": sum(1 for row in rows if row[3]),
        "goes": dict(sorted(goes.items())),
        "went": dict(went.most_common()),
        "verdicts": dict(verdicts.most_common()),
        "sure when it refused": (round(sum(sure_when_refused) / len(sure_when_refused), 2)
                                 if sure_when_refused else None),
        "seconds": {"least": round(seconds[0], 1), "middle": round(seconds[len(seconds) // 2], 1),
                    "most": round(seconds[-1], 1),
                    "all of them": round(sum(seconds), 1)},
        "what was said": dict(in_words),
        # Convergence, which is the thing a vocabulary is judged on: a word already in the record
        # found again is one idea kept, and a word made where one existed is the same idea twice.
        "the look": {"asked": sum(1 for row in rows if row[8]),
                     "found a word already there": sum(1 for row in rows if row[7])},
    }


def readable(shape: dict) -> str:
    """The distribution as lines to print."""
    if not shape.get("readings"):
        return "no reading has been recorded in this world yet."
    out = [f"{shape['readings']} reading(s): {shape['typed']} typed, "
           f"{shape['made the word']} of them under a word made for it"]
    out.append("  goes:      " + ", ".join(f"{n}x{k}" for k, n in shape["goes"].items()))
    out.append("  ended:     " + "; ".join(f"{k} {n}" for k, n in shape["went"].items()))
    if shape["verdicts"]:
        out.append("  verdicts:  " + "; ".join(f"{k} {n}" for k, n in shape["verdicts"].items())
                   + (f"  (sure when refusing: {shape['sure when it refused']})"
                      if shape["sure when it refused"] is not None else ""))
    took = shape["seconds"]
    out.append(f"  seconds:   least {took['least']}, middle {took['middle']}, most {took['most']}, "
               f"{took['all of them']} in all")
    out.append("  said as:   " + "; ".join(f"{k} {n}" for k, n in shape["what was said"].items()))
    look = shape["the look"]
    out.append(f"  the look:  asked {look['asked']}, already had the word "
               f"{look['found a word already there']}")
    return "\n".join(out)
