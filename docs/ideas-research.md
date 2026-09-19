# Ideas: search, research and monitoring

Not planned work yet — directions for using web search in the world, collected while testing
the host scenarios. The common case behind them is gathering information about something over
time: a TV and a hair dryer to buy, a neighbourhood, a school, a car, a company before an
interview.

## The shape of the case

- There is a subject — an entity in the world: a Place (neighbourhood), an Organization
  (school), a thing (TV, car).
- Information about it accumulates, from conversations and from search, each piece with a
  source and a date.
- There are options and criteria; options drop out with a reason ("LG ruled out: glare"), and a
  decision comes later.

## Research on any entity

    job = school.research("admission deadlines, ratings, distance from home")

- Asynchronous: returns a job at once, the host carries on with other tasks.
- Runs inside the world: Nemotron splits the question, Tavily searches, values are extracted
  and checked against the source snippet.
- Results land on the entity itself: comments with `source`, date and a ttl (web facts go
  stale); new options as candidates until the user picks.
- The host learns it's done from a `[jobs]` line in the next run result, or `wait(job, 30)`.
  A job that hits an ambiguity waits in the queue of questions for the user.
- Jobs outlive the conversation: the next conversation finds the results in the world.

## Deep research by the host

A host with its own web tools (Claude Code) can run a long investigation itself: plan, search,
read, conclude. The world's part is keeping the result where it will be looked for — sourced,
dated facts on the subject and candidates — so the next conversation, or another agent, starts
from what was found. Needs a `source` field on comments.

## Monitoring and background collection

Only the world can do these — a host exists only while a conversation lasts.

- `entity.watch("price and availability", every=timedelta(days=3))`: repeat the search, compare
  with what's known, put changes in a news queue shown at the next interaction ("QN90D is down
  to $1,299", "school enrolment opened").
- An expired web-sourced comment is a natural trigger to check again.
- Automatic enrichment of a newly recorded school or car — only with the user's consent: it
  costs credits (Tavily: ~1,000 free a month) and sends (de-identified) queries outside.

## Missing pieces this would need

- Background jobs in the world server: queue, `wait`, `[jobs]` in run results.
- `source` on comments.
- A class for things that are chosen, bought and owned (`Item`): status idea → candidate →
  ruled out → chosen → bought → sold, for whom, price, links. In the s05 scenario the host had
  to use Project + tagged Ideas, and the candidates ended up unlinked from the project.

Suggested order when this becomes work: research → jobs → watch → deep research support.
