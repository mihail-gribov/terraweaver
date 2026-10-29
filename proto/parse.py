"""Text into structure: the things one text names, their values, and what joins them.

One text is read whole, in one call — a message, a page — because what joins two things is said
across sentences, and only a reader of the whole can see it. Nemotron proposes; every value and
every link stands on the text's own words, checked twice before anything is kept:

- by code: the quote is in the text, and a number's quote has a number in it;
- by the decision model: the quote says what the claim says.

Measured 2026-10-26 on 259 shop and review pages: told to leave a value out when the page doesn't
say it, the model wrote "works without a cloud" from "LiDAR navigation", and from "the app walked
me through connecting to WiFi". Asking it more firmly would not have held; checking does.

A thing is the one the memory holds under the same name and kind, else a new one.

    from proto.parse import parse
    parse(structure, session, page_text, source="https://…", want="robot vacuums and their specs")
"""
import json
import re
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from proto.models import role  # noqa: E402

READ = """Read the text below and say what it states{want}. Answer with JSON only:
{{"things": [{{"name": "...", "kind": "one word or two", "values": {{"<attribute>": {{"value": \
<number, word or true/false>, "quote": "the text's exact words"}}}}}}],
 "links": [{{"from": "<name>", "to": "<name>", "as": "<word>", "says": "the link as a short sentence", \
"quote": "the text's exact words"}}]}}
Things are everything the text names: people, organisations, places, products, events. Whoever \
writes in the first person ("my sister") is "the user". Attributes are short snake_case names with \
their unit where there is one (price_eur, noise_db). Only what the text states; every value and \
link has its quote, copied exactly; a number's quote has the words that say what it is ("Schwellen \
bis 2 cm", not "2 cm").

Example. Text: "My manager at Lumen is Olga; she lives in Porto."
{{"things": [{{"name": "the user", "kind": "person", "values": {{}}}}, {{"name": "Olga", "kind": "person", \
"values": {{}}}}, {{"name": "Lumen", "kind": "organisation", "values": {{}}}}, {{"name": "Porto", "kind": "place", \
"values": {{}}}}],
 "links": [{{"from": "Olga", "to": "the user", "as": "manager_of", "says": "Olga is the user's manager", \
"quote": "My manager at Lumen is Olga"}}, {{"from": "the user", "to": "Lumen", "as": "works_at", "says": \
"The user works at Lumen", "quote": "My manager at Lumen is Olga"}}, {{"from": "Olga", "to": "Lumen", "as": \
"works_at", "says": "Olga works at Lumen", "quote": "My manager at Lumen is Olga"}}, {{"from": "Olga", "to": \
"Porto", "as": "lives_in", "says": "Olga lives in Porto", "quote": "she lives in Porto"}}]}}

{fields}{context}Text{source}:
{text}"""

CONTEXT = """What came before, and what is already known — to understand the text by (who "she", "my \
team", "our office" are), not to read: take nothing from it, and quote only the text.
{context}

"""

FIELDS = """Values: use exactly these attribute names, and no others —
{listed}

"""

def _models():
    """The reader and the judge."""
    return role("reader"), role("judge")


def words(text: str) -> str:
    return " ".join(re.sub(r"[^\w.,%€$]+", " ", str(text).lower()).split())


def holds(decider, quote: str, claim: str) -> float:
    """p that the quote says the claim."""
    try:
        return decider.noul(f'Words from a text:\n"{quote}"', f"Do these words say that {claim}?",
                            true="yes, the words say it", false="no, the words don't say it")["p"]["yes"]
    except Exception:  # noqa: BLE001 - what can't be checked is not kept
        return 0.0


def claim(name: str, meant: str, value) -> str:
    """A value as the sentence it amounts to. Glued as "X has works without an app (yes/no): yes",
    the judge read 0.52 off a quote saying the opposite — "App-Steuerung" — and kept it; said as
    "X works without an app" it read 0.30 (2026-10-26)."""
    meant = re.sub(r"\s*\([^)]*\)", "", meant).strip()
    yes = value is True or str(value).strip().lower() in ("yes", "true", "ja")
    no = value is False or str(value).strip().lower() in ("no", "false", "nein")
    if yes:
        return f"{name}: {meant}"
    if no:
        return f"it is not so that {name}: {meant}"
    return f"{name} — {meant}: {value}"


