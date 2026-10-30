"""Topics kept current from the web: a sweep, in the quiet, over every topic not looked up lately.

The object is the topic, not a question. A topic is fresh for `FRESH` from its latest web entry in
the journal, or from a sweep that found nothing on it or found that its outside does not change;
one the user has not spoken of in `DORMANT` is left as it is; any other topic is due, whether or
not the user speaks of it now. The server's timer (`memory/jobs.py`) offers a sweep every minute. At most once in `EVERY` (the
time of the last sweep is kept beside the graph, so a restart does not shorten it), a sweep takes
up to `TOPICS` due topics, one at a time:

1. a one-token question: would what is current outside help here (places, events, prices — what
   changes within weeks)? Not: the topic counts as checked, and is not asked again for a month —
   the user's own matters (an allergy, a grumble about work) never reach the web;
2. queries from the user's questions on the topic (their interests, asked in its entries), or from
   the topic itself when it has none: the place, the venues it names, the kind of thing, the dates —
   never a person's name or a private detail;
3. Tavily finds pages; the reader says what on them answers it, each fact with its address;
4. a second one-token question: does it matter? If so, it is kept in the journal as the web's entry
   for that topic (`journal.keep_web`) and read into the topic like the user's entries are — never
   as the user's words. If not, the topic is checked, with no entry.

The agent hears of it with the memory's next answer to a message of the user's (`Listener.note`):
what was found, or that nothing new was.
"""
import json
import logging
import os
import threading
from datetime import datetime, timedelta
from pathlib import Path

from memory import trace
from memory.models import role

log = logging.getLogger("memory.refresh")

# A topic is looked up on the web again after this long: prices and event lists change within
# weeks, and one search per topic a month bounds what the shared demo spends (2026-10-30).
FRESH = timedelta(days=30)
# A topic the user has not spoken of for this long is no longer theirs to keep current. Only their
# own entries count: the web's would keep a topic alive by themselves.
DORMANT = timedelta(days=90)
# A sweep at most this often, from the end of the last one; at most this many topics in it.
EVERY = float(os.environ.get("TERRAWEAVER_WEB_EVERY", "3600"))
TOPICS = int(os.environ.get("TERRAWEAVER_WEB_TOPICS", "3"))
# At most this many of a topic's questions make its queries, the most recent first: each costs a search.
QUESTIONS = 3
# Searched only when the outside surely changes: a work grumble ("why does the earlier standup annoy
# me") read 0.55, concerts 0.89–0.96 (2026-10-30).
CHANGES = 0.7
VOLATILE = ("Would what is current outside help with this — places, events, concerts, prices, offers, "
            "what is on sale or available, opening hours, news — things that change within weeks? Not "
            "the user's own plans, calendar, memories or people.",
            "yes, what is current outside would help", "no, it is the user's own matter")
QUERIES = """A topic the user keeps coming back to: "{name}".
Where it stands: {text}
{question}
Today is {today}.

Write up to {n} web search queries that would find what is current for this now: places, events, \
offers, prices, dates. Each query names the city or country the user is in or speaks of, the kind \
of thing, and the date or month the user speaks of (else this one) — a day named without its month \
is the next one to come: "the 14th", said on the 30th, is next month's; a venue or place the topic \
names may be a query of its own — never a person's name, a health detail or anything private of \
the user's.
Answer as JSON: {{"queries": ["...", "..."]}}"""
FOUND = """A topic the user keeps coming back to: "{name}".
Where it stands: {text}
What the user wants on it: {questions}
Today is {today}.

Pages found on the web:
{pages}

Say what on these pages answers it now: up to {n} short facts, each with the address of the page it \
is on, in the form "- fact (address)". Only what is in the place the user is in or speaks of, and \
fits what they want; a page about another city, or a general list, does not bear on it. Only what \
the pages say; dates and prices as given. If nothing does, answer "nothing"."""
# Kept only when it is worth it: something the user would want to know, not a page that merely
# mentions the matter.
WORTH = ("Did the search find something that matters for this now — specific and current, in the "
         "place the user is in or speaks of: an event with its date, a place, a price or an offer — "
         "that the user would want to know? Not pages about another place, general lists or tips.",
         "yes, something that matters", "no, nothing that matters")


