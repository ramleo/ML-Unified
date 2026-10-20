Chapter 18Real-Time Analytics


> Watch traffic to this site arrive as it happens. Page views and tool opens flow from the browser into PostgreSQL through a FastAPI ingestion endpoint, and Supabase Realtime pushes each new row straight to the dashboard — no polling, no refresh button.

## At a glance

| | |
|---|---|
| **Also called** | Live Event Dashboard |
| **Model or method** | Supabase Realtime · asyncpg |
| **What you give it** | Browser events (page views, tool opens) |
| **Live Events** | ∞ |
| **Where it runs** | On the server |
| **Find it at** | `/tools/realtime-analytics` |

## Using the tool

### What this tool does
A live analytics dashboard for the AIRaML portfolio: page views, tool usage,
query success rates, AI provider usage, geography, devices, and engagement —
all filterable by date range.

### Range selector
- Presets: Today / Yesterday / 7 days / 30 days — click a pill to reload every
  panel for that window.
- Custom calendar: click one date for a single day (hourly view) or a start and
  end date for a multi-day range (daily view). Future dates are disabled.
- Export CSV: downloads all events for the active range (up to 5,000 rows) with
  id, timestamp, type, path, session, country, duration, and metadata.

### Panels
- Stat cards: headline totals for the selected range.
- Events sparkline: area chart of event volume over time; hover for exact
  counts. A green "Peak hour" badge shows the busiest hour of the trailing
  7 days, independent of the selected range.
- Conversion funnel: step-by-step visitor progression.
- Visitors by Country: world dot map — circle size scales with event count;
  hover a circle for the exact number.
- Activity heatmap: 7×24 grid (day of week × UTC hour) for the last 7 days;
  darker cells = more events.
- HF Space Tools: tool-open activity tracked from the ML Unified backend, with
  per-tool page/copy/open counts.
- Portfolio Tools: tool-open events from the portfolio site itself (AutoML,
  Text-to-SQL, Document Intelligence, SHAP, Drift, and the rest).
