"""Tests for the two doors, `say` and `ask` (memory/listen.py): who said what, what is kept, what
is never kept, a forget only once confirmed, and the agent's question routed; the intake read with stand-in models.

Run: .venv/bin/python tests/test_listen.py        # no model calls: the judge is a stand-in
"""
import asyncio
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import memory.models  # noqa: E402
from memory import journal as base  # noqa: E402
from memory.listen import Listener  # noqa: E402

failures: list[str] = []


def check(name: str, condition: bool, detail: str = "") -> None:
    print(f"{'PASS' if condition else 'FAIL'}  {name}" + (f"  — {detail}" if detail and not condition else ""))
    if not condition:
        failures.append(name)


class Judge:
    """Yes by words, for the intake and the doors: personal when the user's message names Mila, the
    flat, a budget, a flight, or asks something; a question when it asks or says find/forget; a
    forget on "forget"; general knowledge on "TCP"; a confirmation on "yes"."""
    down = False
    prompts: list[str] = []
    gated: list[str] = []

    @staticmethod
    def _user(text):
        return text.rsplit('The user: "', 1)[-1].rsplit('"', 1)[0].lower()

    def say(self, system, prompt, room=None, thinking=True):
        import json
        Judge.prompts.append(prompt)
        said = prompt.rsplit('The user: "', 1)[-1].rsplit('"', 1)[0]
        low = said.lower()
        message = ("My budget for the new robot vacuum is up to 400 euros."
                   if "400" in said and "The assistant:" in prompt else said)
        asks = "?" in said or low.startswith(("find", "please find", "please forget", "forget", "can you"))
        return json.dumps({"new_topic": False, "message": message, "questions": [message] if asks else []})

    def noul(self, state, question, true, false):
        if Judge.down:
            raise RuntimeError("402 Payment Required")
        q = question.lower()
        said = self._user(state)
        if "personal life" in q:
            Judge.gated.append(state)
            yes = any(w in said for w in ("mila", "flat", "400", "flight", "find", "forget", "?"))
        elif "something the user asks" in q:
            yes = True
        elif "give what was asked" in q:
            yes = "does not say" not in state.lower()
        elif "general knowledge" in q:
            yes = "tcp" in state.lower()
        elif "same question" in q:
            first, _, now = state.lower().partition("asked now:")
            words = lambda t: {w.strip('".?,').rstrip("s") for w in t.split() if len(w.strip('".?,')) > 4} - {"before:", "asked"}
            yes = len(words(first) & words(now)) >= 2
        elif "confirm" in q:
            yes = "yes" in state.lower().rsplit(": \"", 1)[-1]
        elif "found, looked up" in q:
            yes = "find" in state.lower().rsplit(": \"", 1)[-1]
        else:
            yes = False
        return {"p": {"yes": 0.9 if yes else 0.1, "no": 0.1 if yes else 0.9}}

    def choice(self, state, question, options):
        asked = state.lower().rsplit("taken out of the last message:", 1)[-1]
        kind = "memory" if "forget" in asked else "action" if "book" in asked else "know"
        return {"choice": kind, "p": {kind: 0.8}}


def listener(where: Path) -> tuple[Listener, list]:
    base.facts = where / "facts.md"
    base.confirm_forget = None
    solved = []

    async def context(message, limit):
        return "- Mila and Alex live in Belgrade." if "live?" in message else "nothing"

    async def ask(question):
        return "Mila and Alex live in Belgrade." if question.lower().startswith("where") else f"The memory does not say. (asked {question!r})"

    async def choose(what):  # the reader that picks entries to forget, without a model
        return [n for n, _, text in base._entries(base._memory()) if "mila" in text.lower()]
    base.choose_forget = choose
    def solve(text):
        import time
        solved.append(text)
        time.sleep(0.3)
        return f"candidates for {text!r}"
    return Listener(base, base._keep, context, ask, solve, lambda: None, interests_path=where / "interests.jsonl"), solved


def journal() -> str:
    return base.facts.read_text() if base.facts.exists() else ""


