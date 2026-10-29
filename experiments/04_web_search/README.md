# 04 — Web search: what the world can take from it

Started 2026-10-05 by the user.

## The question

A personal assistant's user cares about events, news, articles, places, things to buy. Can the
chain **search → fetch → page into items → `formalise` → check against the page** turn the web into
sourced candidates the world can hold, for the scenarios in `docs/archive/ideas-research.md` ("Scenarios,
2026-10-05")? And what object model do those candidates end up in?

What counts as an answer, per scenario:

- **Grounding a mention** (scenario 2): from a sentence the user said, the public thing it
  names, with every attribute present on the page it came from, or an honest "not found".
- **Pick it for me** (scenario 1): from a request and what the world knows, a set of
  candidates in a research world, each attribute checked against its page, filterable by the
  host's code.
- **Watching** (scenario 3): a repeated search that reports what is new since the last one, and
  nothing that is not.

## What it runs against

Search goes through `ait-search` (`~/Projects/agent-tools/search-cli`), with Tavily as the engine,
not through raw API calls: it remembers every page it returned, marks new ones on a repeated
search, and keeps the fetched bodies. Without `TAVILY_API_KEY` Tavily runs in keyless mode
(search and fetch only, free, rate-limited); the same code runs with a key. Its store for this
experiment is `var/web_search_store` — pages are not committed.

The world side, from stage C on, is the base world (`ontology.base_specs` +
`WorldRuntime(fixture=None)`), driven through the doors a host goes through.

## Stages

    A  probe     What comes back per scenario kind: listing or item page, how many results carry a
                 date, wrong places, fetch failures, the score below which results are noise.
                 No world, no model. probe.py; queries in queries.py.
    B  items     A listing page (artrabbit, jazznearyou) into its items: name, dates, venue,
                 the item's own link. The piece under test; which reader does it (Nemotron,
                 schema.org markup where a page has it, the page's own structure) is part of
                 the question.
    C  formalise Items into a research world of their own through `formalise`, the page as the
                 source, `check.py` verifying each attribute against it.
    D  grounding A sentence with a mention → query → candidates → `world.identify` over them.

## The object model — the same task as the dialogue, from another narrator

Settled with the user, 2026-10-05: this is the world's main task again — build the object model
of the world — with a web page in the place of the person talking. The page is the storyteller,
the world formalises; `formalise`, the engineer, the picker and the walk down the class tree are
the same machinery. Nothing is hand-written for it: a public event grows as a subclass of `Event`
(and a concert or an exhibition further down) the way any class grows from a conversation.
`Event` in the base is a happening in the person's life (`name`, `about`, `start_time`,
`end_time`); what a listing adds — venue, price, ticket link, performers, an exhibition's end —
is for the world to grow.

What differs from the dialogue, and what the experiment has to live through:

- **The source can be checked.** In a dialogue the person has the last word; here the page has,
  and every attribute is verified against it (`check.py`).
- **There is nobody to ask.** A closed question that goes to the person in a dialogue is closed
  by the page here, or stays open.
- **Many objects at once.** One listing is dozens of events, not one remark.
- **Identity across sources.** One concert on songkick and on jazznearyou is the `identify`
  problem with candidates from different pages.
- **Freshness.** A web fact has a retrieval date and a shelf life; what a person said has neither.

If the same machinery builds a sound model from web text, that is evidence it is general and
not fitted to dialogue — which is also the claim the write-up wants to make.

Still open: whether the engineer consults schema.org (`Event`, `MusicEvent`, `ExhibitionEvent`,
`NewsArticle`, `Place`, `Offer`) as an accepted norm when it grows these classes — a reference
with its source recorded, not starting classes. Some pages carry that vocabulary as JSON-LD
(the-berliner: `Article` with `datePublished`).

## Known so far (from the session that started this, before probe.py)

- For events, search returns listing pages, not event pages; listings parse well in Tavily's
  markdown (artrabbit: title, "03 Oct 2026 – 31 Oct 2026", venue, link per item).
- Dates: news 8/8, articles 5–7/8, events 2–3/8.
- Wrong places: "Belgrade" → Belgrade, Montana; "Berlin" hiking → Berlin, Connecticut.
- Tavily extract failed on eventbrite and belgrade-beat; a plain GET of jazznearyou and artrabbit
  event pages returned a stub, so whether they carry JSON-LD is unknown.
- `ait-search` gaps: no `topic=news`, search depth fixed at `basic`.

## Files

    queries.py   the queries, by scenario kind, with the place each is about
    probe.py     stage A: runs the queries through ait-search, writes results/probe-<date>.json
                 and prints a table per query
