"""Readers from outside the world, for the two kinds of question it cannot answer itself.

There are two ways of getting an answer and they cost differently by an order of magnitude.
A **closed** question — which of these options — is cheap and comes back calibrated, so anything
that can be put as a choice is put as one. An **open** question, where a word has to be invented,
is the expensive kind and is asked only where nothing else will do.

So: naming the two ends of a link type is open and is asked once per type; judging which way a
link runs is closed and is asked once per link. On a hundred-fact world that was 26 open
questions against 115 closed ones, and the closed side is where the volume always is.

Neither reader is required. A world with none does everything it did before and skips the
looking; `inspector` checks for one and marks what it could not read so a later pass finds it.
"""
import json
import os

NAMER = "nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B"

SYSTEM = ("You name the parts of a link type in a record of facts. A link has a subject — the "
          "end it starts from — and an object — the end it leads to. You answer with JSON and "
          "nothing else.")

ASK_NAMES = """Link type: {kind}
What it is: {type_is}
Written like: {examples}

Name what each end IS, as a short noun phrase a thing could be checked against — "a city that
serves as a capital", not "the capital". Keep it wide enough for everything that honestly
belongs there: a religion's followers include people as well as organisations.

Also say whether the word '{kind}' tells a reader which end it starts from. `capital_of` does:
"a capital_of b" reads "a is b's capital". `author` does not: it could start from the writer or
from the book. If it does not, give a word that would.

JSON only:
{{"subject_is": "...", "object_is": "...", "clear_name": "<the word, or a clearer one>"}}"""


def namer(model: str = NAMER, key: str | None = None, ttl: float | None = None):
    """A reader that names the ends of a type. One open question, asked once per type.

    `ttl` is how long the world waits. Measured: most answers come back in four or five seconds
    and one in several takes twenty, so a short wait has most of them for nothing and leaves
    the slow one to a later pass rather than to somebody's patience.
    """
    from openai import OpenAI

    from terraweaver import inspector

    client = OpenAI(base_url="https://api.tokenfactory.nebius.com/v1/",
                    api_key=key or os.environ["NEBIUS_API_KEY"],
                    timeout=ttl if ttl is not None else inspector.TTL)

    def ask(account: dict) -> dict | None:
        if not account:
            return None
        said = client.chat.completions.create(
            model=model, temperature=0, max_tokens=3000,
            messages=[{"role": "system", "content": SYSTEM},
                      {"role": "user", "content": [{"type": "text", "text": ASK_NAMES.format(
                          kind=account["kind"], type_is=account.get("type_is") or "(nobody said)",
                          examples="; ".join(account.get("examples") or []) or "(nothing yet)")}]}],
        ).choices[0].message.content or ""
        # A reasoning model spends its budget thinking first; an empty answer is a budget that
        # ran out, not a refusal, and is worth nothing rather than worth guessing at.
        start, end = said.find("{"), said.rfind("}")
        if start < 0 or end < start:
            return None
        return json.loads(said[start:end + 1])

    return ask