def main() -> int:
    memory.models.role = lambda name: Judge()
    with tempfile.TemporaryDirectory() as tmp:
        heard, solved = listener(Path(tmp))
        run = lambda *a, **k: asyncio.run(heard.say(*a, **k))

        out = run([{"role": "user", "text": "Let's refactor this function."}])
        check("work talk is not kept", journal() == "", journal())
        out = run([{"role": "user", "text": "Can you explain a TCP handshake?"}])
        check("a question of general knowledge: a wish kept, not looked into", "TCP handshake" in journal()
              and "looking into" not in out and not solved, out)

        run([{"role": "user", "text": "My wife Mila would love a candlelight concert."}])
        check("the user's life is kept, in their words, as the user's", "· the user\nMy wife Mila would love" in journal(), journal())

        run([{"role": "agent", "text": "What budget do you have for the vacuum?"}])
        check("the agent's reply alone is never kept", "budget do you have" not in journal())
        run([{"role": "user", "text": "up to 400 euros"}])
        check("the user's answer is rewritten to stand alone, with the words as said beside it, not the agent's",
              'My budget for the new robot vacuum is up to 400 euros.\n(said: "up to 400 euros")' in journal() and "What budget" not in journal(), journal())
        check("the rewrite is shown the agent's message just before, and nothing earlier",
              "What budget do you have" in Judge.prompts[-1] and "Mila" not in Judge.prompts[-1], Judge.prompts[-1])
        check("the gate reads the user's messages before it too", "Mila" in Judge.gated[-1], Judge.gated[-1])
        run([{"role": "user", "text": "Mila's flat has thick rugs"}])
        check("with no agent's message before it, the message is kept as said, alone",
              "· the user\nMila's flat has thick rugs\n" in journal() + "\n" and "(said: \"Mila's flat" not in journal(), journal())

        run([{"role": "memory", "text": "From the user's personal memory: Mila lives in the flat"}])
        check("what the memory said itself is never taken back in", "From the user's personal memory" not in journal())

        run([{"role": "tool", "text": "Your flight to Lisbon on 12 November is confirmed.", "source": "email from the airline"}])
        check("what a tool read is not heard: it reaches the memory through the user's answer", "Lisbon" not in journal(), journal())

        run([{"role": "user", "text": "my flat wifi password is: hunter2 and token ghp_abcdefghijklmnopqrstuvwxyz123456"}])
        check("a secret is withheld before it is kept", "hunter2" not in journal() and "ghp_" not in journal() and "[withheld]" in journal(), journal())
        check("a secret never reaches the models", not any("hunter2" in p or "ghp_" in p for p in Judge.prompts))

        Judge.down = True
        run([{"role": "user", "text": "Tom works from home on Mondays"}])
        Judge.down = False
        check("a message the models could not read is kept, not dropped", "Tom works from home on Mondays" in journal())

        out = run([{"role": "user", "text": "Please find me a candlelight concert"}])
        check("the user's request to find is kept as their interest, not searched for",
              not solved and "Please find me a candlelight concert" in [i["asked"] for i in heard.interests()]
              and "looking into" not in out, out)
        got = asyncio.run(heard.ask("find candlelight concerts in Belgrade this winter"))
        check("the agent's `ask` is what gathers: one search, answered", solved == ["find candlelight concerts in Belgrade this winter"]
              and "candidates for 'find candlelight concerts in Belgrade this winter'" in got, f"{solved} / {got}")
        out = run([{"role": "user", "text": "Please find me a candlelight concert?"}])
        concert = [i for i in heard.interests() if i["asked"] == "Please find me a candlelight concert"]
        check("the user asking again counts the interest once more, nothing searched",
              len(solved) == 1 and concert and concert[0]["times"] == 2, str(heard.interests()))
        import time
        out = run([{"role": "user", "text": "thanks"}])
        check("what the agent was given is not brought up again", "wanted to know" not in out and "asked of the memory" not in out.lower(), out)

        before = journal()
        out = run([{"role": "user", "text": "Please forget everything about Mila"}])
        check("a forget is only proposed: nothing taken out yet", journal() == before and "confirm" in out.lower(), out)
        out = run([{"role": "user", "text": "yes, go ahead"}])
        check("confirmed, the entries go", "Mila" not in journal().split("· forget")[0].split("The user asked")[0], journal())

        out = asyncio.run(heard.ask("What is Tom's surname?"))
        check("the agent's question is answered from the memory, nothing kept", "does not say" in out and "surname" not in journal(), out)
        out = run([{"role": "user", "text": "Where do Mila and I live?"}])
        check("the user's question: what the memory holds is put beside it, nothing searched",
              "live in Belgrade" in out and len(solved) == 1, out)
        out = run([{"role": "user", "text": "When is Mila's flat lease up?"}])
        check("a question the memory can't answer: kept as an interest, still nothing searched",
              len(solved) == 1 and "looking into" not in out, out)
        got = asyncio.run(heard.ask("find a good dentist in Belgrade"))
        check("the agent's own request to find is gathered and answered", solved[-1] == "find a good dentist in Belgrade" and "candidates" in got, got)
        time.sleep(0.6)
        asked = {i["asked"]: i for i in heard.interests()}
        check("the user's questions are kept as their interests, the agent's gatherings beside them",
              asked.get("When is Mila's flat lease up?", {}).get("by") == "user"
              and asked.get("find a good dentist in Belgrade", {}).get("answered"), str(asked))
        again, solved_again = listener(Path(tmp))
        again.load_interests()
        check("interests outlive a restart, with their counts and the gatherings' answers",
              again.interests() == heard.interests() and not solved_again, f"{again.interests()} / {heard.interests()}")
        got = asyncio.run(again.ask("find a good dentist in Belgrade"))
        check("a gathering answered lately answers the same again, no new search",
              "candidates for 'find a good dentist in Belgrade'" in got and not solved_again, f"{solved_again} / {got[:200]}")
        def bag(texts):  # a stand-in for embeddings: words as dimensions
            import numpy as np
            vocab = ["quiet", "robot", "vacuum", "concert", "mila", "lease", "flat", "dentist"]
            return [np.array([float(w in t.lower()) for w in vocab]) + 1e-6 for t in texts]
        third, solved3 = listener(Path(tmp))
        third._embed = bag
        third.load_interests()
        got = asyncio.run(third.ask("find a good dentist in Belgrade, please"))
        check("asked in other words, by meaning: what was prepared is given at once, no new search",
              "asked before" in got and "candidates for 'find a good dentist in Belgrade'" in got and not solved3, got[:300])
    from memory import server

    class Ctx:
        def __init__(self, headers):
            self.headers = headers
    got = asyncio.run(server.say([{"role": "user", "text": "Mila likes jazz"}], Ctx({"x-personal-hooks": "on"})))
    check("a client whose hooks pass every message is not heard through `say` as well", got == server.HOOKED, got)
    check("a client without the header is heard", not server.hooked(Ctx({})) and not server.hooked(Ctx(None)))
    print(f"\n{len(failures)} failed" if failures else "\nall passed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
