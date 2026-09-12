# Part 282a — Phase 3 and Phase 4

Verbatim record of the session that followed [Part 281](Session_2026-09-12_TheTestsThatFoundSixBrokenPages_Part281.md),
same day. Split across four files because a single one would breach the
400-line limit: **282a** phases 3 and 4, **282b** the hardening plan and the
EDA fold-in, **282c** the Space retirement and the origin bug, **282d** the
Plotly rebuild agreement.

User messages are reproduced word for word. Assistant messages are the text
the user actually saw; tool calls are summarised in square brackets.

---

## Turn 1

**User:**

> do phase 3

**Assistant:** Phase 3 is the backend's deterministic shell: cascade order,
fallback, budget caps, schema validation. Let me see what test infrastructure
already exists there.

*[Explored `services/ml-api`, found CI already runs `pytest services/ml-api/tests/`.
Read `_llm.py`, `security/budget.py`, `origin_policy.py`, `rate_limit.py`,
`_schema.py`, `_validate.py`, `file_gate.py`, `body_size.py`,
`rag/generation.py`, `rag/_image_gen_budget.py`. Installed `slowapi` and
`yara-python` locally. Wrote five test files, ran them.]*

**Assistant:** The suite found one. The Vercel preview regex uses `.*`, which
matches slashes and colons.

*[Tightened `ALLOWED_ORIGIN_REGEX` to `https://[A-Za-z0-9.-]+\.vercel\.app`.
Ran the full suite: 207 passed. Then planted two deliberate bugs — moved
Gemini to the head of the cascade, changed the budget guard's `>=` to `>` —
and confirmed 13 tests went red before restoring.]*

**Assistant:**

Phase 3 is done. **165 new tests, 5 files, all green. The suite found one real bug.**

The bug, and I fixed it: the Vercel preview allowlist used
`https://.*\.vercel\.app`, and `.*` matches slashes and colons. So
`https://evil.com/?next=https://x.vercel.app` was an allowed origin. Not
reachable from a browser, since a browser never puts a path in an Origin
header. But this module exists precisely to refuse rather than negotiate, so
it should not depend on the caller formatting the header properly. The host
part is now `[A-Za-z0-9.-]+`. Real preview subdomains still pass.

| Suite | Tests | Covers |
|---|---|---|
| provider cascade | 26 | order, fallback, missing keys, candidate list |
| budget caps | 13 | both budget modules, at the boundary |
| schema and extraction shape | 67 | the eight schemas, JSON parsing, the normaliser |
| validation rules | 37 | invoice totals, balances, line items, formats |
| security gates | 23 | origin, body size, upload scanning |

They run in the existing CI job, no workflow change needed.

Three things worth knowing about what these do and do not prove:

- **They never call a provider.** Order and fallback rules are deterministic
  code, so providers are replaced with recorders. That also means nothing here
  would have caught the retired Cohere model name. Only a live call catches
  that. What these do catch is what made it invisible: a paid provider that is
  not last, and a cascade that keeps going after somebody already answered.
- **The field count is never asserted.** It is a model's decision, and it moved
  15 to 13 to 18. Only the nine invoice fields from the schema constant are pinned.
- **I proved they can fail.** I planted two bugs, moving Gemini to the front of
  the cascade and changing the budget's `>=` to `>`. Thirteen tests went red,
  and the right ones. Restored, 207 pass.

Two local-only notes: I installed `slowapi` and `yara-python` into the venv,
both already in the Space requirements. And `check-file-length.sh` says
`automl_stage.py` is now at 336 lines and can drop its baseline entry.

Commit? The origin policy change is backend, so that means a Space upload and
a rebuild too.

---

## Turn 2

**User:**

> yes

*[Staged six explicit paths, committed `299350b`, pushed. Uploaded six files to
the HF Space in one commit `118befd`, waited for the rebuild, then verified.]*

**Assistant:**

Done and verified live.

**Commit `299350b`**, pushed to ML-Unified. **Space commit `118befd`**, one
upload, one rebuild, now RUNNING.

The live Space confirms the origin fix is actually serving, not just that the
app came back up:

| Origin sent | Result |
|---|---|
| `https://evil.com/?next=https://x.vercel.app` | 403 |
| `https://evil.com` | 403 |
| `https://ml-portfolio-git-test-ramleo.vercel.app` | 200 |
| `https://ml-portfolio-rho.vercel.app` | 200 |

The first row is the one that matters. Before this commit it was 200.

Phase 3 is closed: 165 tests across the cascade, the spend caps, the schemas,
the normaliser, the validator and the request gates. They run in the CI job
that already existed, so the next push exercises them without any workflow change.

Phase 4 is what's left of the testing plan, and it's a different animal:
golden-set evaluations with property assertions instead of exact matches, run
nightly rather than per-commit, because they cost provider calls and their
output moves. Say the word when you want it.

