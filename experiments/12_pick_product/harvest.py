"""Gather a database of candidates from the web: every robot vacuum the pages offer, deduplicated.

    .venv/bin/python experiments/12_pick_product/harvest.py <out> --need "a robot vacuum"
    .venv/bin/python experiments/12_pick_product/harvest.py <out> --from extract   # redo a stage

Stages, each kept in <out> so a later one can be redone alone:
  queries   Nemotron writes searches for the kind of thing, from the need alone: no person in them
  search    Tavily (--engine) through ait-search, every query, the top pages fetched (queries.json -> pages.jsonl)
  pages     the decision model: does the page name specific models with a price or a spec?
  extract   Nemotron: each product the page names, its fields, and the page's words for each
  verify    the decision model: do those words say what the field claims? If not, it is unknown
  catalog   one row per brand + model; offers from many pages fold into a price interval

Nothing here is the user's: the need is a kind of thing, and the user's conditions come in only
when the catalogue is searched (find.py).
"""
import argparse
import concurrent.futures
import json
import re
import subprocess
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
from terraweaver.nemotron import Nemotron as Reader  # noqa: E402

SUPER = "nvidia/nemotron-3-super-120b-a12b"
STAGES = ["queries", "search", "pages", "extract", "verify", "catalog"]

QUERIES = """Today is {today}. Write {n} web search queries that together find as many specific models of {need} \
on sale in Germany as possible, with their prices and specifications: shop listings, price \
comparisons, tests and reviews, lists of best models in each price range, models for particular \
needs (pets, carpets, thresholds, quiet, without cloud, budget). Mix German and English. Name kinds \
of thing only, never a person. Answer with a JSON list of strings and nothing else."""

EXTRACT = """Below is the text of a web page. List every specific model of {need} it names \
(brand and model), with what the page says about each. Answer with a JSON list, one object per \
model, and nothing else:
[{{"brand": "...", "model": "...", "price_eur": number or null, "noise_db": number or null,
  "threshold_mm": number or null, "suction_pa": number or null, "hepa": true/false/null,
  "pet_hair": true/false/null, "carpet": true/false/null, "needs_cloud": true/false/null,
  "mop": true/false/null, "text": "one sentence in English: what the page says about it",
  "quotes": {{"<field>": "the page's exact words that say it", ...}}}}]
A field is null unless the page says it of that model, and every field that is not null has its quote: words copied exactly from the page, a few to a sentence. Prices in euros as the page gives them.
If the page names no specific model, answer [].

Page ({url}):
{body}"""

PAGE = ("Does this page name specific {need} models (brand and model) together with a price or a "
        "specification for at least one of them?")


def say(reader: Reader, prompt: str, room: int = 6000) -> str:
    return reader.say("Answer exactly in the form asked.", prompt, room=room, thinking=False)


def as_json(said: str, opener: str):
    start, end = said.find(opener), said.rfind("]" if opener == "[" else "}")
    try:
        return json.loads(said[start:end + 1]) if start >= 0 else None
    except ValueError:
        return None


def jsonl(path: Path) -> list[dict]:
    return [json.loads(l) for l in path.read_text().splitlines() if l.strip()] if path.exists() else []


def queries(out: Path, need: str, n: int) -> None:
    got = as_json(say(Reader(model=SUPER), QUERIES.format(today=date.today().isoformat(), n=n, need=need)), "[") or []
    (out / "queries.json").write_text(json.dumps(got, indent=1, ensure_ascii=False))
    print(f"queries: {len(got)}")


def search(out: Path, fetch: int, engine: str) -> None:
    pages = {}
    for q in json.loads((out / "queries.json").read_text()):
        run = subprocess.run(["ait-search", "--engine", engine, "search", q, "--limit", "20", "--fetch", str(fetch),
                              "--tag", "pick12"], capture_output=True, text=True, timeout=600)
        try:
            found = json.loads(run.stdout)
        except ValueError:
            print(f"  failed: {q!r}: {run.stderr[:200]}")
            continue
        for r in found.get("results", []):
            # Only what this engine fetched: a body the store kept from another one is not used.
            body = next((b for b in r.get("bodies") or [] if b.get("path") and b.get("source") == engine), None)
            if body and r["url"] not in pages:
                pages[r["url"]] = {"id": r["id"], "url": r["url"], "title": r["title"],
                                   "published": r.get("published"), "query": q, "path": body["path"]}
        print(f"  {len(pages):4d} pages after {q!r}")
    (out / "pages.jsonl").write_text("".join(json.dumps(p, ensure_ascii=False) + "\n" for p in pages.values()))


def body(page: dict, limit: int = 14000) -> str:
    return Path(page["path"]).read_text(errors="replace")[:limit]


