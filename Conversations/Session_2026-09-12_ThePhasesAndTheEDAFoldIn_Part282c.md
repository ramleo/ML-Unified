# Part 282c — Retiring the Space, and the app that refused its own pages

Continues [Part 282b](Session_2026-09-12_ThePhasesAndTheEDAFoldIn_Part282b.md).

---

## Turn 9

**User:**

> yes

*[Recounted from the repositories: backend 380, frontend 57. Rewrote Plan B as
shipped in three steps, added three inventory rows for the new bugs, corrected
the CI row to admit the half-applied gitleaks fix. Republished.]*

**Assistant:**

Updated at the same link: https://claude.ai/code/artifact/a76e10ac-efe8-4582-9e94-3a1953426ef7

| | Was | Now |
|---|---|---|
| Backend tests | 326 | 380 |
| Frontend tests | 56 | 57 |
| EDA card | built, no page | live |

Plan B is now written as shipped, in three steps, each carrying what it actually
found rather than what it proposed. I gave it a callout for the thing the plan
itself got wrong: this document said the EDA service was not deployed. It was,
and it was returning 500 to a large share of real CSVs. The lesson is worth
keeping, so I put it in bold. A service nobody calls is not dormant, it is
unmonitored.

Three new rows in the inventory for the bugs, including the one that cost me the
most time. An unhandled 500 is produced outside the CORS middleware, so the
browser reports a CORS failure and the real cause never leaves the server.

I also corrected the CI row rather than quietly updating the count. It now says
plainly that the secret-scanning fix was applied to one repository and not the
other, that ML-Unified's 23 pull requests stayed red for the rest of the day
after ml-portfolio's eight were unblocked, and that the fix is proven by
rebasing one pull request and watching all four checks pass.

Plan C is untouched. Two gaps open, one half closed.

---

## Turn 10

**User:**

> what are you suggesting?

**Assistant:**

Two things, both loose ends from today, both quick.

1. **Retire the old EDA Space and point `ML_EDA_URL` at ml-api.** It is running
   broken code that ml-api now serves correctly. One variable change plus
   deleting a Space. I need your go-ahead because it is your infrastructure.
2. **Merge the 31 Dependabot pull requests.** 23 in ML-Unified, 8 in
   ml-portfolio. They are unblocked now but each needs a rebase to pick up the
   CI fix. I can do them in batches and stop on the first failure.

After that, the biggest remaining item is **Gap 1 in the security plan**, edge
rate limiting at Vercel. It is free tier, it is the layer you concluded could
not be done in application code, and it is about an hour.

Everything else can wait: the two deferred file splits, the untested ml-sql
provider paths, and the handbook clips at 25 of 50.

Say which and I will start.

---

## Turn 11

**User:**

> do 1

*[Checked the Space variables — `ML_EDA_URL` was a plain variable and
`ML_VISION_URL` already pointed at ml-unified itself. Set `ML_EDA_URL` to
`https://wram1708-ml-unified.hf.space`, waited for the restart, confirmed
`/app-config`. Then drove `?mode=eda` in a browser and the upload failed with
"Origin not allowed."]*

**Assistant:** Found a real problem: the Space's own served page cannot call its
own API. Confirming.

```
--- POST from the Space's own origin ---
  403
--- same request, no Origin header ---
  200
```

**Assistant:** Confirmed, and it is pre-existing rather than something I
introduced: the vision page already pointed at ml-unified and had the same
problem. The app rejects its own served pages with 403, because a same-origin
POST still carries an `Origin` header.

*[Added `_self_origins()` reading `SPACE_HOST` or deriving from `SPACE_ID`, six
tests including one asserting other Spaces stay blocked. Committed `d30d6b4`,
pushed, uploaded to the Space as `4b92c8f`, verified live in four directions,
then drove the legacy page end to end. Paused the old ml-eda Space.]*

**Assistant:**

Done, and it turned up a bug worth more than the task itself.

**What I did.** Pointed `ML_EDA_URL` at ml-api, verified the legacy page against
it, then paused the old ml-eda Space rather than deleting it. Pausing stops it
serving and is reversible; nothing points at it any more, so deletion buys
nothing that cannot wait. It now answers 503.

