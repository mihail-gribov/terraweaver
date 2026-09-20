"""Deciding whether an answer is right, and saying how that decision was made.

LongMemEval scores with a model judge and type-specific rubrics, because the gold answer is a
phrase and a good response is a sentence. We keep that shape and change one thing: the judge is
named in the results, because a score without its judge is not comparable to anybody's — the
same rule as naming the backbone and the embedder.

Abstention is judged by us, not by the model. Thirty of the 500 questions have no answer in the
history, and the right response is to say so; that is a string check against a refusal, not a
semantic match, and it is the one place where being strict is fairer than being clever.
"""
import re

from host import plain

RUBRIC = {
    "temporal-reasoning":
        "The response must get the timing right — dates, order, or duration. A response with "
        "the right facts but the wrong date or order is wrong.",
    "knowledge-update":
        "The fact changed during the history. The response must give the latest value. Giving "
        "the old value, or both without saying which holds now, is wrong.",
    "single-session-preference":
        "The response must reflect the stated preference. It may be phrased as advice as long "
        "as the preference is honoured.",
}

DECLINES = ("don't know", "do not know", "not know", "no record", "nothing in", "not in my",
            "cannot find", "can't find", "couldn't find", "no information", "isn't recorded",
            "is not recorded", "not recorded", "nothing recorded", "unable to find",
            "doesn't say", "does not say", "no mention", "not mentioned", "unsure")


def declined(answer: str) -> bool:
    lowered = answer.lower()
    return any(phrase in lowered for phrase in DECLINES)


def judge(instance, answer: str, model: str = "haiku") -> dict:
    """{'correct': bool, 'how': 'abstention'|'judge', 'model': …, 'said': raw verdict}"""
    if instance.abstention:
        return {"correct": declined(answer), "how": "abstention", "model": None, "said": ""}
    if not answer.strip():
        return {"correct": False, "how": "empty", "model": None, "said": ""}

    extra = RUBRIC.get(instance.kind, "")
    prompt = (
        "You are grading one answer from a personal assistant against the reference answer.\n\n"
        f"Question: {instance.question}\n"
        f"Reference answer: {instance.answer}\n"
        f"Assistant's answer: {answer.strip()[:4000]}\n\n"
        f"{extra}\n"
        "The assistant's answer is correct if it contains the reference answer's information, "
        "however it is worded, and does not contradict it. Extra detail is fine.\n"
        "Reply with one word: CORRECT or WRONG."
    )
    said = plain(prompt, model=model)
    verdict = re.search(r"\b(CORRECT|WRONG)\b", said.upper())
    return {"correct": bool(verdict and verdict.group(1) == "CORRECT"),
            "how": "judge", "model": model, "said": said[:200]}
