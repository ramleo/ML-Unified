Chapter 19Real-Time Analytics


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
  red <70%.
- AI Provider Usage: share of queries served by each provider, plus a by-model
  breakdown (e.g. llama-3.3-70b, gemini-2.0-flash) — useful to see which models
  carry the load.
- Engagement metrics, Top Pages, Top Referrers (grouped by hostname + path,
  UTM parameters stripped), Events by Type, and a Visitors-by-Device donut
  (desktop / mobile / tablet).

### Notes
- Sparkline buckets by UTC hour for single-day views and by calendar date for
  multi-day views.
- Panels hide themselves automatically when there is no matching data in the
  selected range.
- The full visible User Guide is available on the page itself.

## What problem it solves

Every other tool in this book does something to data you give it. This one
watches the site itself.

The question it answers is not analytical, it is architectural: **how do you get
an event from a visitor's browser onto a dashboard, live, without polling?**
Nearly every analytics page in the world answers that with a timer — ask the
server every five seconds whether anything happened. That works, and it is
wasteful in a specific way: almost every request returns "nothing new", and the
data you are looking at is on average two and a half seconds stale.

This dashboard has no timer. A row is inserted into PostgreSQL and the database
pushes it to the open browser. The number on screen changes because something
happened, not because a clock ticked.

## How it works, step by step

**The write path — three hops:**

1. A visitor opens a page or a tool. The browser posts a small JSON object to
   `/api/track`.
2. That route runs on the server, adds the visitor's country from the CDN's own
   header, and inserts a row into the `events` table in Supabase PostgreSQL.
3. PostgreSQL's replication stream notices the insert.

**The read path — no request at all:**

4. The dashboard, on load, opens a **WebSocket** to Supabase Realtime and
   subscribes to `INSERT` on `public.events`.
5. When a row lands, the database pushes it down that socket.
6. The browser prepends it to the live feed and **updates every statistic
   locally** without asking the server for anything.

## The model or algorithm

No model. The interesting parts are the transport and one piece of client-side
state management.

### Why this is not polling

Polling means the client asks repeatedly. It is simple, it works everywhere, and
it has two costs: a request per interval per open tab whether or not anything
happened, and latency equal to half the interval on average.

What replaces it here is **PostgreSQL's logical replication**. Postgres already
writes every change to a write-ahead log so it can recover from a crash and feed
replicas. Logical decoding turns that log into a stream of readable change
events. Supabase Realtime reads that stream, matches each change against what
open clients have subscribed to, and pushes matching rows down their WebSockets.

The consequence worth stating: **the dashboard is driven by the database's own
durability mechanism.** The event reaches the browser because it was committed,
not because anything polled for it. Nothing extra is written to make it work.

### The tracking endpoint runs server-side, for one specific reason

The insert cannot happen from the browser, because the write needs the Supabase
**service-role key** — a credential that bypasses row-level security. Shipping
that to the client would let anyone write anything into the table.

So `/api/track` is a server route. The browser posts to it with no credential at
all; the route holds the key in a server-only environment variable and does the
insert.

Note the asymmetry, because it is the whole security design:

| Direction | Credential | Why it is safe |
|---|---|---|
| **Write** | service-role key, server-only | never leaves the server |
| **Read** | anon key, in the browser | read-only, and the table is public data |

Two keys with two power levels, and the powerful one never crosses the network
to a client.

**The country comes from a header, not from the client.** `CF-IPCountry` or
`x-vercel-ip-country`, set by the CDN. A browser-supplied country would be a
value the visitor controls; an edge-supplied one is not.

The endpoint also sets permissive CORS headers, with an `OPTIONS` handler, so
events can be posted from the other deployed apps in this project rather than
only from this site.

### The optimistic dashboard update

This is the part with the most engineering in it, and it is easy to miss.

When a new event arrives, the dashboard does **not** re-fetch its statistics. It
recomputes them in the browser from the single row that just arrived:

- `today_count` increments
- the current hour's bucket in `per_minute` increments, or is created
- the event's path is found in `top_pages` and incremented, or appended — then
  the list is re-sorted and re-trimmed to ten
- `by_type` is updated the same way
- the funnel counter for `page_view`, `tool_open` or `query_run` steps up
- the feed keeps the newest **50** events, the chart the last **30** buckets

Every one of those is an immutable update — a new array, a new object — because
React needs a changed reference to re-render.

There is also a guard that is the sort of thing that only shows up in use:

```ts
if (range !== "today") return;
```

If you are looking at last week, a live event still joins the feed but **must
not** be added to the statistics, because it is not inside the range those
statistics describe. Without that line, browsing a historical range would slowly
corrupt its own totals with today's traffic. Live updates have to respect the
filter the user is looking through.

### The funnel

Three event types in a deliberate order: `page_view` → `tool_open` →
`query_run`. That is the drop-off worth measuring on this site — how many
visitors arrive, how many open a tool, how many actually run something. Each
step is a much stronger signal of interest than the one before it.

## Why these choices

**Why a WebSocket rather than polling.** Zero requests when nothing happens,
and no staleness when something does. On a low-traffic site the difference in
load is the whole point: polling costs the same whether traffic is zero or
constant.

**Why update statistics client-side instead of re-fetching.** A re-fetch per
event turns a push architecture back into a request-per-event one, which is
worse than polling under load. The dashboard already holds the aggregate; the
new row is a delta.

**Why Supabase rather than a self-managed Postgres.** Realtime, the WebSocket
infrastructure, connection pooling and row-level security come as one managed
piece. Building the same thing means running a logical-replication consumer and
a WebSocket fan-out service — considerably more moving parts than this site
justifies.

**Why store `meta` as JSON.** Different event types carry different payloads —
which tool, which model won, how many rows. A schema per type would need a
migration each time a tool is added. A JSON column takes whatever a tool sends.
The trade is that nothing validates its shape.

## How to read the output

- **The live feed is the newest 50 events.** It is a window, not a log.
- **The funnel is the metric that means something.** Page views measure reach;
  `query_run` measures whether anyone actually used the thing.
- **Counts update optimistically.** What you see is the dashboard's arithmetic
  on the events it has received since load, added to the totals it fetched at
  load. Refreshing re-reads from the database.
- **Country comes from the CDN's geo-IP header**, so a VPN reads as its exit
  country and a missing header reads as blank.
- **Nothing arriving is a real observation.** A quiet feed means a quiet site,
  not a broken socket — the connection state is separate.
- **Switch ranges and the statistics stop moving.** That is the range guard,
  not a stall.

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