def pages(out: Path, need: str) -> None:
    reader = Reader()
    rows = jsonl(out / "pages.jsonl")

    def judge(page):
        try:
            return reader.noul(body(page, 6000), PAGE.format(need=need), true="yes, it names models with a "
                               "price or a specification", false="no, it names none")["p"]["yes"]
        except Exception as e:  # noqa: BLE001 - a page that can't be read is a page without products
            print(f"  {page['url']}: {e}")
            return 0.0
    with concurrent.futures.ThreadPoolExecutor(8) as pool:
        for page, p in zip(rows, pool.map(judge, rows)):
            page["p_products"] = round(p, 3)
    (out / "pages.jsonl").write_text("".join(json.dumps(p, ensure_ascii=False) + "\n" for p in rows))
    print(f"pages: {sum(p['p_products'] >= 0.5 for p in rows)} of {len(rows)} name products")


def read(reader: Reader, need: str, page: dict) -> list[dict]:
    """Every product a page names, with its fields and the sentence that says so."""
    try:
        got = as_json(say(reader, EXTRACT.format(need=need, url=page["url"], body=body(page)), 12000), "[")
    except Exception as e:  # noqa: BLE001 - a page that can't be read names nothing
        print(f"  {page['url']}: {e}")
        return []
    text = said_words(body(page))
    found = []
    for p in got or []:
        if not isinstance(p, dict) or not p.get("model"):
            continue
        # A field stands only on words the page has. Told to leave a field null when the page
        # doesn't say it, the model still wrote needs_cloud=false for pages silent on the cloud;
        # a quote copied from the page is checked here, by code, and a field without one is unknown.
        quotes = p.get("quotes") if isinstance(p.get("quotes"), dict) else {}
        for f in ("price_eur", *FIELDS):
            if p.get(f) is not None and not (said_words(str(quotes.get(f) or "")) and
                                             said_words(str(quotes.get(f))) in text):
                p[f] = None
        # "clears 4.5 cm thresholds" came back as threshold_mm 4.5: the quote carries the unit.
        said = str(quotes.get("threshold_mm") or "").lower()
        if isinstance(p.get("threshold_mm"), (int, float)) and p["threshold_mm"] < 15 and \
                re.search(r"\d\s*cm\b|centimet", said):
            p["threshold_mm"] = p["threshold_mm"] * 10
        found.append({**p, "url": page["url"], "published": page.get("published")})
    return found


def said_words(text: str) -> str:
    return " ".join(re.sub(r"[^\w.,%€]+", " ", text.lower()).split())


def extract(out: Path, need: str) -> None:
    reader = Reader(model=SUPER, timeout=300)
    rows = [p for p in jsonl(out / "pages.jsonl") if p.get("p_products", 0) >= 0.5]
    found = []
    with concurrent.futures.ThreadPoolExecutor(8) as pool:
        for got in pool.map(lambda page: read(reader, need, page), rows):
            found += got
    (out / "offers.jsonl").write_text("".join(json.dumps(p, ensure_ascii=False) + "\n" for p in found))
    print(f"extract: {len(found)} mentions from {len(rows)} pages")


# Each field as the claim it amounts to, for the decision model to read against its quote.
CLAIMS = {
    "price_eur": lambda m, v: f"{m} costs about {v} euros",
    "noise_db": lambda m, v: f"{m} makes about {v} dB of noise",
    "threshold_mm": lambda m, v: f"{m} climbs thresholds or obstacles of about {v / 10:g} cm ({v:g} mm)",
    "suction_pa": lambda m, v: f"{m} has about {v} Pa of suction",
    "hepa": lambda m, v: f"{m} {'has' if v else 'has no'} HEPA filter",
    "pet_hair": lambda m, v: f"{m} handles pet hair {'well' if v else 'poorly'}",
    "carpet": lambda m, v: f"{m} cleans carpets {'well' if v else 'poorly'}",
    "needs_cloud": lambda m, v: (f"{m} needs a cloud account or an app to work" if v else
                                 f"{m} works without a cloud account or an app"),
    "mop": lambda m, v: f"{m} {'can' if v else 'cannot'} mop",
}


