# Logging Specification

**Status:** agreed 2026-09-05. **Partially implemented 2026-09-06** — §9 items
1, 4 and 9 built, plus the `trackedFetch` funnel items 2 and 3 need. One tool
migrated; 55 not. See §11.
**Owner:** this file is the single source of truth for what the site logs.
Change the logging, change this file, and change the privacy page (see §7).

---

## 1. Why this exists

On 2026-09-05 the Contract/Invoice Reconciliation tool failed all day. Every
LLM call returned HTTP 429. Diagnosing it took hours, and the reason it took
hours is that **nothing was written down anywhere durable**:

- Hugging Face Space logs are a live buffer. Every file upload and every
  secret change restarts the Space and clears the history.
- The Space's disk is ephemeral, so writing log files there does not survive.
- There was no way to ask "what happened at 15:09 on 5 September".

The answer, when it finally arrived, was a two-line story: the Gemini key was
rotated at ~14:50, and the first successful call was at 15:09:11. Both facts
existed. Neither was recorded in a place they could be read together.

The goal of this spec is that a question of the form *"what happened at
&lt;time&gt; on &lt;date&gt;"* is always answerable by one query.

---

## 2. What already exists

| Piece | Where | Notes |
|---|---|---|
| `track(type, extra)` | `ml-portfolio/src/hooks/useAnalytics.ts` | Fire-and-forget POST, failures swallowed |
| `useAnalytics(type)` | same file | Fires once on mount — used for `page_view` |
| `useToolTracking(tool)` | same file | Fires `tool_open` on mount, `tool_close` on unmount with duration |
| `POST /api/track` | `ml-portfolio/src/app/api/track/route.ts` | Writes to Supabase with the service-role key |
| Supabase `events` table | Supabase project | Columns below |
| Analytics dashboard | `/tools/realtime-analytics` | Reads the same table live over a WebSocket |

**`events` columns today:** `type`, `path`, `session_id`, `country`
(server-derived from the CF/Vercel header), `referrer`, `duration_ms`,
`meta` (jsonb), plus `created_at`.

**Session identity:** `localStorage["_ml_session"]`, a `crypto.randomUUID()`
created on first visit. No cookie, no account, no PII.

**Coverage as of 2026-09-05:** 51 of 52 tool pages call something, and
`page_view` fires from 61 files — but only **five event types are ever
emitted**: `page_view`, `tool_open`, `tool_close`, `query_run`, `error`.
And `error` has exactly one call site in the entire codebase.

So the infrastructure is sound and the vocabulary is nearly empty. This spec
fills the vocabulary; it does not rebuild the plumbing.

---

## 3. The journey, stage by stage

Each stage lists what a visitor actually does, the event to emit, and the
`meta` fields that make the row worth having. **Bold** = not implemented yet.

### Stage 1 — Arrival

The visitor lands, from a search engine, a link, or directly.

| Action | Event | meta |
|---|---|---|
| Loads any page | `page_view` ✅ exists | `device`, `returning`, plus **`utm_source`, `utm_medium`, `utm_campaign`, `lang`, `viewport`** |
| First page of the session | **`session_start`** | `landing_path`, `referrer_host`, `device`, `lang` |

*Why `session_start` separately:* today "first visit" is inferred from a
`_ml_pv_count` counter in localStorage. An explicit row is queryable.

### Stage 2 — Exploring

They scan the site and look for something.

| Action | Event | meta |
|---|---|---|
| Types in the live search | **`search`** | `query_len`, `result_count`, `zero_results` (bool) |
| Clicks a search result | **`search_result_click`** | `position`, `tool` |
| Clicks a nav item | **`nav_click`** | `target`, `from_path` |
| Clicks a tool card | **`tool_card_click`** | `tool`, `source` (home / category / search) |
| Scrolls a long page | **`scroll_depth`** | `percent` (25/50/75/100), fired once per threshold |

*Highest-value row on this page:* `search` with `zero_results: true`. It is
the only record of what someone came for and did not find. Log the query
**length**, not the text — see §6.

### Stage 3 — Learning

Before using a tool, some visitors read or watch first.