**The bug.** Driving the legacy page in a browser, the upload failed with
"Origin not allowed". The app was rejecting its own served pages with 403. A
same-origin POST still carries an `Origin` header, and the Space's own origin
was not on the allowlist. This was not something I introduced. The vision page
already pointed at ml-api and had the same fault; it had simply never been
exercised. Fixed in `d30d6b4`, deployed as Space commit `4b92c8f`.

The origin is read from the platform's own `SPACE_HOST`, or derived from
`SPACE_ID`, so a rename or fork keeps working. It adds one exact origin,
deliberately not a wildcard over `hf.space`, which would let every Space on the
platform call this API. Verified live in all four directions:

| Origin | Result |
|---|---|
| The Space's own | 200, was 403 |
| The production front end | 200 |
| Another Space | 403 |
| A lookalike hostname | 403 |

Then the legacy page end to end in a real browser. It renders everything, and
its statistics table shows `kurtosis: null` for the short column, which is the
exact value that used to crash the old service.

**364 backend tests pass**, six of them new for the self-origin logic, including
one asserting the fix did not open the door to other Spaces.

Two notes. The production site and ml-sql are both unaffected, checked after two
Space restarts. And there is an unrelated pre-existing 500 from the analytics
endpoint on page load, which I have not touched.

Want me to update the hardening plan again? Plan B's one open item is now closed
and this origin bug belongs in the inventory.

---

## Turn 12

**User:**

> yes

*[Updated counts to 386 backend, added an inventory row for the 403 bug,
replaced Plan B's "Still open" section with one on retiring the Space.
Republished.]*

**Assistant:**

Updated at the same link: https://claude.ai/code/artifact/a76e10ac-efe8-4582-9e94-3a1953426ef7

Three changes:

- **Backend tests 380 to 386**, ml-api at 364, from the six new self-origin tests.
- **A new inventory row for the 403 bug**, including that it hit three pages,
  that the origin is now read from the platform rather than hardcoded, and that
  it is one exact origin rather than a wildcard over `hf.space`, with a test
  holding that line.
- **Plan B's open item is closed** and replaced with a short section on retiring
  the Space. It says the Space is paused rather than deleted, and why: paused
  stops it serving, is reversible, and nothing points at it.

I gave that section the lesson in bold, because it is the one worth keeping from
today. Checking the thing you changed is not the same as using it. The repoint
verified fine by every measure I had, the injected URL was right and that URL
answered 200, and the page was still broken. Only opening it in a browser showed that.

Plan C is untouched. Two gaps open, one half closed.

---

## Turn 13

**User:**

> where did you add eda?

**Assistant:**

Four places.

**Backend, in ml-api.** The code moved out of the deleted `services/ml-eda` into
a package at `services/ml-api/routers/eda/`, mounted in `app.py:224-225`. Three
endpoints:

| Route | File |
|---|---|
| `POST /eda` | `router.py:34` |
| `POST /eda/clean` | `router.py:123` |
| `POST /eda/suggest` | `_suggest.py:302` |

The supporting modules are `_stats.py`, `_readiness.py`, `_clean.py` and
`_utils.py`, all moved across unchanged apart from the fixes.

**Tests, in ml-api.** Four files: `test_eda.py` and `test_eda_multivariate.py`
are the 35 that came with the service, split because the original was 394 lines.
`test_eda_json_safety.py` and `test_eda_suggest_cascade.py` are new.

**The page, in ml-portfolio.** `src/app/tools/exploratory-data-analysis/`, eight
files. The shell is `page.tsx`, the upload and orchestration is `EdaRunner.tsx`,
and the four panels are overview, columns, charts and actions.

**The card, in ml-portfolio.** `src/data/capabilities/pipeline.ts` line 16, in
the ML Pipeline domain, plus a line in `src/lib/toolNav.ts` so the back link
goes to the right area page.

Live at https://ml-portfolio-rho.vercel.app/tools/exploratory-data-analysis, and
the legacy static page at `?mode=eda` on the Space now hits the same endpoints.

---

Continues in [Part 282d](Session_2026-09-12_ThePhasesAndTheEDAFoldIn_Part282d.md).
