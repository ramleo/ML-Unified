-- Security log — LOGGING_SPEC.md §5b. Run once in the Supabase SQL editor.
--
-- Purpose: answer "was anything malicious uploaded, and when" — NOT to measure
-- usage. Deliberately separate from `events`, deliberately not readable by
-- anything the site exposes.
--
-- What is stored: facts ABOUT an upload — name, type, size, and a SHA-256
-- fingerprint. NOT the upload. §10 leaves content storage undecided; nothing
-- here presumes it.

create table if not exists public.security_log (
  id          bigserial primary key,
  ts          timestamptz default now(),
  session_id  text,
  run_id      text,          -- joins to events.meta->>'run_id'
  tool        text,
  filename    text,          -- see the note below
  ext         text,
  size_bytes  bigint,
  mime        text,
  sha256      text,          -- the fingerprint; the file itself is discarded
  prompt_len  int,           -- length only
  country     text
);

create index if not exists security_log_ts_idx     on public.security_log (ts desc);
create index if not exists security_log_sha256_idx on public.security_log (sha256);
create index if not exists security_log_run_idx    on public.security_log (run_id);

-- RLS ON, and NO policies, on purpose. The anon key the browser holds can then
-- read nothing here at all, while the service-role key (which bypasses RLS)
-- still writes. §5b: "not readable by any API route the site exposes."
alter table public.security_log enable row level security;

-- ── Why the filename is here and not in `events` ─────────────────────────
-- "report.pdf" is harmless; "john-smith-payslip-march.pdf" is not — filenames
-- routinely carry a person's name and a document type. It is kept anyway
-- because a filename without its contents is a different order of exposure: a
-- payslip's NAME reveals a person, its CONTENTS reveal a salary, an employer,
-- an address and a tax number. So it lives here, under 30-day expiry and
-- restricted access, and never in the table the public dashboard reads.

-- ── 30-day retention (§5b) ───────────────────────────────────────────────
-- Long enough to investigate an incident, short enough that this is not a
-- permanent archive of other people's documents. Shorter than the 14 months
-- that analytics get, because this holds more sensitive fields.
create extension if not exists pg_cron with schema extensions;

create or replace function public.purge_old_security_log()
returns void
language sql
security definer
set search_path = public
as $$
  delete from public.security_log where ts < now() - interval '30 days';
$$;

select cron.schedule(
  'purge-security-log',
  '41 3 * * *',            -- 03:41 UTC, after the analytics purge at 03:17
  $$select public.purge_old_security_log();$$
);

-- ── Checking it ──────────────────────────────────────────────────────────
--   select jobname, schedule, active from cron.job;
--   select count(*) from security_log where ts < now() - interval '30 days';
--
-- Has this exact file been seen before? (The point of the hash.)
--   select ts, tool, filename, size_bytes from security_log
--    where sha256 = '<paste hash here>' order by ts desc;
