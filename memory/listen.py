"""One door for the agent: `say(message)` — the user's message as written, and the memory answers.

The memory does with each message what a mind does with what it hears, and the agent decides
nothing about it:

- keeps what the message tells of the user's life, in the user's words (a secret never);
- puts beside it what it already holds that bears on it;
- keeps every question of the user's as their interest, and a repeat of it as one more time
  asked: not to be answered there and then — that is the agent's, through `ask` — but to say
  what the memory should get ready, from what it holds, for the next time it comes up
  (2026-10-28, the user);
- answers the agent's own `ask` always, waiting for it: the only door that gathers from the web
  (`memory/solve.py`), and the same gathering again while it is fresh;
- takes out what the user asks to be forgotten, but only once the user has confirmed which
  entries — a forget is never done on a guess;
- and gives, with any answer, what it has come to since the last one ("the memory remembered").

What a message holds is read by the intake (`memory/intake/intake.py`): the user's message with the
agent's message just before it, never more — personal or a request? the message rewritten to be
understood alone ("up to 400" after "what is the budget?"), and its questions, each of a kind. The
agent's message is what the user's is understood by, then dropped: never kept.

Reached two ways (docs/decisions.md, 2026-10-27): a hook that passes every message, where the
agent has hooks; or the agent itself, passing every message that touches the user's life.
"""
import asyncio
import logging
import re
import threading
from datetime import datetime

log = logging.getLogger("listen")
# An answer prepared this recently answers the same question again, instead of a new search:
# three days, as fresh as what a task chooses from (memory/tools.py FRESH).
FRESH_JOB = 3 * 24 * 3600
# Meaning finds the candidates, the judge says which is the same question. Measured on bge-small
# (2026-10-27): repeats sat at 0.64–0.85 ("who are my colleagues now?" ~ "who do I work with at
# Brightwork?" 0.64), while "weather in Belgrade on Saturday" ~ "... on Sunday" was 0.89 — so
# only a near-verbatim repeat is taken without the judge.
SAME_QUESTION, SAME_QUESTION_MAYBE = 0.97, 0.6

# What is never kept, whatever the message: keys, tokens, card numbers, passwords said as such.
SECRETS = re.compile(
    r"\b(sk-[A-Za-z0-9_-]{16,}|ghp_[A-Za-z0-9]{20,}|gh[ousr]_[A-Za-z0-9]{20,}|xox[abpr]-[A-Za-z0-9-]{10,}"
    r"|AKIA[0-9A-Z]{16}|eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}"
    r"|[A-Za-z0-9_\-]{32,}|(?:\d[ -]?){13,19})\b"
    r"|(?i:\b(?:password|passwd|pin|passcode)\b(?:\s*(?:is|:|=))+\s*\S+)")

QUESTIONS = {
    "find": ("Does the user ask for something to be found, looked up, compared or picked — a search "
             "that needs gathering from the web or adding up what was told — not just a reply?",
             "yes, they ask for a search or a pick", "no, no search is asked for"),
}
CONFIRM = ("Earlier the memory asked the user to confirm forgetting some entries. Does this message "
           "confirm it — go ahead and forget them?", "yes, go ahead", "no, or something else")