| Action | Event | meta |
|---|---|---|
| Opens the User Guide modal | **`guide_open`** | `tool`, `section` |
| Starts a walkthrough | **`demo_start`** | `tool`, `mode` (live / recorded) |
| Finishes it | **`demo_complete`** | `tool`, `mode`, `duration_ms` |
| Abandons it | **`demo_abandon`** | `tool`, `mode`, `step_index`, `step_total` |

*Why this matters:* 19 walkthrough clips were re-recorded on 2026-09-05 and
there is currently no way to know whether a single person watches one, or
where they give up.

### Stage 4 — Setting up

Feeding the tool its input.

| Action | Event | meta |
|---|---|---|
| Uploads a file | **`upload`** | `ext`, `size_bytes`, `rows` / `pages` / `chunks`. The filename and SHA-256 go to the security log (§5b), not here |
| Loads bundled sample data | **`sample_load`** | `tool`, `sample` |
| Changes a setting | **`config_change`** | `field`, `to` (only for enumerated values, never free text) |
| Pastes text into a box | **`paste_input`** | `chars` |

### Stage 5 — Running

| Action | Event | meta |
|---|---|---|
| Presses the run button | `query_run` ✅ exists | add **`tool`, `run_id`** |
| It succeeds | **`run_success`** | `run_id`, `latency_ms`, `provider`, `model` |
| It fails | **`run_error`** | `run_id`, `latency_ms`, `stage`, `error_class`, `http_status` |
| They press it again after a failure | **`run_retry`** | `run_id`, `attempt` |

`run_id` is a UUID minted client-side per press. It is what joins the click
to the backend's own record of the same work (§5).

### Stage 6 — Results

| Action | Event | meta |
|---|---|---|
| Results render | **`result_view`** | `tool`, `result_count` |
| Expands a row / opens a citation | **`result_expand`**, **`citation_click`** | `index`, `kind` |
| Exports | **`export`** | `format` (csv / json / png / pdf) |
| Copies output | **`copy`** | `what`, `chars` |
| Downloads a produced file | **`download`** | `ext`, `size_bytes` |

### Stage 7 — Failure

`error` exists but has one call site, so in practice failures are invisible.
Every catch block that a user can see the effect of should emit:

| Field | Meaning |
|---|---|
| `stage` | upload / config / run / render |
| `error_class` | `rate_limited`, `timeout`, `bad_input`, `backend_5xx`, `network`, `unknown` |
| `http_status` | when there is one |
| `tool`, `run_id` | to join it to the attempt |

**`rate_limited` is its own class deliberately** — it is exactly what went
unnoticed for a day, and it must be one query away.

### Stage 8 — Leaving

| Action | Event | meta |
|---|---|---|
| Leaves a tool | `tool_close` ✅ exists | already carries `duration_ms`, `queries_run` |
| Leaves the site | **`session_end`** | `duration_ms`, `pages`, `tools_used`, `runs` — best-effort on `visibilitychange` |

---

## 4. Vocabulary rule

All event names live in **one file**, exported as constants, and nothing
calls `track()` with a string literal. Without this, `run_error` becomes
`runError` in the third place someone adds it and the dashboard quietly
under-counts. One file, one spelling, no exceptions.

Proposed: `ml-portfolio/src/lib/logEvents.ts`.

---

## 5. Backend call log

Separate from the user journey, and joined to it.

**Table:** `llm_calls` in the same Supabase project.

| Column | Notes |
|---|---|
| `ts` | |
| `service` | ml-api / ml-vision / ml-eda |
| `tool` | which feature made the call |
| `provider`, `model` | mistral, gemini, … |
| `status` | ok / error |
| `http_status` | 200, 429, … |
| `error_code`, `error_message` | the provider's own, truncated |
| `latency_ms` | |
| `session_id`, `run_id` | joins to the `events` table |

**Built 2026-09-06.** Table created with RLS enabled and no policies, so the
public anon key cannot read it while the service-role key (which bypasses RLS)
still writes. The shared secret is **`AIRAML_LOG_TOKEN`**, set both as a Space
secret and as a Vercel environment variable.

**How the Space writes it:** the Space posts to a new authenticated route on
Vercel, which writes to Supabase. **Not** by putting a Supabase service-role
key on the Space — the Space's logs were found leaking a Gemini key on
2026-09-05 (fixed in `e5f47e7`), and a database key is a far worse thing to
leak. The shared-secret header pattern already used by
`services/ml-api/routers/security_status.py` (`SECURITY_STATUS_TOKEN`) is the
precedent to copy.

