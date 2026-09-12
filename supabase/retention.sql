-- 14-month analytics retention — LOGGING_SPEC.md §8, decided 2026-09-06.
--
-- Run once in the Supabase SQL editor. Deleting old rows is NOT automatic:
-- until something like this is scheduled, "14-month retention" is a stated
-- intention rather than a fact, and the privacy page would be claiming
-- something the database does not do.
--
-- Why 14 months: GA4 offers 2 / 14 / 26 and defaults to 26; most privacy
-- guidance recommends 14. Long enough to compare this September against last
-- September, short enough not to hoard data nobody will look at.

-- 1. The scheduler. Supabase ships pg_cron; it lives in the `extensions`
--    schema rather than public.
create extension if not exists pg_cron with schema extensions;

-- 2. The purge itself, as a function so the schedule stays a one-liner and
--    the logic can be changed without touching the schedule.
--
--    security definer so the cron job (which runs as the postgres role) is
--    not dependent on RLS; search_path is pinned because a security definer
--    function without one is a privilege-escalation footgun.
create or replace function public.purge_old_analytics()
returns void
language sql
security definer
set search_path = public
as $$
  delete from public.events    where created_at < now() - interval '14 months';
  delete from public.llm_calls where ts         < now() - interval '14 months';
$$;

-- 3. Daily at 03:17 UTC. Deliberately not on the hour — every scheduled job
--    in the world runs at :00, and there is no reason to join the queue.
select cron.schedule(
  'purge-old-analytics',
  '17 3 * * *',
  $$select public.purge_old_analytics();$$
);

-- ── Checking it ──────────────────────────────────────────────────────────
-- Is it scheduled?
--   select jobid, jobname, schedule, active from cron.job;
--
-- Did it run, and did it succeed?
--   select * from cron.job_run_details order by start_time desc limit 10;
--
-- How much would it delete right now? (Safe — counts, deletes nothing.)
--   select count(*) from events    where created_at < now() - interval '14 months';
--   select count(*) from llm_calls where ts         < now() - interval '14 months';
--
-- Remove the schedule:
--   select cron.unschedule('purge-old-analytics');

-- ── If pg_cron is unavailable on this plan ───────────────────────────────
-- The fallback is a Vercel cron hitting an authenticated route that calls
-- purge_old_analytics(). Steps 1 and 3 above are then skipped and step 2 is
-- still needed. Vercel's Hobby plan allows one cron run per day, which is
-- exactly the cadence this wants.
