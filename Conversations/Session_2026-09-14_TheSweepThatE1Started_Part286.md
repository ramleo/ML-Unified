# Part 286 — The sweep that E1 started

Continues [Part 285](Session_2026-09-14_TheKeyInTheBaseUrl_Part285.md).

Same day. Part 285 closed E1 (the Vercel rate limit) and, while scoping it,
found E9 — a server key sent to a caller's URL. This session is what that one
finding turned into: a full read of both backends and the portfolio's API
routes, which found nine more holes. Every one was fixed and deployed the same
day. The rows E10–E20 in `OPEN_ISSUES.md` carry the per-issue detail; this log
is the shape of the sweep, the two findings that mattered most, and the
mistakes worth not repeating.

The rule underneath the whole day: **scoping a task is reading, and reading is
where the holes were.** The rate limit (E1) would have slowed every one of
these; not one of them needed more than a single request.

---

## The two that mattered

### E18 — an uploaded file was code execution on the Space

`/shap/custom/upload` (SHAP for your own model) did `joblib.load` on the
uploaded file. joblib is pickle underneath, and a pickle runs arbitrary code
the instant it loads. So one `curl` of a crafted file ran any command on the
ml-api Space — every API key and the HF write token in its environment. It was
reachable: the origin check does not stop a no-Origin `curl`. Public since the
repo went public the day before.

Proven locally before touching anything: a file whose `__reduce__` returns
`(os.system, ("…",))`, loaded the exact way the route loads it, ran a command
(harmless — it wrote a marker, then deleted). This is the "build a test the
tool can fail" habit paying off: the disagreement was real code execution, not
a theory.

The fix is a format change, not a filter. Pickle cannot be made safe by
inspection, so the route now accepts only **skops** files
(`routers/core/skops_safe.py`), and only when every type inside sits under an
ML-library allowlist (sklearn/numpy/scipy/xgboost/lightgbm) — a file naming
`posix.system` or `builtins.eval` is refused before any object is built. The
`export_model` route emits `.skops` too, so the train→export→re-upload
round-trip stays whole. Proven both ways: a genuine skops model loads and
predicts identically; a joblib `.pkl`, the evil pickle (no code ran) and a
skops file naming an unknown type are all refused. Verified again live after
the rebuild.

Two loose ends left on purpose: `Step4Results.tsx` (410 lines) still labels the
button "Download .pkl", and the legacy `frontend/index.html` (5016) still
uploads `.pkl`. Both are over the 400-line gate, so they need a split first —
the endpoint rejects `.pkl` safely in the meantime.

### E10 — a CSV upload could read the Space's own key file

Found first, in the same read that E1 needed. ml-sql opens an uploaded
CSV/Parquet in DuckDB, and `/sql/page` and `/sql/filter` run caller SQL that
`validate_sql` only keyword-checks. DuckDB's `read_csv` / `read_text` read any
file the process can, so one upload plus
`SELECT * FROM read_csv('/proc/self/environ')` returned the environment.
Proven locally with a planted secret file. The fix opens every upload through
one helper that copies the data into a table, then sets
`enable_external_access=false` and `lock_configuration=true`, so caller SQL
cannot switch file access back on. Live check after rebuild: normal query
fine, `read_csv('/etc/os-release')` → "file system operations are disabled by
configuration".

---

## The rest, in one pass

All keyed off the same two reads (ml-api routers, ml-portfolio API routes):