**Where the call goes:** inside `routers/rag/llm.py`, in `complete()` and the
`stream_*` functions — the single funnel every provider call passes through.
Not at the twelve individual Gemini call sites, which is how half of them end
up uninstrumented.

---

## 5b. Security log

Separate from analytics, and deliberately restricted. Its purpose is to
answer *"was anything malicious uploaded or written, and when"* — not to
measure usage.

**Table:** `security_log`. **Not** readable by any API route the site
exposes; service-role access only, so the public dashboard cannot reach it.

| Column | Notes |
|---|---|
| `ts` | |
| `session_id`, `run_id` | joins to `events` |
| `tool` | |
| `filename` | stored — see the note below |
| `ext`, `size_bytes`, `mime` | |
| `sha256` | the fingerprint; see below |
| `prompt_len` | length only, for now |
| `country` | from the platform header, as with `events` |

**Retention: 30 days, then deleted.** Long enough to investigate an incident,
short enough that this is not a permanent archive of other people's
documents.

**Why the hash earns its place.** The file is deleted; the fingerprint is
not. Two uploads of the same file produce the same hash, so a repeat can be
spotted without either copy having been kept. If a malicious sample turns up
later, hashing it and searching this table says exactly when and how often it
came through. It can also be checked against public malware databases without
the file ever having been stored.

**Filenames are stored (decided 2026-09-05).** `report.pdf` is harmless;
`john-smith-payslip-march.pdf` is not, and filenames often carry a name and a
document type. The reasoning for storing them anyway: a filename without its
contents is a different order of exposure from the contents themselves — a
payslip's filename reveals a name, its contents reveal a salary, an employer,
an address and a tax number. That is why filenames live here under the 30-day
expiry and restricted access, and never in `events`.

**Content is NOT stored** — see §10, this is undecided. Today the security
log records facts *about* an upload, not the upload.

**The password tool is excluded from this log entirely.** Its whole promise
is that the password never leaves the browser, and that promise is currently
true. No hash, no length, no row.

---

## 6. Rules

1. **No content in the analytics table.** `events` holds types, sizes,
   counts and enumerated choices only — never document text, prompt text or
   search query text. A contract uploaded to the reconciliation tool must
   never reach the table the public dashboard reads from.
   Filenames and hashes are recorded, but in the restricted security log
   (§5b), never in `events`.
2. **Never block the user.** Fire and forget; swallow every failure. A
   logging outage must be invisible to a visitor.
3. **One vocabulary file** (§4).
4. **`session_id` is anonymous** and stays that way: a random UUID in
   localStorage, no account, no cookie, no IP stored beyond the
   country code the platform header already provides.
5. **Truncate everything free-form.** Error messages to 400 characters.

---

## 7. Privacy page obligation — read before implementing

`ml-portfolio/src/app/privacy/page.tsx` says of itself:

> *Written from what the code actually does, not from a template. Every claim
> below was checked against the source before being written down… the
> analytics columns are the exact insert in `src/app/api/track/route.ts`… If
> any of those change, this page is wrong and needs updating with them.*

So **expanding what is logged is not complete until the privacy page is
updated in the same change.** The page's honesty is a property someone
deliberately built; shipping new event types without touching it silently
turns a true page into a false one.

---

## 8. Retention

Supabase free tier is 500 MB. At the expected volume this is not a
constraint for a long time, but the decision should be made rather than
drifted into. **Decided 2026-09-06: 14 months.** GA4 offers 2 / 14 / 26 and defaults to 26;
most privacy guidance recommends 14. Long enough for year-on-year comparison,
short enough not to hoard.

**Live since 2026-09-06.** `supabase/retention.sql` was run; `cron.job` shows
`purge-old-analytics`, `17 3 * * *`, active. Nothing is actually deleted until
November 2027 — the oldest row is from the day this was built.

---

## 9. Implementation order

Nothing here is built yet. Suggested order, cheapest and highest-value
first:

1. `logEvents.ts` vocabulary file (§4).
2. Stage 7 — error logging with `error_class`. Smallest change, and the one
   that would have saved 2026-09-05.
