"""Topics kept fresh from the web: a topic the user comes back to whose outside changes — prices,
offers, events, schedules, what is on sale — is searched again when it was not searched for a while.

The message is answered at once, from what the memory holds. When it goes on with a topic (the
graph's recall decides that), the decision model is asked, of the message with its topic, whether
what is current outside would help — places, events, prices, what changes within weeks. If it does and it was not searched in `STALE`, the answer says the memory is looking
on the web, and a search runs in the background: the reader writes the queries — kinds of things,
the place, the date, never a name or a detail of the user's — Tavily finds the pages, and the
reader says what on them bears on the topic, each fact with its address. When it is done, the
agent is told with the memory's next answer: what was found, or that nothing new was.

Every search is kept (`graph/web.jsonl`: queries, sources, what was found). What matters — a
second, one-token question — becomes a memory: a layer of the topic, "From the web, <day>: …" with
its addresses, read with the topic like any other layer. Never the journal: the web is a second
narrator, not the user.
"""
import json
import logging
import threading
from datetime import datetime, timedelta
from pathlib import Path

from memory import trace
from memory.models import role

log = logging.getLogger("memory.refresh")

# Searched again after this long: a price or an event list a week old may no longer hold.
STALE = timedelta(days=7)
# Asked of the message with its topic, every time: whether the web has something current to add.
VOLATILE = ("Would what is current outside help with this — places, events, concerts, prices, offers, "
            "what is on sale or available, opening hours, news — things that change within weeks? Not "
            "the user's own plans, calendar, memories or people.",
            "yes, what is current outside would help", "no, it is the user's own matter")
QUERIES = """A topic the user keeps coming back to: "{name}".
Where it stands: {text}
The user now says: "{message}"
Today is {today}.

Write up to {n} web search queries that would find what is current for this now: places, events, \
offers, prices, dates. Each query names the city or country the user is in or speaks of, the kind \
of thing and the month — never a person's name, a health detail or anything private of the user's.
Answer as JSON: {{"queries": ["...", "..."]}}"""
FOUND = """A topic the user keeps coming back to: "{name}".
Where it stands: {text}
The user now says: "{message}"
Today is {today}.

Pages found on the web:
{pages}

Say what on these pages bears on it now: up to {n} short facts, each with the address of the page \
it is on, in the form "- fact (address)". Only what is in the place the user is in or speaks of, \
and fits what they want; a page about another city, or a general list, does not bear on it. Only \
what the pages say; dates and prices as given. If nothing bears on it, answer "nothing"."""
# Kept as a memory only when it is worth one: something the user would want to know, not a page
# that merely mentions the matter.
WORTH = ("Did the search find something that matters for this now — specific and current, in the "
         "place the user is in or speaks of: an event with its date, a place, a price or an offer — "
         "that the user would want to know? Not pages about another place, general lists or tips.",
         "yes, something that matters", "no, nothing that matters")


class Refresher:
    def __init__(self, where: Path, search=None, write=None, volatile=None, worth=None, keep=None, now=datetime.now):
        self.path = where / "web.jsonl"
        if search is None:
            from memory.tools import tavily
            search = tavily
        self.search = search
        self.write = write or (lambda prompt: role("reader").say("Answer as asked.", prompt, room=3000, thinking=False))
        self.volatile = volatile or (lambda t, message: role("judge").noul(
            f'A topic the user keeps coming back to, "{t["name"]}": {t["text"][-600:]}\n\nThe user now says: "{message}"',
            *VOLATILE)["p"]["yes"])
        self.worth = worth or (lambda t, found: role("judge").noul(
            f'A topic the user keeps coming back to, "{t["name"]}": {t["text"][-600:]}\n\nThe user now says: '
            f'"{t.get("message", "")}"\n\nFound on the web:\n{found}',
            *WORTH)["p"]["yes"])
        # Where a finding that matters becomes a memory: a layer of the topic (Graph.add_to_topic).
        self.keep = keep
        # How the agent hears of it, with the memory's next answer (Listener.note).
        self.tell = None
        self.now = now
        self.lock = threading.Lock()
        self.running: set = set()
        self.found = {}
        for line in (self.path.read_text().splitlines() if self.path.exists() else []):
            if line.strip():
                row = json.loads(line)
                self.found[row["topic"]] = row

    def touched(self, topics: list[dict], message: str = "") -> list[str]:
        """The topics a message goes on with: each stale one that changes is searched, in the
        background. Returns the names of those being searched now."""
        started = []
        for t in topics:
            key = str(t["topic"])
            with self.lock:
                if key in self.running:
                    continue
                last = self.found.get(key)
                if last and self.now() - datetime.fromisoformat(last["day"]) < STALE:
                    continue
            try:
                p = round(float(self.volatile(t, message)), 2)
                trace.step("web_worth", topic=t["name"], message=message, p=p)
                if p < 0.5:
                    continue
            except Exception:  # noqa: BLE001 - not known to change: not searched
                log.exception("asking whether a topic changes failed")
                continue
            with self.lock:
                if key in self.running:
                    continue
                self.running.add(key)
            started.append(t["name"])
            threading.Thread(target=self._refresh, args=({**t, "message": message},), daemon=True).start()
        return started

    def _refresh(self, t: dict) -> None:
        key = str(t["topic"])
        try:
            today, text = self.now().strftime("%Y-%m-%d"), t["text"][-1200:]
            said = self.write(QUERIES.format(name=t["name"], text=text, message=t.get("message", ""), today=today, n=2))
            try:
                queries = json.loads(said[said.find("{"):said.rfind("}") + 1])["queries"][:2]
            except (ValueError, KeyError, TypeError):
                queries = []
            pages = [p for q in queries for p in self.search(q, 4)]
            shown = "\n\n".join(f"[{p['url']}] {p.get('title') or ''}\n{(p.get('text') or '')[:1500]}" for p in pages[:8])
            found = self.write(FOUND.format(name=t["name"], text=text, message=t.get("message", ""), today=today,
                                            pages=shown or "none", n=6)).strip() \
                if pages else "nothing"
            matters = found.lower().strip(".") != "nothing" and float(self.worth(t, found)) >= 0.5
            row = {"topic": key, "name": t["name"], "day": self.now().isoformat(timespec="seconds"),
                   "queries": queries, "sources": [p["url"] for p in pages], "text": found, "kept": matters}
            with self.lock:
                self.found[key] = row
                with self.path.open("a") as f:
                    f.write(json.dumps(row, ensure_ascii=False) + "\n")
            if matters and self.keep:
                self.keep(t["topic"], f'From the web, {today}: {" ".join(found.split())}', row["day"])
            if self.tell:
                self.tell(f'Looked on the web for what is new on "{t["name"]}" ({today}). Found what matters, '
                          f'now kept with the topic — give it to the user if it still bears on what they want:\n{found}'
                          if matters else f'Looked on the web for what is new on "{t["name"]}" ({today}): nothing '
                          f'new that matters. Tell the user, if you said you would look.')
            trace.step("web", topic=t["name"], queries=queries, sources=row["sources"][:8], found=found, kept=matters)
        except Exception:  # noqa: BLE001 - a search that failed leaves the topic as it was
            log.exception("refreshing a topic from the web failed")
            if self.tell:
                self.tell(f'Looking on the web for "{t["name"]}" failed; nothing was found.')
        finally:
            with self.lock:
                self.running.discard(key)