- **E11–E13** ml-portfolio LLM routes (`ai-tools`, `ai-explain`, `chat`) spent
  the site's keys with no cap on model, output tokens, message count or size,
  and defaulted to the billed provider. Now: model restricted to what the
  site's own tools use on a server key, output/size caps, Cohere/free-first
  defaults. `ai-explain` also gained Turnstile and a Groq→Cohere→Mistral→
  Gemini→Claude fallback chain (the user's order — free before billed).
- **E14 / E16** ml-sql had no origin check and one *global* 30/min limit (one
  caller could lock everyone out), and `/sql/connect` would connect to any
  address given (SSRF — loopback, private net, cloud metadata). Now:
  `routers/_guard.py` enforces origin, per-IP limits and a daily LLM cap;
  `routers/_conn_guard.py` refuses any target that is not a single public https
  host. E14 was proven live — before the rebuild the metadata request *hung
  20s*, the old code really trying to reach `169.254.169.254`.
- **E17** neither Space could block an IP (HF has no firewall, browsers hit the
  Spaces directly). Both now honour a `BLOCKED_IPS` Space variable. Shipped
  dormant — set the variable to use it.
- **E19 / E20** ml-api's automl custom URL had no https/public check
  (SSRF-lite, no key leak), and the attack-surface scanner followed redirects
  by hostname (could be bounced inward). Both closed; both low.

Confirmed safe and left alone: the live-scanner tools already resolve and
refuse private addresses; automl `/explain`'s `custom` provider never gets a
server key (`custom` is absent from the server-key map); the LLM-judge routers
already have origin, rate, budget and body-size guards.

---

## Two mistakes, and the analytics bug the sweep uncovered

**A deploy-poll that spent the billed keys.** After pushing E12, I polled the
live `/api/ai-explain` with a no-token request to detect the new code. The old
code answered that request — three times, on the billed Claude/Gemini keys,
before the deploy landed. The lesson, now a memory: a probe that loops until a
deploy is live runs against the OLD code first, so it must be one that BOTH the
old and new code refuse for free. E13's poll did this right (21 messages + a
keyless provider).

**The analytics dashboard was mostly measuring my own laptop.** Chasing a "0%
query success" card the user screenshotted, the real causes were two: the stats
route still read `meta.success` off `query_run` after the 2026-09-06 logging
rewrite moved outcomes to `run_success`/`run_error` (so every run since counted
as a failure), and the query fetched only the first 1000 events (keepalive
fills that in days). Fixing both, the 7-day event count went from a capped 1000
to 4801. Then the deeper one: `.env.local` holds the *production* Supabase keys,
so every local e2e run, demo recording and manual check had been writing into
the live table — 833 of the newest 1000 rows had no country, and all 182
keepalive `run_error`s were laptops pinging an unstarted `localhost:8000`.
`/api/track` and `/api/security-log` now skip writes unless `VERCEL` is set;
page views also record the browser time zone as a rough region. The old rows
were left in place by the user's choice.

---

## Commits

| Repo | Commit | What |
|---|---|---|
| ML-Unified | `20b3d74` | E10 — DuckDB file access locked |
| ml-portfolio | `180408f` | E11 — ai-tools cost caps |
| ml-portfolio | `5692b36` | E12 — ai-explain Turnstile, caps, free-first chain |
| ml-portfolio | `4e259ba` | E13 — chat conversation bounds |
| ml-portfolio | `b48bde4` | stats: success from run outcomes, paging past 1000 |
| ml-portfolio | `905cea9` | local runs stop writing to live analytics; browser tz |
| ml-sql | `fea4edc` | E16 — origin, per-IP limits, daily cap |
| ml-sql | `14775fb` | E14 — /sql/connect public-host check |
| ml-portfolio | `f8859a3` | text-to-sql shows load/connect outcomes; schema-read bug |
| ml-api | `a93a951` | E18 — skops-only model load, RCE closed |
| both Spaces | `7dcba14` | E17 — BLOCKED_IPS blocklist |
| ml-api | `0864438` | E19 — automl custom_base_url https+public |
| ml-api | `9ed10b1` | E20 — scanner stops following redirects |

Plus the `docs:` commits that recorded each row's hash and live result in
`OPEN_ISSUES.md`, per the standing rule to keep that file current as issues land.

Still open: the two cosmetic label fixes (need a file split), and **key
rotation** — the free Vercel keys (E9) and every key on both Spaces (E10
exposed them). Readable while the holes were open, so rotating is the real
close-out; it is the user's to do.