---

## Turn 3

**User:**

> do phase 4

**Assistant:** Phase 4 needs live provider calls, so before building I'll check
what credentials CI actually has.

*[Found no LLM provider secrets in GitHub Actions — only Render hooks and a
security token. Read the `/document/analyze` SSE contract and the cache. Built
`services/ml-api/evals/` with `_pdf.py`, `_check.py`, `_client.py`, `_score.py`,
`goldens.py`, `run.py`, `README.md`, plus `tests/test_eval_harness.py`
(62 tests) and `.github/workflows/nightly-evals.yml`.]*

**Assistant:**

Phase 4 is built and everything that can be verified without spending a call is verified.

**269 tests pass** (62 new harness tests), ruff clean, all files under the limit.

What it is: six documents whose correct answers are known because I wrote them,
built as real PDFs at run time, posted to the deployed Space, and checked by
property rather than by string. An invoice total of 1180.00 passes as `1180`,
`1,180.00`, `$1,180.00` or `USD 1180.00`. Nothing anywhere asserts a field count.

Three standards, because three different things go wrong:

- **Hard.** Provider, cache, document type, and the arithmetic flags. A paid
  provider serving is a hard failure *even when every value is perfect*, because
  right answers from the billed key mean the two free providers ahead of it are
  dead. That check is the reason the suite exists, and it also caps what a
  nightly run can cost.
- **Scored.** Extracted values, judged on an aggregate 80% match rate. One
  missed field on one night is noise.
- **Inconclusive.** Nobody served. A busy free tier is not a regression, and
  calling it one is how a report gets muted. The run still fails if *every*
  document comes back this way.

Two design points worth flagging. There are no provider keys in this repo's
Actions secrets and I added none. The job posts to the Space, which already
holds them, so it also tests the real router-cascade-keys wiring where the
money bug actually lived. And the PDFs are generated per run with a unique
reference stamped in the footer, because the analyzer caches on file bytes. A
committed fixture would be served from cache forever and the eval would stay
green while the cascade rotted.

The nightly workflow runs at 03:20 UTC and installs two packages, not the full
ml-api requirements.

**I have not run it live yet.** That is six documents, roughly eighteen provider
calls. They should all land on free Cohere or Mistral, but if both fail the
cascade reaches the paid key, so I am not spending it without your say-so.
Options: run one document as a smoke test, run all six, or commit as-is and let
tonight's schedule be the first real run.

---

## Turn 4

**User:**

> proceed

**Assistant:** Running one document first as a smoke test, so a harness bug
costs one call rather than eighteen.

*[`invoice_consistent`: ok, cohere, 19.5s, 9/9 values. Then the full set.]*

```
  [  ok] invoice_consistent                 cohere              14.8s  9/9 values
  [  ok] invoice_total_does_not_add_up      cohere              14.4s  3/3 values
  [  ok] receipt                            cohere              15.2s  5/5 values
  [  ok] bank_statement                     cohere              25.7s  6/6 values
  [  ok] purchase_order                     cohere              15.7s  6/6 values
  [  ok] resume                             cohere              19.8s  7/7 values

Values matched : 36/36  (100%)
Hard failures  : 0
Inconclusive   : 0
Served by      : cohere
```

*[Committed `c27d609`, pushed. Dispatched the nightly workflow with one golden
to prove the job runs in the runner — it passed. CI green on all four jobs.
Saved a memory recording the four phases.]*

**Assistant:**

Phase 4 is done and verified in three places. **Commit `c27d609`**, pushed.

The live run passed: **36 of 36 values, all six documents served by Cohere, no
paid call.** Then I dispatched the actual nightly workflow with one document to
prove the job works in the runner, not just on my machine. It passed there too.
CI on the push is green across all four jobs.

One result worth pointing at. The `invoice_total_does_not_add_up` golden carries
a planted arithmetic error, and the run passes only because the validator caught
it on the live Space. That is a negative control that fired for real, not a
green light I have to take on trust.

Timings, since they set what the nightly costs:

| | |
|---|---|
| Per document | 14 to 26 seconds |
| Full set, with pauses | about 2 minutes |
| Provider calls per night | roughly 18, all free tier |

I skipped the Space upload deliberately. Rule 4 covers backend changes, and
nothing here runs on the Space. The evals are dev tooling that calls the Space
from outside. Uploading them would cost a rebuild and several minutes of 500s
to deploy files that never execute there. Say the word if you want the mirror
exact anyway.

Two things I did not build, and you should know they are gaps rather than
oversights. There is no eval for the scanned document path, because that needs
the vision model, which is the paid key. And the frontend has no nightly
equivalent. Both are additions, not repairs.

The whole plan is now closed. I saved the phase map to memory so it does not
get re-proposed.

---

Continues in [Part 282b](Session_2026-09-12_ThePhasesAndTheEDAFoldIn_Part282b.md).