3. Stage 5 — run outcome with `run_id` and latency.
4. `llm_calls` table and the Space→Vercel route (§5).
5. Stage 2 — search, especially zero-result searches.
6. Stage 4, 6 — upload / export / copy.
7. Stage 3 — demo engagement.
8. Stage 1, 8 — session boundaries.
9. Privacy page update (§7) — **must ship with whichever of the above lands
   first**, not at the end.

---
## 10. Open questions

### Storing content itself — UNDECIDED

The case for: knowing *what* was uploaded or prompted is the only way to
review a prompt-injection attempt or read a malicious document after the
fact. Major platforms do retain content for abuse monitoring — OpenAI keeps
API inputs 30 days for exactly this — and they disclose it.

The case against, and what it would cost:

1. **It inverts the privacy page's central claim.** The page currently says
   uploads are *"discarded when the response is returned — it is never
   written to disk."* Supabase is disk, and unlike the Space's scratchpad it
   is not wiped on restart. That sentence would have to be rewritten, not
   amended.
2. **Some tools handle secrets.** Password Strength (real passwords), Email
   Header Auth (real headers and addresses), Phishing Classifier (real
   correspondence), Reconciliation (real contracts). The password tool is
   already excluded from §5b for this reason.
3. **Storage.** Document text will outgrow the Supabase free tier far faster
   than event rows will. If content is ever stored it belongs somewhere built
   for bulk — a Hugging Face Dataset repo is free and the account already
   exists.
4. **Most of the security signal does not need it.** Hash, type, size and a
   YARA verdict answer "was this malicious" — and this project already ships
   a YARA scanner. Full content mainly buys prompt-injection review, which is
   real but narrower than it first appears.

**Nothing is lost by deferring.** The `sha256` recorded from day one means a
later capture can still be matched to an earlier event.

Agreed wording if content is ever stored:

> Uploads are deleted after use, except in a 30-day security log used to
> investigate abuse.

### Smaller ones

- ~~**Retention**~~ — 14 months (§8), scheduled and active since 2026-09-06.
- ~~**Search queries**~~ — decided 2026-09-06: a **salted** hash, not the text
  and not only the length. Length alone is unactionable; a hash counts repeat
  zero-result searches. Salted because an unsalted hash of a short query is
  recoverable by hashing a dictionary. Not yet built — item 5.
- **`session_end`** — worth the unreliability of `visibilitychange`?
- **Free tier only.** The owner's constraint is that everything stays on free
  tiers. Supabase's database allowance is small; verify the current figure on
  the dashboard before committing to content storage of any kind.

---
## 11. What is built (2026-09-06)

| Piece | File | State |
|---|---|---|
| §4 vocabulary | `ml-portfolio/src/lib/logEvents.ts` | Done — 28 event names, 6 error classes, 4 stages, `classifyStatus`/`classifyThrown` |
| Frontend funnel | `ml-portfolio/src/lib/trackedFetch.ts` | Done — emits `run_success`/`run_error` for any caller that uses it |
| §5 sink route | `ml-portfolio/src/app/api/llm-log/route.ts` | Gated on `AIRAML_LOG_TOKEN`, 404s if unset |
| §5 Space side | `services/ml-api/routers/rag/call_log.py` | ContextVar + fire-and-forget poster |
| §5 instrumentation | `services/ml-api/routers/rag/llm.py` | Done — all four `stream_*` wrapped |
| §7 privacy page | `ml-portfolio/src/app/privacy/page.tsx` | Done, same change per §7 |
| Stage 5/7 in a tool | `ReconciliationReport.tsx` | ONE tool only |

**Why `llm.py` was wrapped, not edited per call site:** the four `stream_*`
functions were renamed `_stream_*_raw` and re-exposed under their original
names wrapped in `instrument()` — §5's own argument, applied to itself.

**The join key:** `run_id` is minted client-side per press, sent in the
request body, and put on a ContextVar so every judge call carries it.
`events.meta->>'run_id'` joins to `llm_calls.run_id`.

**Not built:** 55 of 56 tools still call `fetch` directly (81 sites); stages
1, 2, 3, 4, 6, 8 emit nothing; `security_log` (§5b) has no table; the
retention cron is decided but unscheduled; no route but reconciliation
accepts a `run_id`.
