# Part 287 — The proofs became tests, and the guidelines got teeth

Continues [Part 286](Session_2026-09-14_TheSweepThatE1Started_Part286.md).

2026-09-16. The E10–E20 sweep had left three loose ends worth finishing: its
guard proofs were one-off `curl`s and local scripts, not tests; two cosmetic
labels were still wrong; and there was no signal when a free key died outside
the document path. This session turned the proofs into a permanent suite,
closed those items and one new one (E21, found by accident), then made a first
implementation pass through `WEBSITE_GUIDELINES.md`.

The spine of the day: **a fix isn't finished until something watches it** —
whether that's a CI test, a dashboard row, or a guard that refuses the naive
case. And where a fix can only be partial, say so rather than imply more.

---

## 1. E4 — the guard proofs became tests, and ml-sql entered CI

E10 (DuckDB file-read), E14 (`/sql/connect` SSRF) and E18 (skops-only model
load) were each proven once by hand and had nothing catching a regression.
ml-sql had **no test suite at all** and was not in CI — that was E4.

New `services/ml-sql/tests/`: `test_duckdb_conn.py` (E10 — a planted secret is
refused via `read_csv`/`read_text`; the `/proc/self/environ` payload too),
`test_conn_guard.py` (E14 — 25 accept/refuse cases with DNS mocked, so it is
hermetic and offline), `test_providers.py` (the untested provider paths — each
provider unwraps a *different* reply shape, mocked HTTP, no key spent). Plus
`test_skops_safe.py` in ml-api (E18 — genuine model round-trips; joblib, evil
pickle and an unlisted-type skops file all refused; a marker file proves the
evil pickle's payload never ran). A new `test-ml-sql` CI job runs the ml-sql
suite on every push (light deps, its own job, no torch).

Verified in a scratch venv: 39 ml-sql + 5 E18 pass, ruff clean, and CI green
(39 passed, nothing skipped). Then the habit that matters: the E10 test was
shown to **fail against the pre-fix broken open** — a plain `duckdb.connect()`
leaked the planted secret; the locked connection refused it. A test that
cannot fail in the interesting case proves nothing. `2192ccc`.

## 2. E18 — one label was wrong, the other was right

`Step4Results.tsx` had two download buttons, and the reflex would have been to
"fix both `.pkl` labels." Reading first showed they hit **different** routes:
the winner's small button calls `/models/{id}/export`, which returns a
**`.skops`** file since E18 — mislabelled `.pkl`. The action-bar button calls
`/model/{id}/download`, which genuinely serves a joblib **`.pkl`** — correct as
written. So only the first changed.

The file was 410 lines (over the gate), so the AI-analysis panel was extracted
to `AutoMLAnalysisPanel.tsx` first (240 + 243, both under 400) — a pure
presentational split. Verified live by running the whole AutoML wizard on the
Space and reading the response headers: the export button serves
`…_pipeline.skops`, the download button `…_pipeline.pkl`. Label and artefact
now agree. ml-portfolio `4dfce66`, tracker `8102c35`.

## 3. The cleanup that found E21

The wizard run left a test model on the shared Space, so cleaning it up meant a
`curl -X DELETE`. It returned 200 — **an unauthenticated no-Origin request had
just deleted a model.** The origin middleware refuses a *disallowed* Origin but
lets a *no-Origin* request through by design, and the delete route had no other
auth. That is E21, logged on the spot (`29aff74`). (Eight leftover probe models
from earlier sessions were cleared the same way, once the user approved — the
auto-mode classifier blocks irreversible deletes, so each needed a go-ahead.)

The fix is deliberately **partial, and named as such**: `delete_model` now
requires an allowlisted Origin (`origin_present_and_allowed`), refusing the
naive/accidental `curl`. It does **not** stop a curl that forges the Origin
header — only Turnstile/auth would, judged disproportionate for a route whose
worst case is deleting a model that regenerates on the next train. `/train` was
left alone (already rate-limited, and origin-requiring it is equally forgeable
while breaking 4 tests). Regression test `test_model_delete_origin.py`; the
user chose the depth (DELETE-only, dashboard-not-email). Backend change, so
both files were uploaded to the Space and verified live after the rebuild with
a harmless discriminator — a no-Origin DELETE of a nonexistent id: **403** on
the new code (guard fires before the lookup) vs 404 on the old, deleting
nothing. `af02fcc`.

## 4. E3 — surfacing a dead key instead of swallowing it

The nightly evals catch a stale free key on the document path (the paid key
serving is itself the alarm). Every other LLM route caught a provider 401/403
and moved on silently, so a dead free key quietly escalated to the billed
Claude/Gemini key with no signal.

This was a design decision, not a guess, so it was put to the user: **channel**
(dashboard log, not email — no new infra) and **scope** (ml-portfolio's three
LLM routes, not the HF Spaces). New `src/lib/providerAlert.ts`: `isAuthFailure`
distinguishes a dead key (401/403, by `.status` or an "invalid/expired/
unauthorized" message) from a transient 429/5xx/network blip, and
`recordProviderAuthFailure` writes an `auth_failure` row to the `llm_calls`
table the dashboard already reads, plus a greppable `PROVIDER_AUTH_FAIL` log
tag — VERCEL-gated and throttled to one row per route/provider per 10 min so a
dead key can't flood the table. Classifier check: 8 real auth shapes flagged, 6
transient/network shapes ignored. ml-portfolio `078d076`, tracker `9911e25`.

## 5. A first pass through WEBSITE_GUIDELINES

Asked to "implement those guidelines to our website." Most of the doc was
already ✅; the honest gaps were narrow. Evidence, not assumption, found them:

- **SEO §D** — there was **no** `robots.txt` or sitemap. Added `app/robots.ts`
  and `app/sitemap.ts` (tool slugs read from the filesystem at build, so a new
  tool is included automatically — 58 URLs, confirmed in the built output).
- **A11y §B — reduced motion** — the CSS honoured it in four files, but the
  canvas animations (ConstellationBackground, on 53 pages) ran a rAF loop that
  ignored it. Added a global `prefers-reduced-motion` CSS block *and* made the
  background draw a single static frame when set.
- **A11y §B — focus + landmarks** — added a site-wide `:focus-visible` floor,
  and a `<main>` landmark to **every** tool page. There is no shared tool
  layout, so this was 53 pages: a codemod for the 41 sharing the `relative z-10`
  wrapper, the 10 outliers (different `tool-header-row` structures, automl's
  content in an inner component) hand-placed. Exactly one main each; build clean.
  `e830ce3`, `618ee08`.

The larger, measurement-driven tail — `next/image` migration (28 files),
contrast on the dark theme, Core Web Vitals, heading structure — was **not**
done. It was written up as a dated plan in the guidelines doc (run the axe /
Lighthouse audits first so the effort is sized by real findings), to do the
next day. `97246d5`.

---

## Judgment, not rote — E5 deferred on purpose

E5 ("split `mm_pdf.py` and `_generate.py` before adding") was declined this
session rather than executed. Reading found the premise had drifted: the two
files are **deployed** backend code, neither is *over* the 400 gate (373, 366),
and they are not special — **ten** files sit in the 360–394 band. E5's own
wording is "split *before adding*", a conditional gate, and there is no feature
queued for either. Splitting live-Space modules purely to shave line count —
each needing an HF upload, a rebuild and a re-verify — is refactor-for-its-own-
sake with real deploy risk and no gain. Deferred until a change actually needs
one of them, which is exactly what the rule intends.

---

## Commits

| Repo | Commit | What |
|---|---|---|
| ML-Unified | `2192ccc` | E4 — guard proofs → tests, ml-sql into CI |
| ml-portfolio | `4dfce66` | E18 — `.skops` label fix + Step4Results split |
| ML-Unified | `8102c35` | E18 follow-up recorded |
| ML-Unified | `29aff74` | E21 logged |
| ml-portfolio | `078d076` | E3 — provider auth-failure alerting |
| ML-Unified | `9911e25` | E3 recorded |
| ML-Unified | `af02fcc` | E21 — origin-required DELETE + test (Space uploaded, verified live) |
| ml-portfolio | `e830ce3` | robots/sitemap + reduced-motion + focus-visible |
| ml-portfolio | `618ee08` | `<main>` landmark on all 53 tool pages |
| ML-Unified | `97246d5` | guidelines: status + 2026-09-17 plan |

Test-model cleanup also removed 8 leftover probe models from the Space, leaving
only the 4 built-ins plus `80-cereals` (a real dataset, kept).

---

## Lessons

- **A fix isn't finished until something watches it.** One-off proofs rot the
  moment the next commit lands; E4 turned them into CI tests, and E3 into a
  dashboard row. Prove the watcher can fire (E10's test fails against the old
  open; E21's discriminator is 403 vs 404).
- **Read before "fix both."** The two `.pkl` labels looked identical; one was a
  bug and one was correct because they served different formats.
- **Cleanup is reading too.** Deleting a test model surfaced an unauthenticated
  delete no one had noticed.
- **Name a partial fix as partial.** E21's origin guard stops the naive curl,
  not a forged one; saying so beats implying protection it doesn't give.
- **Let the user decide the genuinely open choices.** E3's channel and scope,
  E21's depth — asked, not assumed, because each changed what got built.
- **Most of a guidelines doc can already be true.** The value was finding the
  few real gaps with evidence, not re-doing what was in force.

Open items are tracked in [OPEN_ISSUES.md](../docs/OPEN_ISSUES.md); the website
follow-ups in [WEBSITE_GUIDELINES.md](../docs/WEBSITE_GUIDELINES.md).
