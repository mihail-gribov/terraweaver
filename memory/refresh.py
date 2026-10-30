"""A topic extended from the web: new facts found for the user's own questions on it.

The message is answered at once, from what the memory holds. When it goes on with a topic (the
graph's recall decides that), the user's questions on that topic are taken — those kept as their
interests and asked in the topic's entries, and the message's own — and each not extended for this
topic in `STALE` is due. If any is, the decision model is asked whether what is current outside
would help (places, events, prices, what changes within weeks); if so, the answer says the memory
is looking on the web, and in the background each due question becomes queries (the place and the
kind of thing, never a name or a private detail), Tavily finds pages, and the reader says what on
them answers it, each fact with its address.

What was found is one reply of the web's: if a second one-token question says it matters, it is
kept in the journal as the web's entry for that topic (`journal.keep_web`) and read into the topic
like the user's entries are — never as the user's words. Each question is marked with when it was
extended for the topic and what it gave, and the agent is told with the memory's next answer:
what was found, or that nothing new was.
"""
import json
import logging
import threading
from datetime import datetime, timedelta

from memory import trace
from memory.models import role

log = logging.getLogger("memory.refresh")

# A question is extended for a topic again after this long: a price or an event list a week old
# may no longer hold.
STALE = timedelta(days=7)
# At most this many questions per extension, the most recent first: each costs a search.
QUESTIONS = 3
VOLATILE = ("Would what is current outside help with this — places, events, concerts, prices, offers, "
            "what is on sale or available, opening hours, news — things that change within weeks? Not "
            "the user's own plans, calendar, memories or people.",
            "yes, what is current outside would help", "no, it is the user's own matter")
QUERIES = """A topic the user keeps coming back to: "{name}".
Where it stands: {text}
The user asked: "{question}"
Today is {today}.

Write up to {n} web search queries that would find what is current for this question now: places, \
events, offers, prices, dates. Each query names the city or country the user is in or speaks of, \
the kind of thing, and the month the user speaks of (else this one) — never a person's name, a \
health detail or anything private of the user's.
Answer as JSON: {{"queries": ["...", "..."]}}"""
FOUND = """A topic the user keeps coming back to: "{name}".
Where it stands: {text}
The user's questions on it: {questions}
Today is {today}.

Pages found on the web:
{pages}

Say what on these pages answers the questions now: up to {n} short facts, each with the address of \
the page it is on, in the form "- fact (address)". Only what is in the place the user is in or \
speaks of, and fits what they want; a page about another city, or a general list, does not bear on \
it. Only what the pages say; dates and prices as given. If nothing does, answer "nothing"."""
# Kept only when it is worth it: something the user would want to know, not a page that merely
# mentions the matter.
WORTH = ("Did the search find something that matters for this now — specific and current, in the "
         "place the user is in or speaks of: an event with its date, a place, a price or an offer — "
         "that the user would want to know? Not pages about another place, general lists or tips.",
         "yes, something that matters", "no, nothing that matters")


