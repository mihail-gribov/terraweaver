"""The sentence door's reading, end to end, with both parties stood in.

Run: .venv/bin/python tests/test_formalise.py

A base world, the host's facts said in words, and the reading that types them: look, make, check,
write. The engineer and the picker are scripted, so what is tested is the pipeline and not a model —
that one is measured in experiments/01_relation_formalisation.
"""
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from terraweaver import authoring, formalise, growth, ontology  # noqa: E402
from terraweaver.formalise import record  # noqa: E402
from terraweaver.runtime import WorldRuntime  # noqa: E402

CORE = Path(__file__).resolve().parent.parent / "ontology" / "core"
failures: list[str] = []


def check(name: str, condition: bool, detail: str = "") -> None:
    print(f"{'PASS' if condition else 'FAIL'}  {name}" + (f"  — {detail}" if detail and not condition else ""))
    if not condition:
        failures.append(name)


class Engineer:
    """Answers each open question with the next scripted block of lines, and keeps what it was asked."""

    def __init__(self, blocks):
        self.blocks, self.asked = list(blocks), []

    def say(self, system, asked):
        self.asked.append(asked)
        return self.blocks.pop(0) if self.blocks else ""


class Picker:
    """The closed questions: which word (scripted), and whether a claim is said (a date only if named)."""

    def __init__(self, words=(), invented=(), word_fits=True):
        self.words, self.invented, self.looked = list(words), set(invented), 0
        self.word_fits = word_fits

    def choose(self, state, question, options):
        # Two different closed questions come through here now: which word, and whether the word
        # the look picked is the same idea as the words that were said. The second is answered yes
        # unless a test says otherwise, so a scripted word is not spent on it.
        if "the same idea" in question:
            return {"says_so": 1.0} if self.word_fits else {"none of these": 1.0}
        self.looked += 1
        want = self.words.pop(0) if self.words else "none of these"
        return {want: 1.0} if want in options else {}

    def ask(self, state, questions):
        out = {}
        for key, asked in questions.items():
            # The date as the world holds it, because the claim is now read from the record and
            # not from the literal the engineer typed: "1792" was written, 1792-01-01 is held.
            bad = any(date in asked["instructions"] for date in self.invented)
            out[key] = {"probabilities": {"not_in_it": 1.0} if bad else {"says_so": 1.0}}
        return out


def base_world():
    where = Path(tempfile.mkdtemp(prefix="tw-formalise-"))
    specs = growth.apply_growth(ontology.base_specs(CORE), {})
    rt = WorldRuntime(str(where / "world.db"), specs=specs, selves=True, home=where)
    authoring.install(rt.world, where / "grown")
    rt.start_task("the host", "record facts said in words, for the reading to type", "recording")
    return rt


def say(rt, words, a, b):
    got = rt.run(f'a = Thing.identify(name="{a}")[0]\nb = Thing.identify(name="{b}")[0]\n'
                 f'world.relate(a, b, {words!r})', "the host")
    assert got["ok"], got


DEFINE = ('world.define_relation("capital_of", "a city that is the seat of a country\'s government", '
          'cardinality="many-to-one", subject_is="a city that serves as a capital", '
          'object_is="the country whose capital it is")\n')


