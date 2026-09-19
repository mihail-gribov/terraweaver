# PerQA

Synthetic personal data and questions from the PerQA benchmark (ReQAP, ACL 2025 Findings):
https://reqap.mpi-inf.mpg.de/ — Philipp Christmann and Gerhard Weikum, "Recursive Question
Understanding for Complex Question Answering over Heterogeneous Personal Data",
arXiv:2505.11900.

Licensed under CC BY 4.0 (https://creativecommons.org/licenses/by/4.0/). Unmodified copy in
`raw/` (not committed: ~500 MB). Re-download:

    for s in train dev test; do
      curl -sSLO https://reqap.mpi-inf.mpg.de/static/$s.zip && unzip -q $s.zip -d raw && rm $s.zip
    done

## Layout

`raw/{train,dev,test}/<split>_persona_<n>/` — 20 personas (12 train, 2 dev, 6 test):

- `<persona>.json` — the persona: names, family, friends, partners, tastes, habits.
- `<persona>_str.csv` — structured events (ground truth): `event_type` + JSON `event_data`.
  793k in total: music_stream (703k), movie_stream, workout, meet_up, online_purchase,
  tvseries_stream, trip_highlight, annual_celebration, annual_doctor_appointment, trip,
  oneoff_event.
- `<persona>_obs.csv` — what the user's devices would actually show: calendar entries, mails,
  social media posts, streams, purchases. Each row points back to its `structured_event_id`
  and lists `properties_mentioned`. 812k in total.
- `questions.json` — 17.6k questions in total, each with `question`, `sql_query` over the
  structured events, `answers` and `reference_date` ("this year" is relative to it).

## Use in TerraWeaver

- **Read tests:** load structured events into the world, let the host answer the questions
  in code, compare with `answers`.
- **World-building tests:** feed the observable texts (mails, calendar, posts) to `remember`
  and compare the resulting world with the structured events — the obs → str link is exactly
  the ground truth for extraction.
- **Procedural memory:** questions repeat the same analytical patterns with different
  parameters — material for harvesting procedures.