class Refresher:
    """`questions_of(topic)` and `extended(question, topic, day, entry)` are the listener's: the
    user's questions live with their interests. `keep_web(text, topic)` keeps the web's reply in
    the journal and returns its number."""

    def __init__(self, keep_web, questions_of=None, extended=None, search=None, write=None, volatile=None,
                 worth=None, now=datetime.now):
        if search is None:
            from memory.web import tavily
            search = tavily
        self.keep_web, self.search, self.now = keep_web, search, now
        self.questions_of = questions_of or (lambda topic: [])
        self.extended = extended or (lambda *a: None)
        self.write = write or (lambda prompt: role("reader").say("Answer as asked.", prompt, room=3000, thinking=False))
        self.volatile = volatile or (lambda t, message: role("judge").noul(
            f'A topic the user keeps coming back to, "{t["name"]}": {t["text"][-600:]}\n\nThe user now says: "{message}"',
            *VOLATILE)["p"]["yes"])
        self.worth = worth or (lambda t, questions, found: role("judge").noul(
            f'A topic the user keeps coming back to, "{t["name"]}": {t["text"][-600:]}\n\nThe user asked: '
            f'{questions}\n\nFound on the web:\n{found}', *WORTH)["p"]["yes"])
        # How the agent hears of it, with the memory's next answer (Listener.note).
        self.tell = None
        self.lock = threading.Lock()
        self.running: set = set()

    def due(self, topic: dict) -> list[dict]:
        """The user's questions on the topic not extended for it in STALE, the most recent first."""
        now = self.now()
        due = [q for q in self.questions_of(topic)
               if not q.get("extended") or now - datetime.fromisoformat(q["extended"]) >= STALE]
        return sorted(due, key=lambda q: -q["id"])[:QUESTIONS]

    def touched(self, topics: list[dict], message: str = "") -> list[str]:
        """The topics a message goes on with: each with questions due, whose outside changes, is
        extended in the background. Returns the names of those being extended now."""
        started = []
        for t in topics:
            key = t["topic"]
            due = self.due(t)
            if not due:
                continue
            with self.lock:
                if key in self.running:
                    continue
            try:
                p = round(float(self.volatile(t, message)), 2)
            except Exception:  # noqa: BLE001 - not known to change: not searched
                log.exception("asking whether a topic changes failed")
                continue
            trace.step("web_worth", topic=t["name"], message=message, p=p, questions=[q["asked"] for q in due])
            if p < 0.5:
                continue
            with self.lock:
                if key in self.running:
                    continue
                self.running.add(key)
            started.append(t["name"])
            threading.Thread(target=self._extend, args=(t, due), daemon=True).start()
        return started

    def _extend(self, t: dict, due: list[dict]) -> None:
        key = t["topic"]
        today, text = self.now().strftime("%Y-%m-%d"), t["text"][-1200:]
        try:
            queries = []
            for q in due:
                said = self.write(QUERIES.format(name=t["name"], text=text, question=q["asked"], today=today, n=2))
                try:
                    queries += json.loads(said[said.find("{"):said.rfind("}") + 1])["queries"][:2]
                except (ValueError, KeyError, TypeError):
                    log.warning("no queries for %r: %r", q["asked"], said[:200])
            pages = [p for query in dict.fromkeys(queries) for p in self.search(query, 4)]
            shown = "\n\n".join(f"[{p['url']}] {p.get('title') or ''}\n{(p.get('text') or '')[:1500]}" for p in pages[:10])
            asked = "; ".join(f'"{q["asked"]}"' for q in due)
            found = self.write(FOUND.format(name=t["name"], text=text, questions=asked, today=today,
                                            pages=shown, n=6)).strip() if pages else "nothing"
            matters = found.lower().strip(".") != "nothing" and float(self.worth(t, asked, found)) >= 0.5
            entry = self.keep_web(f'For the questions {asked}, the web says, on {today}:\n{found}', key) if matters else None
            day = self.now().isoformat(timespec="seconds")
            for q in due:
                self.extended(q["id"], key, day, entry)
            trace.step("web", topic=t["name"], questions=[q["asked"] for q in due], queries=queries,
                       sources=[p["url"] for p in pages][:10], found=found, entry=entry)
            if self.tell:
                self.tell(f'Looked on the web for {asked} ("{t["name"]}", {today}). Found what matters, kept as '
                          f'entry #{entry} — give it to the user if it still bears on what they want:\n{found}'
                          if matters else f'Looked on the web for {asked} ("{t["name"]}", {today}): nothing new '
                          f'that matters. Tell the user, if you said you would look.')
        except Exception:  # noqa: BLE001 - a search that failed leaves the topic as it was
            log.exception("extending a topic from the web failed")
            if self.tell:
                self.tell(f'Looking on the web for "{t["name"]}" failed; nothing was found.')
        finally:
            with self.lock:
                self.running.discard(key)