def main() -> int:
    # --- a word made once and found again ---
    rt = base_world()
    say(rt, "Rome is the capital of Italy.", "Rome", "Italy")
    say(rt, "Paris has been the capital of France since 1792.", "Paris", "France")
    engineer = Engineer([DEFINE + "a.set_capital_of(b)", 'a.set_capital_of(b, starts="1792")'])
    picker = Picker(words=["capital_of"])
    got = formalise.formalise(rt, engineer, picker)
    check("both facts are typed", got["typed"] == 2, str(got))
    check("the word is made once and joined once", got["defined"] == 1 and got["joined"] == 1,
          f"defined={got['defined']} joined={got['joined']}")
    check("the first fact is not looked for — the record has no words yet", picker.looked == 1,
          str(picker.looked))
    check("the second is asked with the word already here",
          "The word is already here: `capital_of`" in engineer.asked[1], engineer.asked[1][-600:])
    check("the question never asks for a nature", all("nature" not in a for a in engineer.asked))
    links = {l.display_name(): l for l in rt.world.all("CapitalOf", limit=None)}
    check("the date that was said is on its link",
          any("Paris" in n and l.valid_from is not None for n, l in links.items()), str(links))
    check("nothing is left bare", not any(l.valid_until is None
                                          for l in rt.world.all("Related", limit=None)))

    # Every reading is written down as it happens, because a tally of one number per run cannot
    # tell "typed on the first go" from "typed on the third after two refusals".
    shape = record.distribution(rt.world)
    check("every reading of this world is written down", shape["readings"] >= 2, str(shape))
    check("with how many goes each took",
          all(isinstance(k, int) and k >= 1 for k in shape["goes"]), str(shape["goes"]))
    check("and how it ended", "done" in shape["went"], str(shape["went"]))
    check("and what the check said, with how sure it was",
          shape["verdicts"].get("says_so", 0) >= 2, str(shape["verdicts"]))
    check("and whether the look already had the word",
          shape["the look"]["found a word already there"] >= 1, str(shape["the look"]))
    check("and it reads as lines", "reading(s)" in record.readable(shape),
          record.readable(shape)[:120])


    # --- a date nobody said is never written ---
    rt = base_world()
    say(rt, "Rome is the capital of Italy.", "Rome", "Italy")
    engineer = Engineer([DEFINE + 'a.set_capital_of(b, starts="1792")', DEFINE + "a.set_capital_of(b)"])
    got = formalise.formalise(rt, engineer, Picker(invented=["1792"]))
    trace = got["read"][0]
    check("the invented date is refused on what the record now holds",
          "1792" in trace["answered"][0] and "not bear it out" in trace["answered"][0],
          trace["answered"][0][:120])
    check("and the link that carried it is taken back, not left standing",
          len([l for l in rt.world.all("CapitalOf", limit=None, history=True)
               if l.valid_from is not None]) == 0,
          str([(l.display_name(), l.valid_from) for l in
               rt.world.all("CapitalOf", limit=None, history=True)]))
    check("and the engineer's second block is what lands", trace["went"] == "done", trace["went"])
    rome = rt.world.all("CapitalOf", limit=None)
    check("the link holds no start, which is what the sentence gave",
          len(rome) == 1 and rome[0].valid_from is None, str([(l, l.valid_from) for l in rome]))

    # A failure is written down with whose fault it was. Counted together, a reading the network
    # lost and a reading the check refused both read as "not typed", and they are not the same news.
    rt = base_world()
    say(rt, "Rome is the capital of Italy.", "Rome", "Italy")
    # Lines that run and join nothing: three goes and the reading gives up, which is a judgement
    # about the words and not a breakage of ours.
    formalise.formalise(rt, Engineer(["pass"] * 3), Picker(words=["capital_of"]))
    shape = record.distribution(rt.world)
    check("a reading that gave up is written down as a judgement, not as a breakage",
          shape["went wrong"] == {"substantive": 1}, str(shape["went wrong"]))
    check("and what it was is kept in the words it happened in",
          any("gave up" in what for what in shape["what went wrong"]),
          str(shape["what went wrong"]))

    rt = base_world()
    say(rt, "Rome is the capital of Italy.", "Rome", "Italy")
    formalise.formalise(rt, Engineer([]), Picker(words=["capital_of"]))
    shape = record.distribution(rt.world)
    check("an engineer that said nothing is written down as technical",
          shape["went wrong"] == {"technical": 1}, str(shape["went wrong"]))

    # --- the word the look picks is checked against the words that were said ---
    # Measured 2026-09-29: the look answered `author_of` for facts whose words were `performed`,
    # four times, at 0.95, 0.92, 0.83 and 0.62. A fact under a word that means something else cannot
    # be found by anybody asking in the words it was said in, and it supersedes the wrong things — so
    # the look's answer is a hypothesis, and it is put back to the decision model as a phrase.
    rt = base_world()
    say(rt, "Rome is the capital of Italy.", "Rome", "Italy")
    formalise.formalise(rt, Engineer([DEFINE + "a.set_capital_of(b)"]), Picker(words=["capital_of"]))
    say(rt, "Lou Reed performed Blood on the Tracks.", "Lou Reed", "Blood on the Tracks")
    wrong_word = Picker(words=["capital_of"], word_fits=False)
    plays = ('world.define_relation("performed", "who performed a work", '
             'cardinality="many-to-many", subject_is="the performer", object_is="the work")\n')
    got = formalise.formalise(rt, Engineer([plays + "a.set_performed(b)"]), wrong_word)
    trace = got["read"][0]
    check("a word that does not say what the account says is refused, and a word is made",
          got["defined"] == 1 and "does not say" in str(trace["look"].get("refused")),
          f"defined={got['defined']} look={trace['look']}")

    # --- the goes run out, and the decision model's answer is acted on rather than thrown away ---
    # 12 readings of 355 used to end "not borne out by the words" and 71 "gave up", every one a link
    # the engineer had written and the record then lost, while the picker had already said what was
    # wrong with it.
    rt = base_world()
    say(rt, "Rome is the capital of Italy.", "Rome", "Italy")
    got = formalise.formalise(rt, Engineer([DEFINE + 'a.set_capital_of(b, starts="1792")'] * 3),
                              Picker(invented=["1792"]))
    trace = got["read"][0]
    check("a date the words do not give comes off and the link stays",
          got["typed"] == 1 and trace["went"] == "settled on the picker's verdict",
          f"{got['typed']} typed, went={trace['went']}")
    kept = rt.world.all("CapitalOf", limit=None, history=True)
    check("and the link it stayed as holds no date",
          len(kept) == 1 and kept[0].valid_from is None,
          str([(l.display_name(), l.valid_from) for l in kept]))

    # Which two things a fact is about is the host's to say. A picker that says the words are about
    # something else is not acted on over the link itself: measured, every false alarm came back in
    # exactly that shape — four of sixteen links, two of them above the threshold — and acting on
    # them would have taken correct links back.
    rt = base_world()
    say(rt, "Rome is the capital of Italy.", "Rome", "Italy")
    got = formalise.formalise(rt, Engineer([DEFINE + "a.set_capital_of(b)"] * 3),
                              Picker(invented=["capital of"]))
    check("a picker that says the link is about something else does not unmake it",
          got["typed"] == 1, f"{got['typed']} typed of one")
    check("and the link stands with the word it was given",
          len(rt.world.all("CapitalOf", limit=None)) == 1,
          str([l.display_name() for l in rt.world.all("CapitalOf", limit=None)]))

    # --- read in the order said: an earlier fact is read first and the later one hands over ---
    rt = base_world()
    say(rt, "Anna has worked at Acme since 2019.", "Anna", "Acme")
    say(rt, "Anna left Acme and has worked at Brightwork since March 2023.", "Anna", "Brightwork")
    works = ('world.define_relation("works_at", "a person working for an employer", '
             'cardinality="many-to-one", subject_is="an employee", object_is="an employer")\n')
    engineer = Engineer([works + 'a.set_works_at(b, starts="since 2019")',
                         'a.set_works_at(b, starts="since March 2023")'])
    got = formalise.formalise(rt, engineer, Picker(words=["works_at"]))
    ended = {l.object.display_name(): l.valid_until for l in rt.world.all("WorksAt", limit=None, history=True)}
    check("both employments are typed", got["typed"] == 2, str(got))
    check("the earlier one ends where the later one begins",
          ended.get("Acme") is not None and str(ended["Acme"]).startswith("2023-03-01")
          and ended.get("Brightwork") is None, str(ended))

    # --- the close reads through the same pipeline, and says so ---
    rt = base_world()
    say(rt, "Rome is the capital of Italy.", "Rome", "Italy")
    rt.world.engineer = Engineer([DEFINE + "a.set_capital_of(b)"])
    rt.world.jev = Picker()
    tally = rt._read_what_was_said()
    check("the close types what was said in words", tally.get("typed") == 1, str(tally))
    rt.world.engineer = Engineer([])       # nothing left to read, so nothing is asked
    check("and a second close has nothing to read", rt._read_what_was_said() == {}, "")

    # Whether two words are one idea is a closed question, and it is asked **about the two words**
    # rather than about the account. Measured 2026-09-30 over twenty-four pairs the look had really
    # answered, hand-labelled: asked about the account the decision model was wrong on four of them,
    # confidently — 0.93 that `performed` and `performed_by` differ, 0.99 for `founded` and
    # `founder_of` — and each refusal became another word for an idea the record already had. Asked
    # about the two words: 24/24, never wrong. A spelling rule that chopped endings was tried in
    # between and is gone; no list of endings is complete and it ties the world to one language.
    from terraweaver.formalise.look import says_the_same

    class _Words:
        """Answers the word-pair question, and records what it was shown."""

        def __init__(self, same):
            self.same, self.shown = same, None

        def choose(self, state, question, options):
            self.shown = state
            from terraweaver import prompts
            return {"says_so": 0.95} if self.same else {prompts.NONE_OF_THESE: 0.95}

    asked = _Words(True)
    check("one idea said differently is taken", says_the_same("performed", "performed_by", asked))
    check("and the two words are what it was shown, written out",
          "performed by" in (asked.shown or "") and "_" not in (asked.shown or ""),
          str(asked.shown))
    check("two different ideas take the word away",
          not says_the_same("performed", "author_of", _Words(False)))

    class _Hesitant(_Words):
        def choose(self, state, question, options):
            from terraweaver import prompts
            return {prompts.NONE_OF_THESE: 0.55, "says_so": 0.45}

    check("and a model that only hesitates does not take it away",
          says_the_same("performed", "performed_by", _Hesitant(False)))

    print()
    if failures:
        print(f"{len(failures)} failed: {', '.join(failures)}")
        return 1
    print("all formalise tests passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