def verify(reader: Reader, offers: list[dict]) -> list[dict]:
    """Keep a field only where its quote says it. Measured 2026-10-26: quotes copied exactly from
    the page still claimed what they don't say — "LiDAR Navigation" for works-without-a-cloud,
    "the app walked me through connecting to WiFi" for the same."""
    for o in offers:
        for f in CLAIMS:
            # A number stands on a quote with a number in it: "quiet even on high suction" is no 51 dB.
            if isinstance(o.get(f), (int, float)) and not isinstance(o[f], bool) and \
                    not re.search(r"\d", str((o.get("quotes") or {}).get(f) or "")):
                o[f] = None
    asks = [(o, f) for o in offers for f in CLAIMS if o.get(f) is not None]

    def one(item):
        o, f = item
        quote = str((o.get("quotes") or {}).get(f) or "")
        model = f"{o.get('brand') or ''} {o.get('model')}".strip()
        try:
            return reader.noul(f"Words from a page about {model}:\n\"{quote}\"",
                               f"Do these words say that {CLAIMS[f](model, o[f])}?",
                               true="yes, the words say it", false="no, the words don't say it")["p"]["yes"]
        except Exception:  # noqa: BLE001 - a claim that can't be checked is not kept
            return 0.0
    with concurrent.futures.ThreadPoolExecutor(16) as pool:
        for (o, f), p in zip(asks, pool.map(one, asks)):
            o.setdefault("checked", {})[f] = round(p, 3)
            if p < 0.5:
                o[f] = None
    return offers


def verify_stage(out: Path) -> None:
    offers = jsonl(out / "offers.jsonl")
    verify(Reader(), offers)
    checked = [p for o in offers for p in (o.get("checked") or {}).values()]
    (out / "offers.jsonl").write_text("".join(json.dumps(o, ensure_ascii=False) + "\n" for o in offers))
    print(f"verify: {sum(p >= 0.5 for p in checked)} of {len(checked)} fields said by their words")


def key(offer: dict) -> str:
    """Brand and model as one word: 'Roborock Q7 Max+' and 'roborock q7max+' are one product."""
    brand = (offer.get("brand") or "").lower()
    model = (offer.get("model") or "").lower().replace(brand, "")
    return re.sub(r"[^a-z0-9+]", "", brand + model)


FIELDS = ("noise_db", "threshold_mm", "suction_pa", "hepa", "pet_hair", "carpet", "needs_cloud", "mop")


def fold(offers: list[dict]) -> list[dict]:
    """One row per product; offers from many pages fold into intervals, the most named first."""
    rows = {}
    for o in offers:
        k = key(o)
        if not k:
            continue
        row = rows.setdefault(k, {"key": k, "brand": o.get("brand"), "model": o.get("model"),
                                  "prices": [], "fields": {}, "texts": []})
        price = o.get("price_eur")
        if isinstance(price, (int, float)) and 30 <= price <= 5000:
            row["prices"].append(price)
        for f in FIELDS:
            if o.get(f) is not None:
                row["fields"].setdefault(f, []).append(o[f])
        row["texts"].append({"text": o.get("text"), "url": o["url"], "published": o.get("published")})
    for row in rows.values():
        p = sorted(row.pop("prices"))
        # An accessory or a bundle priced on the same page is not the product's price.
        mid = p[len(p) // 2] if p else 0
        p = [x for x in p if mid / 2 <= x <= mid * 2]
        row["price_eur"] = [min(p), max(p)] if p else None
        for f, seen in row.pop("fields").items():
            # Numbers keep their range; yes/no keeps the majority, a tie is unknown.
            if isinstance(seen[0], bool):
                yes = sum(1 for s in seen if s is True)
                row[f] = True if yes * 2 > len(seen) else False if yes * 2 < len(seen) else None
            else:
                nums = [s for s in seen if isinstance(s, (int, float))]
                row[f] = [min(nums), max(nums)] if nums else None
        row["sources"] = len({t["url"] for t in row["texts"]})
    return sorted(rows.values(), key=lambda r: -r["sources"])


def catalog(out: Path) -> None:
    ranked = fold(jsonl(out / "offers.jsonl"))
    (out / "catalog.jsonl").write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in ranked))
    filled = {f: sum(1 for r in ranked if r.get(f) is not None)
              for f in ("price_eur", "noise_db", "threshold_mm", "suction_pa", "hepa", "needs_cloud")}
    print(f"catalog: {len(ranked)} products; with a field: {filled}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("out", type=Path)
    parser.add_argument("--need", default="robot vacuum cleaners")
    parser.add_argument("--queries", type=int, default=30)
    parser.add_argument("--fetch", type=int, default=10, help="pages fetched per query")
    parser.add_argument("--engine", default="tavily", help="the submission's is tavily; keenable for tests")
    parser.add_argument("--from", dest="start", choices=STAGES, default="queries")
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    for stage in STAGES[STAGES.index(args.start):]:
        {"queries": lambda: queries(args.out, args.need, args.queries),
         "search": lambda: search(args.out, args.fetch, args.engine),
         "pages": lambda: pages(args.out, args.need),
         "extract": lambda: extract(args.out, args.need),
         "verify": lambda: verify_stage(args.out),
         "catalog": lambda: catalog(args.out)}[stage]()


if __name__ == "__main__":
    main()
