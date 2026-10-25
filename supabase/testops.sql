-- TestOps — the test-case automation registry. Run once in the Supabase SQL editor.
--
-- Purpose: answer "which of the ~1,795 documented test cases actually run, and
-- what happened when they did". The TC-*.md files stay the source of truth for a
-- case's TEXT; this holds the mutable state the markdown cannot — the lane it was
-- sorted into, the URL it resolves to, the spec it produced, and every outcome.
--
-- Read only by the owner, through /api/testops. Nothing here is user content.

-- ── Current state: one row per documented case ───────────────────────────────
create table if not exists public.testops_cases (
  tc_id           text primary key,        -- e.g. TC-P12-001
  source_file     text not null,           -- TC-P12.md
  category        text,
  test_name       text,
  steps           text,
  expected        text,
  hint            text,                    -- the Automation Hint field
  source_part     text,                    -- e.g. Part250

  -- Classification. `lane` is the routing decision; `lane_origin` records WHO
  -- decided (regex / model / human) so a hand-correction is never silently
  -- overwritten by the next sync.
  lane            text,                    -- BROWSER | API | REPO | LESSON | DEAD | UNKNOWN
  ready           text,                    -- READY | SETUP | NO_URL | NO_URL_SETUP
  lane_origin     text default 'regex',    -- regex | model | human
  lane_locked     boolean default false,   -- true => sync must not change the lane

  -- Resolution and the artefact it produced.
  target_url      text,
  resolve_method  text,                    -- explicit | slug | static | space-mode | unresolved
  spec_path       text,                    -- tests/testwright-suite/<name>.spec.ts

  -- Denormalised latest outcome, so the dashboard's headline needs no join.
  last_verdict    text,                    -- PASS | HEALED | BUG | STILL_RED | AUTHOR_EMPTY | ...
  last_run_at     timestamptz,
  run_count       int default 0,
  fail_count      int default 0,

  first_seen      timestamptz default now(),
  updated_at      timestamptz default now()
);

create index if not exists testops_cases_lane_idx    on public.testops_cases (lane);
create index if not exists testops_cases_verdict_idx on public.testops_cases (last_verdict);
create index if not exists testops_cases_file_idx    on public.testops_cases (source_file);
create index if not exists testops_cases_ready_idx   on public.testops_cases (ready);

-- ── History: ONE extensible log, deliberately not four rigid tables ──────────
-- `kind` names the record type and `payload` carries whatever that kind needs.
-- Adding a new thing to record is an insert with a new `kind` — no migration, no
-- column, no deploy. The kinds in use today:
--
--   run_verdict  {verdict, provider, heals, duration_ms, correlation_id, error}
--   finding      {severity, title, detail, status, commit}
--   cost         {provider, model, tokens_in, tokens_out, usd, quota_note}
--   decision     {what, why, previous}     -- why a case was marked dead/stale
--   sync         {added, updated, removed, total}
--
-- A CHECK constraint is deliberately omitted: it would have to be altered for
-- every new kind, which is exactly the coupling this table exists to avoid.
create table if not exists public.testops_events (
  id        bigserial primary key,
  ts        timestamptz default now(),
  kind      text not null,
  tc_id     text,                          -- null for programme-wide events
  actor     text default 'system',         -- system | owner | <script name>
  payload   jsonb not null default '{}'::jsonb
);

create index if not exists testops_events_ts_idx    on public.testops_events (ts desc);
create index if not exists testops_events_kind_idx  on public.testops_events (kind, ts desc);
create index if not exists testops_events_tc_idx    on public.testops_events (tc_id, ts desc);
-- Lets a new kind be queried on its payload without adding a column or an index.
create index if not exists testops_events_payload_idx on public.testops_events using gin (payload);

-- ── Access ───────────────────────────────────────────────────────────────────
-- RLS ON with NO policies, matching security_log: the anon key the browser holds
-- reads nothing, while the service-role key used by /api/testops (behind an
-- isOwnerEmail check) bypasses RLS. The owner gate lives in the route, not here,
-- so a leaked anon key still exposes none of this.
alter table public.testops_cases  enable row level security;
alter table public.testops_events enable row level security;

-- ── A convenience view for the dashboard's headline numbers ──────────────────
create or replace view public.testops_coverage as
select
  lane,
  count(*)                                             as total,
  count(*) filter (where spec_path is not null)        as automated,
  count(*) filter (where last_verdict = 'PASS')        as passing,
  count(*) filter (where last_verdict = 'HEALED')      as healed,
  count(*) filter (where last_verdict = 'BUG')         as bugs,
  count(*) filter (where target_url is not null)       as resolved,
  count(*) filter (where last_run_at is null)          as never_run
from public.testops_cases
group by lane;
