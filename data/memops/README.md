# MemOps

"MemOps: Benchmarking Lifecycle Memory Operations in Long-Horizon Conversations"
(arXiv:2607.12893), https://github.com/MemTensor/MemOps — MIT license. Clone in `raw/`
(not committed: ~270 MB). Re-download:

    git clone --depth 1 https://github.com/MemTensor/MemOps raw

## What's in it

Memory as a lifecycle of operations rather than a pile of facts. Each sample is a
conversation plus the gold trace of what memory should do with it.

`raw/generated_result/`:

- `1-background/A01.md …` — 100 topic backgrounds (the facts a persona has on one topic).
- `2-evidence_conversation/<topic>_<operation>.json` — 403 samples. Keys:
  - `target_fact`, `operation_type` (Remember 68, Update 77, Forget 80, Reflect 96,
    TrajectoryOps 82), `difficulty_knobs` (recency trap, update chain, multi-target,
    multi-hop, negative seed, adversarial injection);
  - `operations` — the gold trace: `type` (remember / update / forget / reflect),
    `validity` (confirmed / tentative / retracted), `target`, `old_value` → `new_value`,
    and `trigger_span` / `evidence_spans` quoting the exact user turn;
  - `conversations` — segments of user/assistant dialogue;
  - `answer` — probe questions with expected answers.
- `2-evidence_trace/` — the same traces without the probes.
- `4-inject_evidence_with_distractors/` — the evidence buried in long unrelated dialogue.

`raw/info/topics.md` — the topic codes: A = the user themselves (job, city, health…),
B = people around them (friends, colleagues, family, their contacts), C = plans and
obligations (to-dos, deadlines, appointments, travel), D = belongings and habits,
E = misspoken or corrected statements, F = sensitive or temporary states.

## Use in TerraWeaver

Write-side tests: feed the user turns to the world (a host with `ensure`, or `remember`),
then compare the world with the gold trace:

- confirmed values are current;
- tentative ones are not recorded as current fact;
- a forgotten target is gone while related facts stay;
- an update binds to the same target instead of creating a second one.

Gaps it exposes in the world as it is now:

- no way to forget (delete) an entity or a fact;
- no notion of a tentative fact beyond `Preference.confidence`;
- many targets (spouse, children, pet, medication, commute) have no attribute in the fixed
  class set — material for attribute growth (`docs/schema-growth.md`).
