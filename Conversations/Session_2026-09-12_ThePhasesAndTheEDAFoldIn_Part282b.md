# Part 282b — The hardening plan, and the EDA fold-in

Continues [Part 282a](Session_2026-09-12_ThePhasesAndTheEDAFoldIn_Part282a.md).

---

## Turn 5

**User:**

> update portfolio hardening plan

*[Listed artifacts, found "Portfolio Hardening Plan", read it, recounted tests
from the repositories (backend 326, frontend 56), rewrote the status strip,
inventory and all four Plan A phases, added an SVG diagram of the deterministic
shell, republished to the same URL.]*

**Assistant:**

Updated at the same link: https://claude.ai/code/artifact/a76e10ac-efe8-4582-9e94-3a1953426ef7

The header strip now reads from the repositories rather than from this morning.

| | Was | Now |
|---|---|---|
| Backend tests | 115 | 326 |
| Frontend tests | 0 | 56 |
| Nightly evals | none | 6 goldens, 36 checks |

What I changed beyond the numbers:

- **Plan A is marked shipped**, all four phases, each carrying what it actually
  found rather than what it proposed. Phase 1 found nothing, which is the right
  result for a harness. Phase 2 found the six pages with no heading. Phase 3
  found the origin regex bug. Phase 4 passed 36 of 36 on its first live run.
- **Added a diagram** of the deterministic shell around the probabilistic core,
  since that split is the whole argument and it was only prose before.
- **The edge-case table now has a "Now" column** and it is not flattering. Of
  the three cases, one is covered twice, one is fixed but has no test, and one
  is covered only by analogy. I would rather that be visible than rounded up.
- **Gap 3 in the security plan is half closed.** The nightly evals mean a stale
  free credential on the document path surfaces within a day, because the paid
  key serving is itself the alarm. Every other route is still swallowed by a
  fallback, and I said so.
- **New inventory section** for the three things fixed today, and a row
  admitting the two gaps I left: no eval for the scanned document path, no
  nightly for the frontend.

Plans B and C are otherwise untouched. Plan B picked up one line, that the
exploratory-data-analysis page will get a smoke test automatically the day its
directory exists, because the route list is read from the filesystem.

---

## Turn 6

**User:**

> i didnt understand, is there anything pending?

*[Counted open Dependabot PRs: 23 in ML-Unified, 8 in ML-Portfolio.]*

**Assistant:**

**Testing is finished. Nothing pending there.** All four phases shipped today.

Seven other things are pending. Only the first two are work I'd actually queue up.

1. **The EDA card, Plan B.** The service is written and has 35 passing tests.
   It just isn't deployed and has no page. This is the biggest ready-to-build item.
2. **31 Dependabot pull requests**, 23 in ML-Unified and 8 in ml-portfolio. They
   were blocked by the broken secret-scanning job until today. They're unblocked
   now and nobody has merged them.
3. **Two security gaps.** Edge rate limiting at Vercel, and an audit against the
   2026 OWASP list for LLM applications. Both are real, neither is urgent.
4. **Provider-failure alerting outside the document path.** The nightly evals
   catch a dead free provider on documents. Every other route still swallows a
   401 silently.
5. **ml-sql has two provider paths nobody has ever called.** Given that two
   retired model names hid in this project for weeks, assume they're broken
   until a call proves otherwise.
6. **Two files over the 350-line limit**, both splits you deferred on purpose.
7. **Handbook clips at 25 of 50.** Your call, and it always has been. My
   standing suggestion is eight to ten more, not all 25.

If you want one thing next, it's the EDA card. It's the only item on this list
where most of the work is already done and the missing part is a page.

---

## Turn 7

**User:**

> proceed

**Assistant:** Starting with what already exists, since ml-api already has an `eda.py` router.

*[Found `services/ml-api/routers/eda.py` — 408 lines, never imported, never
mounted, pinned as file-length debt, and a strictly smaller copy of what
`services/ml-eda` does modularly. Found `ML_EDA_URL` pointed at a third Space
that was live. Probed it: `/health` returned 200, `POST /eda` returned 500.
Reproduced locally: `ValueError: Out of range float values are not JSON
compliant: nan ... when serializing dict item 'kurtosis'`.]*

**Assistant:** Before I build: I found that `services/ml-api/routers/eda.py` is
408 lines of **dead code** — never imported, never mounted, and a strictly
smaller copy of what `services/ml-eda` already does properly. The dependencies
are a subset of ml-api's, so folding in adds nothing to install.

One scope decision changes the work materially.

*[Asked two questions.]*

**Question 1 — ml-eda has three endpoints. Which should I fold into ml-api and
surface on the page?**

- Profile + clean (recommended)
- Profile only
- **All three, including AI suggestions** ← chosen

**Question 2 — The dead 408-line routers/eda.py has to go, because a file and a
package cannot share the name 'eda'. How should I handle it?**

- **Delete it (recommended)** ← chosen
- Keep it, name the package differently

**Assistant:** All three, rebuilt to standard, and the dead file goes. Let me
first find everything that references ml-eda.

*[`git mv` of six modules into `services/ml-api/routers/eda/`; rewrote imports
to relative; deleted the dead `eda.py`; added `json_safe()` at the response
boundary; capped uploads; rebuilt `_suggest.py`'s provider handling with a real
cascade, `command-a-03-2025`, a budget cap and an LLM rate limit; removed three
dead assignments the old CI never linted; mounted in `app.py`; moved and split
the 394-line test file; added `test_eda_json_safety.py` and
`test_eda_suggest_cascade.py`; proved the json-safety tests fail without the
fix; deleted `services/ml-eda` and its CI steps.]*

