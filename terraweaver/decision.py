"""The decision model: closed questions answered by Nemotron itself, as calibrated probabilities.

The world asks two kinds of question (`outside`): open ones, where a word has to be written, and
closed ones — which of these named options — where the volume is. The closed ones went to Jev, a
hosted decision model, or to `typecastlm`, a Jev-class model with open weights; both are another
party to depend on, and Jev stopped answering (402). Nemotron answers them itself, through the same
client that serves it as the engineer (`terraweaver.nemotron.Nemotron`):

- **One letter, read, not generated.** The options are lettered, thinking is switched off, and the
  answer is the first token. Token Factory returns that token's log-probabilities, so one call with
  one token out gives a number per option. Measured: 0.37 s a question on the Nano.
- **Both ways round.** The model leans towards whichever letter comes first (75–79% where it
  should be half), so a question is read with its options as given and reversed and the two
  log-probabilities averaged.
- **Normalised per mode.** One temperature per mode, fitted on labelled public rows
  (`experiments/09_decision`) by calibration error and shipped beside this file (`decision.json`)
  for the model it was fitted for.
- **A third answer.** `tfu` reads the same question over three options — the two criteria and
  "the text does not settle it" — which is the abstention a forced yes or no cannot give.

What is here is the world's side of it: the `outside.Closed` connector, and the picker a deployment
gets. The shapes and the result fields are Jev's, so every caller of `outside.Closed` reads this the
same.
"""
import os

from terraweaver import outside
from terraweaver.nemotron import CALIBRATION, MODEL, UNSETTLED, Nemotron, fitted_for  # noqa: F401 - re-exported


class Decision(outside.Closed):
    """Nemotron on Token Factory as the picker: `ask(state, questions)` in Jev's shape.

    noul   {"true": .., "false": ..}          -> {"noul": p(true), "logits"}
    tfu    the same two criteria               -> {"noul", "unsure", "probabilities", "logits"}
    choice {name: description, ...}           -> {"probabilities", "choice", "logits"}
    scale  {level: description, ...} ordered  -> {"probabilities", "choice", "logits"}
    """

    # Read links as claims in `formalise.check`: this model answers "does the sentence say «a w b»"
    # well and the three-way link question not at all (experiments/09_decision).
    asks_claims = True

    def __init__(self, model: str = MODEL, key: str | None = None, ttl: float = 30.0,
                 calibration=CALIBRATION, workers: int = 8, client=None):
        self.model = model
        self.reader = Nemotron(model=model, base_url=outside.NEBIUS, api_key=key, timeout=ttl,
                               calibration=calibration, workers=workers, client=client)

    def ask(self, state: str, questions: dict) -> dict:
        """Every question about one state, asked at once: each is its own call of one token."""
        return self.reader.ask(state, questions)


def picker() -> outside.Closed | None:
    """The picker this deployment has, asked once before it is relied on; None when there is none.

    Nemotron on Token Factory, wherever `NEBIUS_API_KEY` is set. A picker that refuses every call
    would leave every reading unread where the engineer standing in would have read them, hence
    the one question first.
    """
    if not os.environ.get("NEBIUS_API_KEY"):
        return None
    try:
        chosen = Decision()
        chosen.choose("Rome is a city in Italy.", "Which of these is Rome?",
                      {"City": "a city", "Person": "a person"})
        return chosen
    except Exception:  # noqa: BLE001 - without a picker the engineer chooses
        return None