- Tool Usage Comparison: proportional bars for the top /tools/* pages (up to 6).
- Query Success by Tool: per-tool SQL success rate — green ≥90%, amber 70–89%,
  red 

## Limits

- **Session identity is a client-generated id.** Cleared site data is a new
  visitor; two browsers are two visitors.
- **No bot filtering.** Crawlers count as page views.
- **The `meta` column is unvalidated.** Whatever a tool sent is what is stored.
- **Optimistic updates can drift** from the database — a dropped WebSocket
  message is not reconciled until reload.
- **`/api/track` has no authentication or rate limiting.** Anyone who finds the
  endpoint can post events; the write is confined to one table with a fixed
  shape, but the numbers are not tamper-proof.
- **The service-role key bypasses row-level security**, so the route's
  validation is the only thing standing between a request and the table.
- **Only three event types** feed the funnel.
- **Realtime is per-table `INSERT`.** No aggregation server-side; the browser
  does the arithmetic.
- **This is product analytics, not a data warehouse.** No sessionisation, no
  retention cohorts, no attribution.

## Likely interview questions

**"How does the dashboard update without polling?"**
Postgres already writes every change to its write-ahead log for durability.
Logical decoding turns that log into a stream of change events; Supabase
Realtime reads the stream and pushes matching rows to clients over WebSockets
based on what they subscribed to. So the dashboard is driven by the database's
own durability mechanism — the row reaches the browser because it was committed,
not because anything asked.

**"Why can't the browser insert directly into the database?"**
Because the insert needs the service-role key, which bypasses row-level
security. Any credential in client JavaScript is public. So the write goes
through a server route that holds the key in a server-only environment variable,
and the browser reads with the anon key, which is read-only. Two credentials
with two power levels, and the powerful one never reaches a client.

**"Why recompute the statistics in the browser instead of re-fetching?"**
A re-fetch per event turns a push architecture back into request-per-event,
which is worse than polling once traffic picks up. The client already holds the
aggregate and the new row is a delta, so incrementing is both correct and free.
The cost is that the client's numbers can drift from the database if a message
is dropped, and a reload reconciles it.

**"What's the subtle bug in live-updating a filtered dashboard?"**
Applying a live event to statistics for a range it does not belong to. If
someone is looking at last week and today's events keep incrementing those
totals, the view quietly becomes wrong. There is an explicit guard — the event
still joins the feed, but the statistics only update when the selected range is
today. Any live view over a filtered dataset has this problem.

**"What would you fix first?"**
The tracking endpoint. It is unauthenticated and unrate-limited, so the numbers
are not tamper-proof — I would add rate limiting by IP and a shared secret or
signed payload from the known callers. After that, bot filtering, because
crawler traffic inflates page views without touching the funnel and makes the
conversion rate look worse than it is.

## The observability layer

The dashboard above answers *what are visitors doing*. A healthy system needs a
second question answered too: *when something breaks, can we follow it* — from
the click in the browser, through the Next.js API route, into the Hugging Face
Space, down to the model provider, as one linked story. That is observability,
and it was built on the same free stack (Sentry's free tier plus Supabase), kept
**content-free**, and shaped to the OpenTelemetry GenAI conventions so the keys
stay portable if the backend ever moves.

### One trace id, four tiers

The spine is a single id. Every user action already mints a run id in the
browser; that id now rides an `x-trace-id` header on every call. A middleware on
the Space reads it (or mints one for a direct call), holds it in a context
variable for the life of the request, and stamps it on anything that gets
logged — a 500's error row, the request log, a Sentry tag. The Next.js routes do
the same on their side. So four rows written by four services for one click all
carry the same id, and a backend failure can be pivoted straight back to the
frontend action that caused it. None of this needed a new vendor; it is plumbing
on logging that already existed.

### Content-free error tracking

Errors land in two places. The primary is a first-party store — a Supabase
`errors` table fed by an `/api/error` route, grouped by fingerprint into the
dashboard's Errors panel. Alongside it, Sentry captures the same failures on both
ends. Both are **content-free by construction**: no request bodies, messages and
stacks truncated, a scrubber strips anything PII-shaped before an event leaves.
The rule is you log what went *wrong*, never what the user typed — which is also
why there is no session replay.

One lesson is baked into that store now: when a provider returns a 4xx, the
generic `"Client error 422 for url"` is useless on its own, and the body that
names the real reason used to vanish into the Space's ephemeral log. The error
recorder now folds the provider's response body into the stored message, so the
next such failure explains itself instead of being a mystery.

### Per-call LLM telemetry

Every model call made with a server key writes one row — provider, model, input
and output tokens, an estimated dollar cost, latency, and outcome — joined to the
same trace id. Tokens are read from each provider's own usage report with no
change to the request shape; free-tier providers resolve to a known `$0` rather
than a guess. The cost figures drive the provider panel, so you can see which
model is carrying the load and what it is costing.

This panel also taught the sharpest lesson in the layer. Its rows were silently
missing for days because two queries filtered the table on a column named
`created_at` — but this table's timestamp column is `ts`. Postgres answered with
an *undefined column* error, which the frontend's "is the schema set up?" guard
was broad enough to mistake for a missing table, so the panel showed "run the
migration" while hundreds of real rows sat right there. A check that silently
*passes* on a typo is as dangerous as one that cannot fail; the fix was to verify
a "needs setup" against the live schema before trusting it.

### SLOs that measure user-facing success

Counts tell you how much happened, not whether it was good enough. Four service
level objectives — LLM success rate, LLM p95 latency, backend 5xx count, frontend
error count — are computed by one endpoint and shown as a scorecard tile, and a
scheduled job polls that endpoint every half hour and emails if any objective is
breached. The honest scope is stated in the code: this is fast-burn alerting on a
single window, not the multi-window burn-rate math a dedicated SRE stack would
run.

The objective that mattered most was almost wrong. The first reading put LLM
success at 79.9% — a breach. Breaking the failures down showed almost all of them
were free-tier rate-limit 429s that the provider cascade *recovers from*: the
visitor still gets an answer. Counting those as failures measures provider
contention, not the user's experience. Excluding recovered throttles moved the
number to a truthful 99.0%, and the throttle count is surfaced separately rather
than hidden. An SLO has to measure the right thing before its threshold means
anything.

### Per-page logs, and where the time went

Two drill-ins close the loop. A Page Inspector reads the individual error
occurrences for any one page — the in-app equivalent of tailing a log, scoped to
a route and joined by trace id to the raw request logs in Vercel and on the
Space. Its coverage is the whole site, not a handful of instrumented tools,
because a global handler in the root layout reports any uncaught error on any
page along with the route it happened on.

And for the one genuinely multi-step flow — the agentic RAG graph — each node now
reports how long it took. The router, retriever, grader, any rewrite loop, the
web fallback and the generation stream each emit a duration, surfaced as a
per-node breakdown under the Agent Graph. The value is immediate: a slow answer
stops being "the agent was slow" and becomes "retrieval took five seconds and
everything else was noise."

What none of it can do is show you what it never recorded. Telemetry only lights
the parts that are instrumented, the content-free posture means a stored error
carries no payload to reproduce from, and the free tiers keep only weeks of
history — durable analysis still means rolling up summary rows, exactly as the
dashboard above already does.

**"How do you follow one user action across four services?"**
A single trace id. The browser mints one per action and sends it as a header;
every tier reads it, holds it in request-scoped state, and stamps it on whatever
it logs — the error row, the request log, a Sentry tag, the LLM-call row. So four
rows written by four services share one id, and a backend 500 can be pivoted
straight back to the frontend click. The correlation is the product; the separate
logs were already there.

**"Your success SLO read 79.9% and alerted. Was the system actually broken?"**
No — and that is the point of the story. Almost every failure in the denominator
was a free-tier rate-limit 429 that the provider cascade recovers from, so the
visitor still got an answer. The SLO was measuring provider contention, not
user-facing success. Excluding recovered throttles from the denominator moved it
to a truthful 99.0%, with the throttle count surfaced separately. An objective has
to measure the right thing before its threshold is worth alerting on.