*[Then the frontend: eight files under
`src/app/tools/exploratory-data-analysis/`, a capabilities entry, a toolNav
entry, handbook regeneration. Found the insights shape bug via React error 31
and the clean-config shape bug via a misleading CORS error. Split
`capabilities.ts` into four domain files because it breached its pinned size.
Corrected a "Local Compute" tag that would have produced a false privacy claim
in the handbook.]*

**Assistant:**

The EDA card is built and verified end to end. Everything is green: **358
backend tests, 57 frontend tests**, both builds, both length gates, lint clean.

**Three real bugs found, all live before today:**

- **The deployed ml-eda Space returned 500 for a large class of ordinary CSVs.**
  Any numeric column with fewer than four non-null values: pandas gives NaN for
  the kurtosis of three points, and JSON cannot carry NaN. The service answered
  `/health` with "ok" the whole time and its own 35 tests passed, because every
  fixture was big enough to have a defined kurtosis. Nothing on the site
  referenced it, so no user ever hit it. Fixed with one sanitiser at the
  response boundary, and six tests that fail without it.
- **The suggestion route was pinned to a retired Cohere model**, defaulted to
  the provider that rate-limits most, had no cascade at all, and offered a paid
  Gemini key to any anonymous caller with no budget cap. Rebuilt to the standard
  set today: free first, paid last, capped, rate limited, and it names the
  provider that actually answered.
- **A wrong config shape crashed the cleaner with an unhandled 500**, which is
  produced outside the CORS middleware, so the browser reported a CORS error and
  the real cause never reached the client. That sent me looking in the wrong
  place for several minutes. Now a 400 naming the offending key.

Two things I had to fix in my own work, both caught by using the page rather
than reasoning about it. Insights are objects, not strings, so the first render
threw a React error. And the cleaner's config is nested objects, not flat strings.

**One structural change you should know about.** Adding the card pushed
`capabilities.ts` past its pinned size, and the rule is shrink or split rather
than raise the pin. I split it into four files by domain behind an index that
keeps every existing import working. No consumer depends on flat order, only on
domain filtering, and the handbook diff confirms it: 50 to 51 tools, one new
row, nothing reordered.

I also caught myself tagging the card "Local Compute", which the handbook
generator turns into "the file never leaves your machine". The tool uploads the
CSV, so that would have been a false privacy claim in a published document.

`services/ml-eda` is gone as source, folded into ml-api. Its Space is still
running the old broken code and `ML_EDA_URL` still points at it, which only
affects the legacy static page. That needs your call separately.

Commit both repos? The backend change also needs a Space upload and a rebuild.

---

## Turn 8

**User:**

> yes

*[Committed `a0108ec` (backend) and `f680fdc` (frontend), pushed both. Uploaded
13 file operations to the Space in one commit `4f3763a`, including deleting the
stale `routers/eda.py`. Waited for the rebuild and verified live. CI on
ml-portfolio green; the ML-Unified failure turned out to be a Dependabot PR
hitting the gitleaks permission bug — fixed in `3d7e6d3` and proven by rebasing
PR 24, which went fully green.]*

**Assistant:**

The EDA card is live and working on production. Four commits.

| Repo | Commit | What |
|---|---|---|
| ML-Unified | `a0108ec` | fold ml-eda into ml-api, three bug fixes |
| ML-Unified | `3d7e6d3` | gitleaks pull-request scope |
| ml-portfolio | `f680fdc` | the tool page and the capabilities split |
| HF Space | `4f3763a` | 13 file operations, one rebuild |

Verified against the live Space, not just locally. The five-row CSV that
returns 500 on the old ml-eda Space now returns 200 with `kurtosis: null`. A
malformed clean config returns 400 naming the key. The page on the production
site profiles the sample, and the suggestions stream back labelled "answered by
cohere · command-a-03-2025", which is the corrected model name reporting the
provider that actually served.

**I owe you a correction.** When I said this morning that the Dependabot pull
requests were unblocked, that was only true of ml-portfolio. I fixed the
gitleaks permission there and never applied it to ML-Unified, so its 23 pull
requests kept failing for the same reason for the rest of the day. Fixed in
`3d7e6d3`, and I proved it by rebasing pull request 24 onto it: all four checks
now pass, secret scanning included. The other 22 need the same rebase to pick
it up.

Three things worth carrying forward from this build:

- **A deployed service with a passing health check and 35 green tests was broken
  for a large class of ordinary input.** Nothing found it because nothing called
  it. The tests were all written against datasets big enough to have a defined
  kurtosis.
- **An unhandled 500 reaches the browser as a CORS error**, because it is
  produced outside the CORS middleware. That sent me looking in entirely the
  wrong place, and it is worth remembering the next time a CORS failure appears
  on a route that was working.
- **Both of my own bugs came from using the page**, not from reading the code.
  The insight objects and the nested config shape were both invisible until a
  real response arrived.

Two things still need your call. The old ml-eda Space is still running the
broken code with `ML_EDA_URL` pointed at it, which only affects the legacy
static page. And the hardening plan now says "Plan B · open", which is no
longer true. Want me to update it?

---

Continues in [Part 282c](Session_2026-09-12_ThePhasesAndTheEDAFoldIn_Part282c.md).