class Listener:
    """The state `say` keeps between messages: a forget waiting for its yes, and notes to give."""

    def __init__(self, base, keep, context, ask, solve, journal_changed, interests_path=None, embed=None,
                 heard_path=None):
        self.base, self._keep, self._context, self._ask, self._solve = base, keep, context, ask, solve
        self._changed = journal_changed
        self.waiting_forget: dict | None = None
        self.recent: list[dict] = []  # the last messages heard, both sides: what the gate reads with
        self.jobs: list[dict] = []    # the agent's gatherings, each with its answer once done
        self.wanted: list[dict] = []  # the user's questions: their interests, never looked into here
        self.interests_path, self._embed = interests_path, embed
        self.heard_path = heard_path  # every `say`: what was heard and what was answered
        self.notes: list[str] = []
        self._lock = threading.Lock()

    def note(self, text: str) -> None:
        """Something the memory came to on its own, given with the next answer."""
        with self._lock:
            self.notes.append(text)

    def take_notes(self) -> list[str]:
        with self._lock:
            out, self.notes = self.notes, []
        return out

    async def say(self, messages: list[dict], now: str | None = None, wait: bool = True, progress=None) -> str:
        """messages: [{"role": "user" | "agent" | "memory", "text": ...}], in the order they were
        said. The user's words are the user's; the agent's are what a reply of the user is understood
        by, never a fact alone; what the memory said itself is never taken back in. Nothing else is
        heard: what the agent read (mail, files, pages) reaches the memory when the user answers it."""
        parts = []
        remembered = self.take_notes()
        if remembered:
            parts.append("The memory remembered, since it last answered:\n" + "\n\n".join(remembered))
        for m in messages or []:
            role, text = str(m.get("role") or "user").lower(), (m.get("text") or "").strip()
            if not text or role == "memory":
                continue
            if role in ("agent", "assistant"):
                # Only to read the user's next words by ("up to 400" is the budget after "what
                # budget?"), then dropped: never kept, never stored beside the user's.
                self._heard_as("agent", text)
                continue
            if role != "user":
                continue
            parts += await self._heard(text, now, wait, progress)
        answer = _reply(parts)
        self._log_heard(messages, answer)
        return answer

    def _log_heard(self, messages: list[dict], answer: str) -> None:
        """What the memory heard and said back, for a look afterwards: a hook's answer is seen by the
        agent only, never by whoever reads the agent's own record. Secrets withheld here too."""
        if self.heard_path is None:
            return
        import json
        line = {"at": f"{datetime.now():%Y-%m-%d %H:%M:%S}",
                "heard": [{"role": m.get("role"), "text": SECRETS.sub("[withheld]", m.get("text") or "")} for m in messages or []],
                "answered": answer}
        with self._lock, self.heard_path.open("a") as file:
            file.write(json.dumps(line, ensure_ascii=False) + "\n")

    async def ask(self, question: str, wait: bool = True, progress=None, gather: bool = True,
                  now: str | None = None) -> str:
        """The agent's own question to the memory: answered from what it holds, or by gathering the
        facts when it asks for something to be found. Nothing is kept. `gather=False`: from what it
        holds only, never the web (a benchmark measures the memory, not the web)."""
        question = (question or "").strip()
        if not question:
            return "nothing"
        got = await self._sort(question, "", only=("find",), who="The agent asks") if gather else {"find": 0.0}
        if got["find"] >= 0.5:
            return await self._gather(question, wait, progress)
        found = await self._context(question, 10)
        answer = await (self._ask(question, now) if now else self._ask(question))
        return _reply([answer, "What it stands on:\n" + found if found and found.strip().lower().strip(".") != "nothing" else ""])

    async def _heard(self, message: str, now, wait: bool, progress) -> list[str]:
        """One message of the user's."""
        if self.waiting_forget:
            done = await self._confirm(message, now)
            if done:
                return [done]
        # A secret never leaves the machine, not even to be read.
        said = " ".join(SECRETS.sub("[withheld]", message).split())
        got = await asyncio.to_thread(self._read, said)
        self._heard_as("user", said)
        log.info("say: personal %.2f, requests %s", got.for_memory, [(r["kind"], r["text"]) for r in got.requests])
        forget = [r for r in got.requests if r["kind"] == "memory"]
        if forget:
            return [await self._prepare_forget(forget[0]["text"])]
        parts = []
        if got.for_memory >= 0.5:
            kept = self._remember(got.information[0] if got.information else said, said, now,
                                  withheld=said != " ".join(message.split()))
            if kept:
                parts.append(kept)
        # At once, beside each other: what bears on the message, the topic and people it goes on
        # with, and the answer to each question of the user's, from the memory only.
        recall, narrow = getattr(self.base, "graph_recall", None), getattr(self.base, "narrow", None)

        async def recalled() -> str:
            if recall is None:
                return ""
            # Only what the graph has read by now; never waited for.
            numbers = (await asyncio.to_thread(narrow, message))[:3] if narrow else []
            return await asyncio.to_thread(recall, message, numbers)

        async def answered(question: str) -> str:
            # The memory answers what it holds; it never searches from here — a search raced the
            # agent's own `ask` (2026-10-28). The web is the agent's to ask for.
            try:
                said = (await (self._ask(question, now) if now else self._ask(question))).strip()
            except Exception:  # noqa: BLE001 - no answer is the agent's to seek
                log.exception("answering the user's question failed")
                return ""
            if not said or "does not say" in said.lower() or said.lower().startswith("the memory is empty"):
                return ""
            return f'The user asks: "{question}". What the memory holds to answer it:\n{said}'

        asked = [r["text"] for r in got.requests if r["kind"] == "know"]
        found, topic, *answers = await asyncio.gather(self._context(message, 10), recalled(),
                                                      *(answered(q) for q in asked))
        gathered = ([f"What the memory holds that bears on this:\n{found}"]
                    if found and found.strip().lower().strip(".") != "nothing" else [])
        gathered += [topic] + list(answers)
        gathered = [g for g in gathered if g]
        if gathered:
            note = await self._fitted(message, gathered)
            if note:
                parts.append(note)
        # Every question of the user's is a wish to know: kept as one. An action is the agent's.
        for request in got.requests:
            if request["kind"] == "know":
                await self._wanted(request["text"])
        return parts

    async def _fitted(self, message: str, gathered: list[str]) -> str:
        """What was found, made into one note for this message: only what bears on it, adapted to it,
        each line with the facts and days it stands on. A view for the agent, made anew for every
        message; the facts in the memory stay as they are. Unread, the found is given as found."""
        try:
            said = (await self.base._read(FIT.format(message=message, found="\n\n".join(gathered)))).strip()
        except Exception:  # noqa: BLE001 - not fitted: given as found
            log.exception("fitting the note failed")
            return "\n\n".join(gathered)
        if not said or said.lower().strip(" .") == "nothing":
            return ""
        return "From before, for this message (fact numbers and days; the user's latest word wins):\n" + said

    def _heard_as(self, role: str, text: str) -> None:
        from memory.intake.intake import WINDOW
        self.recent = (self.recent + [{"role": role, "text": " ".join(SECRETS.sub("[withheld]", text).split())}])[-WINDOW:]

    def _read(self, said: str):
        """The intake of one message, with the messages before it: the gate reads the last few,
        the rewrite the agent's message just before."""
        from memory.intake.intake import Read, read
        from memory.models import role
        messages = self.recent + [{"role": "user", "text": said}]
        try:
            return read(messages, len(messages) - 1, role("sorter"), role("resolver"))
        except Exception as wrong:  # noqa: BLE001 - see below
            # A message the models could not read is kept as it was said, to be read when they are
            # back: never a write refused (2026-10-27, a 402 from Token Factory dropped five
            # messages); and nothing is searched for or forgotten on a question nobody answered.
            log.warning("say: %r", wrong)
            return Read(said, for_memory=1.0, information=[said], note="unread")

    async def _wanted(self, question: str) -> None:
        """A question of the user's, kept as their interest: how often they come back to a thing says
        what the memory should prepare first. Not answered here and not searched for: the agent
        answers, asking the memory; a search from here raced the agent's own `ask` for the same
        thing (2026-10-28, two gatherings for one concert)."""
        same = await self._same_job(question, self.wanted)
        now = f"{datetime.now():%Y-%m-%d %H:%M:%S}"
        if same is not None:
            same["times"] += 1
            self._record({"id": same["id"], "asked_again": now})
            return
        wish = {"id": self._next_id(), "asked": question, "by": "user", "at": datetime.now(), "times": 1}
        self.wanted.append(wish)
        self._record({"id": wish["id"], "asked": question, "by": "user", "at": now})

    def _next_id(self) -> int:
        return max((j["id"] for j in self.jobs + self.wanted), default=0) + 1

    async def _sort(self, message: str, agent_said: str, only=tuple(QUESTIONS), who="The user says") -> dict:
        from memory.models import role
        judge = role("sorter")
        said = (f'The agent said: "{agent_said[-1500:]}"\n\n' if agent_said else "") + f'{who}: "{message[-4000:]}"'

        def ask(key):
            q, yes, no = QUESTIONS[key]
            try:
                return judge.noul(said, q, true=yes, false=no)["p"]["yes"]
            except Exception as wrong:  # noqa: BLE001 - unasked: see below
                log.warning("say %s: %r", key, wrong)
                return None
        got = dict(zip(only, await asyncio.gather(*(asyncio.to_thread(ask, k) for k in only))))
        # Unanswered is not a search: nothing is looked into on a question nobody answered.
        return {k: got.get(k) or 0.0 for k in QUESTIONS}

    def _remember(self, text: str, said: str, now: str | None, withheld: bool) -> str:
        """The message as the intake rewrote it to stand alone, with the words as said beside it
        when they differ. Not the agent's message: the rewrite is what makes the user's understood
        without it (the user, 2026-10-28)."""
        if not said.replace("[withheld]", "").strip():
            return ""
        told = None
        try:
            told = datetime.fromisoformat((now or "").strip())
        except ValueError:
            pass
        text = " ".join(text.split())
        if text != said:
            text = f'{text}\n(said: "{said}")'
        number = self._keep(text, "the user", told)
        self._changed()
        return f"Kept as entry #{number}." + (" (A secret in it was withheld.)" if withheld else "")

    def _start(self, asked: str, by: str, job: dict | None = None) -> dict:
        """A gathering in the background; its question and, once done, its answer are kept beside
        the user's interests, so a later question of the same is answered from it."""
        from concurrent.futures import Future
        if job is None:
            job = {"id": self._next_id(), "asked": asked, "by": by,
                   "at": datetime.now(), "delivered": False}
            self.jobs.append(job)
            self._record({"id": job["id"], "asked": asked, "by": by, "at": f"{job['at']:%Y-%m-%d %H:%M:%S}"})
        job["future"] = Future()

        def work():
            try:
                found = self._solve(asked)
                job["future"].set_result(found)
                job["answered_at"] = datetime.now()
                self._record({"id": job["id"], "answer": found, "answered_at": f"{job['answered_at']:%Y-%m-%d %H:%M:%S}"})
            except Exception as wrong:  # noqa: BLE001 - said, not lost
                job["future"].set_exception(wrong)
            if not job["delivered"]:
                # Not asked for by the agent in the meantime: brought up with the next answer, for
                # the agent to judge whether the question is still the user's.
                self._delivered(job)
                try:
                    self.note(f"Asked of the memory before: \"{asked[:300]}\" (asked {job['at']:%Y-%m-%d %H:%M}). "
                              f"What the memory found is below. If the question is still the user's, give "
                              f"it to them; if it is not, leave it:\n{job['future'].result()}")
                except Exception as wrong:  # noqa: BLE001
                    self.note(f"Looking into \"{asked[:200]}\" failed: {wrong!r}")
        threading.Thread(target=work, daemon=True).start()
        return job

    def _delivered(self, job: dict, force: bool = False) -> None:
        if force or not job["delivered"]:
            job["delivered"] = True
            self._record({"id": job["id"], "delivered_at": f"{datetime.now():%Y-%m-%d %H:%M:%S}"})

    def _record(self, line: dict) -> None:
        """The user's interests, beside the journal: what they wanted to know, and what was found."""
        if self.interests_path is None:
            return
        import json
        with self._lock, self.interests_path.open("a") as file:
            file.write(json.dumps(line, ensure_ascii=False) + "\n")

    def load_interests(self) -> None:
        """Read the interests back: the user's questions with how often they were asked, and the
        agent's gatherings; one asked and never answered is looked into again."""
        import json
        from concurrent.futures import Future
        if self.interests_path is None or not self.interests_path.exists():
            return
        held: dict[int, dict] = {}
        for line in self.interests_path.read_text().splitlines():
            try:
                r = json.loads(line)
            except ValueError:
                continue
            j = held.setdefault(r["id"], {"id": r["id"], "delivered": False})
            if "asked" in r:
                j.update(asked=r["asked"], by=r.get("by", "user"), at=datetime.fromisoformat(r["at"]), times=1)
            if "asked_again" in r:
                j["times"] = j.get("times", 1) + 1
            if "answer" in r:
                j["future"] = Future()
                j["future"].set_result(r["answer"])
                j["answered_at"] = datetime.fromisoformat(r["answered_at"])
            if "delivered_at" in r:
                j["delivered"] = True
        # A question of the user's that a gathering answered is from before 2026-10-28, when the
        # user's questions were looked into: a gathering all the same, its answer kept.
        self.wanted = [j for j in held.values() if "asked" in j and j["by"] == "user" and "future" not in j]
        self.jobs = [j for j in held.values() if "asked" in j and j not in self.wanted]
        for j in self.jobs:
            if "future" not in j:
                self._start(j["asked"], j["by"], job=j)

    def interests(self) -> list[dict]:
        """What the user wanted to know, how many times, and what the agent had gathered."""
        return ([{"asked": j["asked"], "at": f"{j['at']:%Y-%m-%d %H:%M}", "by": "user", "times": j["times"]}
                 for j in self.wanted] +
                [{"asked": j["asked"], "at": f"{j['at']:%Y-%m-%d %H:%M}", "by": j["by"],
                  "answered": f"{j['answered_at']:%Y-%m-%d %H:%M}" if j.get("answered_at") else None,
                  "given": j["delivered"]} for j in self.jobs])

    def _vector(self, text: str):
        if self._embed is None:
            return None
        import numpy as np
        v = np.array(list(self._embed([" ".join(text.split())]))[0], dtype=float)
        return v / (np.linalg.norm(v) or 1.0)

    async def _same_job(self, question: str, among: list[dict] | None = None) -> dict | None:
        """The question in `among` (the agent's gatherings by default) this one repeats, if any: by
        meaning, and in the band where meaning alone can't tell, by the judge. Without embeddings,
        the judge over the recent ones."""
        from memory.models import role
        among = self.jobs if among is None else among
        v = await asyncio.to_thread(self._vector, question)
        if v is not None:
            scored = []
            for job in among:
                if job.get("v") is None:
                    job["v"] = await asyncio.to_thread(self._vector, job["asked"])
                scored.append((float(job["v"] @ v), job))
            scored.sort(key=lambda sj: -sj[0])
            candidates = [j for sim, j in scored if sim >= SAME_QUESTION_MAYBE][:3]
            if scored and scored[0][0] >= SAME_QUESTION:
                return scored[0][1]
        else:
            now = datetime.now()
            candidates = [j for j in reversed(among) if "future" not in j or not j["future"].done()
                          or (now - j.get("answered_at", j["at"])).total_seconds() < FRESH_JOB][:5]
        for job in candidates:
            try:
                p = await asyncio.to_thread(lambda j=job: role("sorter").noul(
                    f'Asked before: "{j["asked"][:1000]}"\n\nAsked now: "{question[:1000]}"',
                    "Is what is asked now the same question as what was asked before?",
                    "yes, the same question", "no, a different one")["p"]["yes"])
            except Exception:  # noqa: BLE001 - not known to be the same: a question of its own
                continue
            if p >= 0.5:
                return job
        return None

    def _repeated(self, job: dict) -> str:
        """The agent asks again what was gathered before: what is ready is given at once."""
        self._record({"id": job["id"], "asked_again": f"{datetime.now():%Y-%m-%d %H:%M:%S}"})
        if not job["future"].done():
            return (f"This was asked before ({job['at']:%Y-%m-%d %H:%M}); the memory is still looking "
                    f"into it and will bring up what it finds.")
        try:
            found = job["future"].result()
        except Exception:  # noqa: BLE001 - it failed before: looked into again
            self._start(job["asked"], job["by"], job=job)
            return "This was asked before; looking into it failed then, and the memory is looking into it again."
        self._delivered(job, force=True)
        old = (datetime.now() - job.get("answered_at", job["at"])).total_seconds() > FRESH_JOB
        if old:
            # Given at once all the same, with its date; and prepared again, for next time.
            self._start(job["asked"], job["by"], job=job)
        return (f"This was asked before ({job['at']:%Y-%m-%d %H:%M}). What the memory prepared for it "
                f"({job.get('answered_at', job['at']):%Y-%m-%d %H:%M}" + (", may be out of date; being refreshed" if old else "")
                + f") — for you and the user to decide from:\n{found}")

    async def _gather(self, question: str, wait: bool, progress) -> str:
        """The agent asked: answered, whatever it takes — from a gathering already under way for
        the same request, or a new one."""
        job = await self._same_job(question)
        if job is not None and job["future"].done():
            return self._repeated(job)
        job = job or self._start(question, by="agent")
        self._delivered(job)
        future = asyncio.wrap_future(job["future"])
        beat = 0
        while not future.done():
            await asyncio.wait({future}, timeout=20)
            if not future.done() and progress:
                beat += 1
                await progress(beat)
        return ("The facts the memory gathered for this — for you and the user to decide from:\n"
                + future.result())

    async def _prepare_forget(self, message: str) -> str:
        gone = await self.base.choose_forget(message)
        if not gone:
            return "The user asked to forget something, but no entry says it: nothing was forgotten."
        texts = {n: text for n, _, text in self.base._entries(self.base._memory())}
        self.waiting_forget = {"what": message, "entries": gone}
        listed = "\n".join(f"- #{n}: {' '.join(texts.get(n, '').split())[:200]}" for n in gone)
        return ("To forget, the memory would take out these entries:\n" + listed + "\n\nNothing is taken "
                "out yet. Ask the user to confirm, and pass their answer with `say`.")

    async def _confirm(self, message: str, now: str | None) -> str:
        from memory.models import role
        waiting, self.waiting_forget = self.waiting_forget, None
        q, yes, no = CONFIRM
        try:
            p = await asyncio.to_thread(lambda: role("sorter").noul(f'The user says: "{message[-2000:]}"', q, yes, no)["p"]["yes"])
        except Exception:  # noqa: BLE001 - unconfirmed is not forgotten
            p = 0.0
        if p < 0.5:
            return ""
        taken = await self.base.take_forget(waiting["entries"], waiting["what"], now)
        return "Forgotten, as the user confirmed — taken out:\n" + taken


# What was found beside one message, fitted to it: the memory decides what bears on it, never what
# to do about it.
FIT = """The user has just written to their assistant:
<message>
{message}
</message>

Their personal memory found the following. Some of it may not bear on this message.

{found}

Bearing on it is whatever the assistant should know to answer it well: what the memory knows of \
the things the message names or points to ("the TV" is the TV the user has), of the people it \
names, and of the matter it goes on with. Write for the assistant only that, adapted to the \
message: a few short lines, each \
with the fact numbers and the days it stands on, the user's own words quoted where they matter. \
Keep what was ruled out or changed, and when, where it bears on the message. When the user asked \
something the memory answers, give that answer first. Say nothing the found text does not say, \
and give no advice: deciding is the assistant's. If nothing bears on the message, answer with the \
single word: nothing."""


def _reply(parts: list[str]) -> str:
    return "\n\n".join(p for p in parts if p) or "nothing"
