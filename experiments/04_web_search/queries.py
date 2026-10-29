"""Stage A queries, by scenario kind.

Each query names only kinds of thing and public entities — the boundary in
docs/archive/ideas-research.md. `place` is the place the query is about, so a result
from another place with the same name can be counted.
"""

QUERIES = [
    # scenario 1 and 3: events, expected to come back as listing pages
    {"kind": "event", "place": "Berlin", "query": "jazz concerts Berlin 10 October 2026"},
    {"kind": "event", "place": "Berlin", "query": "art exhibitions opening Berlin October 2026"},
    {"kind": "event", "place": "Berlin", "query": "family events Berlin weekend children"},
    {"kind": "event", "place": "Belgrade", "query": "concerts Belgrade Serbia October 2026"},
    # scenario 2: a mention to ground, expected to find the one event
    {"kind": "mention", "place": "Berlin", "query": "Vortex Industriesalon Schöneweide concert"},
    # scenario 4: news and articles
    {"kind": "news", "place": "", "query": "Nvidia Nemotron", "since": "7d"},
    {"kind": "news", "place": "Berlin", "query": "Berlin public transport strike", "since": "30d"},
    {"kind": "article", "place": "", "query": "long-term memory for AI agents", "since": "30d"},
    {"kind": "article", "place": "Berlin", "query": "autumn hikes near Berlin"},
]
