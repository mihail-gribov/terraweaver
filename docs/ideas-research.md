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


## Settling questions from sources, not only from the user

Open questions (`docs/questions.md`) can be closed by three things: a rule, the user, or a
source that can be checked. The third is this document's job. A doubt about a matter of form —
a company's registered name, a domain that belongs to it, the standard spelling of a city, the
usual shape of a job title — is not the user's to settle: the world can look it up against an
accepted norm and close it with `q.answer(value, by="<the source>")`, keeping where the answer
came from. A doubt about whose life it is — which Olga, whether the dentist changed — is always
the user's, and no source may settle it.

The same split applies to structures, not only values: what attributes a kind of thing usually
has, what a relation of this sort is normally called. The world may refine its own shapes
against common practice; it may not invent facts about the person.


## The boundary, stated once

Search is for **kinds of thing and public entities**: what a doula is, whether Quantinuum is a
company, the registered name behind a trading name, how a city is spelled. It is never for the
person or their circle — not a name, not an address, not a sentence they said. A query is a
sentence handed to a stranger, and nothing that goes into one comes back.

This is what makes search safe to use at all: everything it can be asked is a question about the
world, and the answers are exactly the kind that need no one's permission and can be checked by
anyone. Everything else is settled by the person, or not at all.


## Scenarios, 2026-10-05

Collected while looking at what Tavily returns (`experiments/04_web_search`). Ordered by who
starts the search, because that decides what may go into a query and where the result lands.
Every scenario keeps to the boundary above: a query names kinds of thing and public entities,
never the person or their circle.

1. **"Pick it for me"** — the user asks. Where to go on Saturday (the demo), a thing to buy, a
   trip. The world supplies the city, the free window, who is coming (a six-year-old, a friend who
   likes jazz), what was ruled out before and why. The query carries only "jazz concert, Berlin,
   10 October, daytime, child-friendly". Candidates go into a research world of their own through
   `formalise`, `check.py` verifies each attribute against the page; the host ranks with code;
   only the choice and why cross into the person's world.
2. **Grounding a mention** — the user says, the world completes. "On Sunday we're going to Vortex
   at the Industriesalon" becomes the public event: 11 October, 15:30, Reinbeckstr. 9, with the
   page as the source. The same problem as `world.identify`, with candidates from the web. One
   search and one fetch; the cheapest scenario and the one that shows identity work.
3. **Watching** — the world starts, since a host exists only while a conversation lasts. New
   dates of a band or a venue the person likes, the price of a thing set aside, a deadline
   (school enrolment, ticket sales), a web fact whose ttl ran out (opening hours, a place that
   closed). A repeated search is the watch: `ait-search` already marks pages it has not seen
   (`n_new`). Changes reach the host as a news queue at the next interaction.
4. **Digest** — news and articles on what the world knows the person cares about: work, hobbies,
   projects, organisations in their life. The easiest kind (news came dated 8/8), but it shows
   least of what the world adds.
5. **The world checks itself against the norm** — a canonical spelling, whether X is an
   organisation, what attributes a kind of thing usually has. Questions closed by a source
   (`q.answer(value, by=...)`), and the ontology growing from common practice. Invisible to the
   user.

6. **A selection, and a mention nobody asked for** — in the person's interest. The mechanics of
   advertising — a profile of interests, a selection, a moment to show it — with the profile
   owned by the person and the selection working only for them: nobody pays for a place in it.
   - *Interests come from what was said and done*, not a form: "we went to the jazz, loved
     it", "cancelled the exhibition — boring". Each keeps where it came from; one the world
     inferred is marked as inferred. Needs `Preference` as predicate + value.
   - *Relevance is structural*, not text similarity: matches an interest, in the person's place,
     in a free window, fits who is coming, does not repeat what was ruled out.
   - *Novelty* is the repeated search marking pages not seen before.
   - *When to say it* is the hard part. On request ("anything good this week") is easy. Unasked
     only when the conversation gives the occasion — planning Saturday, the world hands the host
     "jazz at the Industriesalon on Saturday, you liked this kind". At most one per
     conversation, always with why ("because in September you…"); the why is what separates it
     from an ad. It belongs with the other unasked actions in `initiative.py`.
   - *Feedback*: ignored, declined, went — each moves the interest's weight, and the share of
     mentions that helped is the measure.
   - *Things to buy*, the same: the world knows what the person already owns (a camera → the lens
     that fits it, not a second camera), what was set aside and why, what is being watched.
     Signals in the person's interest: a recall of something they own, a warranty running out,
     a price drop on what was set aside — and "this model is no better than yours, don't",
     which no advertiser would say.

7. **A long choice** — a car, a TV, a flat: weeks between the first mention and the purchase,
   and the world working for the person in between.
   - *Criteria crystallise from conversation*, not a form: "too big for our parking", "she wants
     white", "the last one's glare drove me mad". Each new criterion re-filters the candidates
     and may start a new search.
   - *A rejection with its reason becomes a criterion*: "LG is out: glare" — from then on the
     world drops glossy screens itself.
   - *Between conversations the world watches*: prices of the shortlist, new models, reviews,
     second-hand offers that fit.
   - *It reports only what changes the decision*: a new candidate passing every criterion, a
     price drop on the shortlist, a review finding a flaw in the favourite, "a new model is out
     next month — wait". Everything else accumulates quietly and is there when asked.
   - *The purchase is not the end*: the chosen candidate becomes a thing the person owns — the
     same object — and the ownership signals of scenario 6 take over.
   - This settles the open question of 2026-09-25 about research worlds: a one-off search
     ("where to go on Saturday") may drop its world; a long choice keeps its research world alive
     until the choice is closed.

What the first look at Tavily already says the scenarios need:

- **A listing is not an event.** For events search returns listing pages (songkick, artrabbit,
  jazznearyou), not event pages. Needed: page-as-list → items, each a candidate with a link to
  its own page. Scenarios 1 and 3 stand on it.
- **Every web fact carries its URL, when it was retrieved, and a ttl.** Without the ttl
  scenario 3 has no trigger.
- **The place comes from the world, and is checked against the page.** "Belgrade" returned
  Belgrade, Montana; "Berlin" a trail in Berlin, Connecticut.
- **Relevance falls off fast.** News results under score 0.5 were about other cities.

For the demo: 2 as the foundation, 1 as the showcase, one episode of 3 ("the world noticed
Vortex has a new date") and one of 6 (planning Saturday, the world mentions an event unasked,
says why, links the page). All three use one chain: search → fetch → list to items → `formalise`
→ check.