def read(text: str, want: str = "", source: str = "", fields: dict | None = None, context: str = "") -> dict:
    """What the text states, checked: {"things": [...], "links": [...], "dropped": [...]}.
    `context` — earlier entries and known things — is shown apart, to understand the text by; a
    quote must stand in `text`, so nothing is kept on the context's words."""
    writer, decider = _models()
    said = writer.say("Answer exactly in the form asked.",
                      READ.format(want=f", about {want}" if want else "", source=f" ({source})" if source else "",
                                  fields=FIELDS.format(listed="\n".join(f"  {k}: {v}" for k, v in fields.items()))
                                  if fields else "", context=CONTEXT.format(context=context[:6000]) if context else "",
                                  text=text[:16000]), room=12000, thinking=False)
    try:
        got = json.loads(said[said.find("{"):said.rfind("}") + 1])
    except ValueError:
        return {"things": [], "links": [], "dropped": []}
    plain, claims, dropped = words(text), [], []
    things = [t for t in got.get("things") or [] if isinstance(t, dict) and t.get("name")]
    for t in things:
        if fields:
            t["values"] = {a: v for a, v in (t.get("values") or {}).items() if a in fields}
        for attr, v in list((t.get("values") or {}).items()):
            v = v if isinstance(v, dict) else {"value": v}
            quote, value = str(v.get("quote") or ""), v.get("value")
            numeric = isinstance(value, (int, float)) and not isinstance(value, bool)
            if not isinstance(value, (int, float, str, bool)) or value in (None, "") or not words(quote) or words(quote) not in plain or \
                    (numeric and not re.search(r"\d", quote)) or (numeric and not _says_what(quote, attr)):
                dropped.append((t["name"], attr, value, quote))
                del t["values"][attr]
                continue
            t["values"][attr] = {"value": value, "quote": quote}
            claims.append((t, attr, quote, claim(t["name"], (fields or {}).get(attr) or attr.replace("_", " "), value)))
    names = {t["name"] for t in things}
    links = [l for l in got.get("links") or [] if isinstance(l, dict) and l.get("from") in names
             and l.get("to") in names and words(l.get("quote") or "") and words(l["quote"]) in plain]
    for l in links:
        says = str(l.get("says") or f"{l['from']} is {l.get('as') or 'linked'} to {l['to']}").rstrip(".")
        claims.append((l, None, l["quote"], says))
    with ThreadPoolExecutor(16) as pool:
        ps = list(pool.map(lambda c: holds(decider, c[2], c[3]), claims))
    for (owner, attr, quote, said), p in zip(claims, ps):
        if p >= 0.5:
            continue
        dropped.append((said, quote, round(p, 2)))
        if attr:
            owner["values"].pop(attr, None)
        else:
            owner["dropped"] = True
    return {"things": things, "links": [l for l in links if not l.get("dropped")], "dropped": dropped}


UNITS = {"cm", "mm", "m", "kg", "g", "db", "w", "v", "mah", "min", "h", "eur", "euro", "euros", "usd", "pa", "l", "ml"}


def _says_what(quote: str, attr: str = "") -> bool:
    """A number's quote names what the number is. "10.2 cm" alone was kept as a threshold height
    of 10.2 cm; it was the robot's own height (2026-10-26): a length fits any dimension. A sum of
    money is the one bare number that says what it is — a price — and on shop pages most prices
    stand alone ("249 €": 24 of 41), so a price's bare amount stands."""
    if re.search(r"(eur|usd|price)", attr) and re.search(r"[€$]|\beur|\busd", quote.lower()):
        return True
    return any(w not in UNITS for w in re.findall(r"[^\W\d_]{2,}", quote.lower()))


def key(name: str) -> str:
    return re.sub(r"[^a-z0-9+]", "", name.lower())


def parse(structure, session: str, text: str, source: str = "", want: str = "") -> dict:
    """Read the text and keep what it states: things, their values, their links. Returns what
    was kept and what was dropped, so the caller sees both."""
    return keep(structure, session, read(text, want, source), source)


def keep(structure, session: str, got: dict, source: str = "") -> dict:
    """Write what `read` found. A thing is the one already held under the same name, else new:
    a page calls the same model a product here and a robot vacuum there."""
    held = {key(t.name): t for t in structure.things(session)}
    made = {}
    for t in got["things"]:
        kind = (t.get("kind") or "").strip().lower().replace(" ", "_") or None
        thing = held.get(key(t["name"])) or structure.entity(session, t["name"], kind=kind)
        held[key(t["name"])] = made[t["name"]] = thing
        for attr, v in t["values"].items():
            thing.set(attr, v["value"], f"{t['name']}: {attr} {v['value']} — \"{v['quote']}\"", source or "text")
    for l in got["links"]:
        structure.link(session, made[l["from"]], made[l["to"]],
                       f"{str(l.get('says') or l['from'] + ' — ' + l['to']).rstrip('.')}: \"{l['quote']}\"",
                       as_=l.get("as"), source=source or "text")
    return {"things": len(made), "values": sum(len(t["values"]) for t in got["things"]),
            "links": len(got["links"]), "dropped": got["dropped"]}
