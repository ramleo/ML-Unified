# Logging & telemetry — one map of everything the site records

A single index of **every log the platform keeps**, what each captures, where it
lives, how long it's kept, and who can read it. The detailed specs stay authoritative
for their own area (linked per row); this is the map so you don't hunt across six
files. Accurate as of 2026-10-18.

> **Detailed specs:** `LOGGING_SPEC.md` (analytics journey + backend call log +
> security log — the source of truth), `LOGGING_COVERAGE.md` (per-tool wiring),
> `FEATURE_TRACKING_SPEC.md` (per-control usage), `ERROR_TRACKING.md` (errors +
> Sentry), `CLICK_AUDIT.md` (crash-durable clicks), `OBSERVABILITY_PLAN.md`
> (alerting). Public disclosure: `ml-portfolio/src/app/privacy/page.tsx`.

---

## The one rule that governs all of it

**Content-free.** No log ever stores document text, prompt text, typed input, or
search-query text. Logs hold types, sizes, counts, enumerated choices, hashes and
fingerprints — never the content itself. (The one nuance: the **security log** keeps
a *filename* + *SHA-256*, never the file; the password tool is excluded everywhere.)
Every logging write is fire-and-forget and must never block or break a user.

---

## The seven stores

| Store | What it records | Where (table · route · code) | Retention · access | Spec |
|---|---|---|---|---|
| **Analytics events** | the user journey — 31 content-free event types (page_view, tool_open, query_run, run_success/error, export, feedback, …) | `events` · `/api/track` · `useAnalytics.ts`, `logEvents.ts` | 14 months · public dashboard reads it (content-free) | LOGGING_SPEC §2–3 |
| **Feature usage** | which *control inside a tool* was used — one `feature_use` event + properties (tool, control), not 800 event names | `events` (same table, `feature_use` type) · `/api/track` · `feature_usage.sql` RPC for the dashboard | 14 months · same as events | FEATURE_TRACKING_SPEC |
| **Backend LLM calls** | every provider call: service, tool, provider/model, status, http_status, latency, error | `llm_calls` · `/api/llm-log` (gated by `AIRAML_LOG_TOKEN`) · `rag/llm.py` + `rag/call_log.py` | service-role only (RLS, no policies) | LOGGING_SPEC §5 |
| **Security log** | facts *about* an upload: filename, ext, size, mime, **sha256**, prompt_len, country, **salted ip_hash** | `security_log` · `/api/security-log` (write-only) · file-input listener | **30 days** · service-role only, never a GET route | LOGGING_SPEC §5b |
| **Error store** | faults: class, message, stack, route (query stripped), source, fingerprint | `errors` · `/api/error` · `useErrorTracking()` + `error_reporting.py` middleware | grouped by fingerprint · dashboard via `error_groups` RPC | ERROR_TRACKING |
| **Click audit** | every interactive click, content-free structural id + label | `click_audit` · `/api/audit` · `auditClick.ts` | durable; read path key-gated (fails closed) | CLICK_AUDIT |
| **Security events** | content-free security signals (gate blocks, rate-limit hits) | `security_log` via `log_security_event` · `/security/status` (token-gated) | polled by a GitHub Action that emails on a spike | OBSERVABILITY_PLAN |

Plus **Sentry** (optional, dormant unless `SENTRY_DSN` set) as a richer secondary
for errors — front + back, content-stripped.

---

## How the stores join up

Two keys thread a single user action across stores:

- **`session_id`** — `localStorage["_ml_session"]`, an anonymous `randomUUID()` set on
  first visit. No cookie, no account, no PII. Present on events, errors, security log,
  click audit.
- **`run_id`** — a UUID minted client-side per "run" press, sent in the request body.
  It joins the **click** (`events.meta->>'run_id'`) to the **backend call**
  (`llm_calls.run_id`) and the **security log** row for the same work.

So "what happened at 15:09 on this date for this run" is answerable by joining on
`session_id` + `run_id` — which is the whole reason the spec exists (a 429 outage once
took hours to diagnose because nothing durable tied the facts together).

---

## Retention at a glance

- **Analytics / feature usage (`events`):** 14 months (cron `purge-old-analytics`).
- **Security log:** 30 days (cron purge) — long enough to investigate, short enough
  not to hoard other people's filenames.
- **LLM calls / errors / click audit:** no fixed expiry set; small-volume.

## Dashboards

- **Real-Time Analytics** (`/tools/realtime-analytics`) — events, feature usage, and
  the errors panel (`AnalyticsErrors`), all over the content-free tables.
- **Click-audit dashboard** (`/audit/dashboard`) — aggregate clicks, key-gated.

## Setup (one-time SQL, Supabase editor)

Run each once (idempotent): `events`/retention, `llm_calls`, `security_log.sql`,
`errors.sql`, `feature_usage.sql`, `click_audit.sql`. Env: `AIRAML_LOG_TOKEN`
(llm-log + security log + IP hash salt), `SECURITY_STATUS_TOKEN` (status endpoint),
optional `SENTRY_DSN` to activate Sentry.

## The privacy obligation (don't skip)

`privacy/page.tsx` is written from what the code actually logs and is the **public**
disclosure. **Any change to what is logged is not done until the privacy page is
updated in the same change** — otherwise a true page silently becomes false. This is
the single rule that ties all the stores above to one user-facing promise.

---

## What is NOT logged (deliberately)

Document/prompt/search **content** (undecided, deferred — LOGGING_SPEC §10); raw IP
(only a coarse country code + a salted hash); anything from the **password tool**;
request bodies / cookies / DOM recordings (Sentry strips these). Storing content, if
ever done, would go to a separate HF Dataset repo with its own disclosure — not these
tables.