class Refresher:
    """`questions_of(topic)` and `extended(question, topic, day, entry)` are the listener's: the
    user's questions live with their interests, and each is marked with the sweeps made for it —
    for the record, not for freshness. `last_web(topic)` is the day of the topic's latest web entry;
    `last_said(entries)` the day the user last spoke in a topic's entries;
    `keep_web(text, topic, when)` keeps one and returns its number. `where` holds the topics checked
    with nothing kept, and the time of the last sweep."""

    def __init__(self, keep_web, questions_of=None, extended=None, last_web=None, last_said=None, where: Path | None = None,
                 search=None, write=None, volatile=None, worth=None, now=datetime.now):
        if search is None:
            from memory.web import tavily
            search = tavily
        self.keep_web, self.search, self.now = keep_web, search, now
        self.questions_of = questions_of or (lambda topic: [])
        self.extended = extended or (lambda *a: None)
        self.last_web = last_web or (lambda topic: None)
        self.last_said = last_said or (lambda entries: None)
        self.where, self.checked, self.swept = where, {}, None
        if where and (where / "web_checks.jsonl").exists():
            for line in (where / "web_checks.jsonl").read_text().splitlines():
                if line.strip():
                    c = json.loads(line)
                    self.checked[c["topic"]] = max(self.checked.get(c["topic"], c["on"]), c["on"])
        if where and (where / "web_sweep.json").exists():
            self.swept = datetime.fromisoformat(json.loads((where / "web_sweep.json").read_text())["at"])
        self.write = write or (lambda prompt: role("reader").say("Answer as asked.", prompt, room=3000, thinking=False))
        self.volatile = volatile or (lambda t, questions: role("judge").noul(
            f'A topic the user keeps coming back to, "{t["name"]}": {t["text"][-600:]}\n\nWhat the user wants '
            f'on it: {questions or "(nothing asked)"}', *VOLATILE)["p"]["yes"])
        self.worth = worth or (lambda t, questions, found: role("judge").noul(
            f'A topic the user keeps coming back to, "{t["name"]}": {t["text"][-600:]}\n\nWhat the user wants '
            f'on it: {questions}\n\nFound on the web:\n{found}', *WORTH)["p"]["yes"])
        # How the agent hears of it, with the memory's next answer (Listener.note).
        self.tell = None
        self.lock = threading.Lock()

    def fresh(self, topic: dict, now: datetime | None = None) -> bool:
        """Looked up on the web within FRESH: the topic, not a question, is what is kept current."""
        seen = [d for d in (self.last_web(topic["topic"]), self.checked.get(topic["topic"])) if d]
        return bool(seen) and (now or self.now()) - max(datetime.fromisoformat(str(d)) for d in seen) < FRESH

    def due(self, topic: dict, now: datetime | None = None) -> bool:
        """Not fresh, and spoken of by the user within DORMANT."""
        now = now or self.now()
        said = self.last_said(topic.get("entries", []))
        return bool(said) and now - datetime.fromisoformat(said) < DORMANT and not self.fresh(topic, now)

    def sweep(self, topics: list[dict]) -> list[str]:
        """Up to TOPICS due topics, one at a time, if the last sweep is EVERY behind. A sweep with
        nothing due is not counted: the first topic read is looked up at once. Returns the names
        of the topics searched."""
        now = self.now()
        if self.swept and (now - self.swept).total_seconds() < EVERY:
            return []
        due = [t for t in topics if self.due(t, now)][:TOPICS]
        if not due:
            return []
        with self.lock:
            done = [t["name"] for t in due if self._refresh(t)]
            self.swept = self.now()
            if self.where:
                (self.where / "web_sweep.json").write_text(json.dumps({"at": self.swept.isoformat(timespec="seconds")}))
        return done

    def _checked(self, topic: int, when: datetime) -> None:
        on = when.isoformat(timespec="seconds")
        self.checked[topic] = on
        if self.where:
            with (self.where / "web_checks.jsonl").open("a") as f:
                f.write(json.dumps({"topic": topic, "on": on}) + "\n")

    def _refresh(self, t: dict) -> bool:
        """One topic: asked whether its outside changes, then searched. True if it was searched."""
        key, when = t["topic"], self.now()
        questions = sorted(self.questions_of(t), key=lambda q: -q["id"])[:QUESTIONS]
        asked = "; ".join(f'"{q["asked"]}"' for q in questions)
        try:
            p = round(float(self.volatile(t, asked)), 2)
        except Exception:  # noqa: BLE001 - not known to change: not searched, asked again next sweep
            log.exception("asking whether a topic changes failed")
            return False
        trace.step("web_worth", topic=t["name"], p=p, questions=[q["asked"] for q in questions])
        if p < CHANGES:
            # The user's own matter: checked, and not asked again for a month.
            self._checked(key, when)
            return False
        today, text = f"{when:%Y-%m-%d}", t["text"][-1200:]
        try:
            queries = []
            for q in questions or [None]:
                said = self.write(QUERIES.format(name=t["name"], text=text, today=today, n=2,
                                                 question=f'The user asked: "{q["asked"]}"' if q else ""))
                try:
                    got = json.loads(said[said.find("{"):said.rfind("}") + 1])["queries"][:2]
                    # "jazz clubs [City Name]": no place known, and the web answers for America.
                    queries += [x for x in got if "[" not in x]
                except (ValueError, KeyError, TypeError):
                    log.warning("no queries for %r: %r", t["name"], said[:200])
            pages = [p for query in dict.fromkeys(queries) for p in self.search(query, 4)]
            shown = "\n\n".join(f"[{p['url']}] {p.get('title') or ''}\n{(p.get('text') or '')[:1500]}" for p in pages[:10])
            wants = asked or f'what is current on "{t["name"]}"'
            found = self.write(FOUND.format(name=t["name"], text=text, questions=wants, today=today,
                                            pages=shown, n=6)).strip() if pages else "nothing"
            matters = found.lower().strip(".") != "nothing" and float(self.worth(t, wants, found)) >= 0.5
            entry = self.keep_web(f'On "{t["name"]}", for {wants}, the web says, on {today}:\n{found}', key, when) \
                if matters else None
            for q in questions:
                self.extended(q["id"], key, when.isoformat(timespec="seconds"), entry)
            if entry is None:
                self._checked(key, when)
            trace.step("web", topic=t["name"], questions=[q["asked"] for q in questions], queries=queries,
                       sources=[p["url"] for p in pages][:10], found=found, entry=entry)
            if self.tell:
                self.tell(f'Looked on the web on "{t["name"]}" ({today}) for {wants}. Found what matters, kept as '
                          f'entry #{entry} — give it to the user if it still bears on what they want:\n{found}'
                          if matters else f'Looked on the web on "{t["name"]}" ({today}): nothing new that matters.')
        except Exception:  # noqa: BLE001 - a search that failed leaves the topic as it was
            log.exception("looking up a topic on the web failed")
            self._checked(key, when)
        return True
