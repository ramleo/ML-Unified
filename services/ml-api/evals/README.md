# Golden-set evals

Phase 4 of the testing plan. Phases 1 to 3 cover code whose output is
fixed. This covers the part a model decides.

## Running it

```
cd services/ml-api
python -m evals.run                                  # against the deployed Space
python -m evals.run --dry-run                        # build the PDFs, send nothing
python -m evals.run --only invoice_consistent        # one document
EVAL_BASE_URL=http://localhost:7860 python -m evals.run
```

Needs `httpx` and `pymupdf`, nothing else. It exits non-zero on failure,
which is what makes the nightly workflow send mail.

Runs at 03:20 UTC daily via `.github/workflows/nightly-evals.yml`, and on
demand from the Actions tab.

## Why it is not part of CI

Every run makes real provider calls, and the answers legitimately differ
between runs. A suite like that on every push is slow, goes red when a
free tier is busy, and gets switched off inside a week.

The harness itself is a different matter. Its scoring logic is ordinary
deterministic code, and it is unit tested in `tests/test_eval_harness.py`
on every push, with no network. A nightly PASS is only worth anything if
that code is right.

## What it asserts, and what it refuses to

Three standards, because three different things can go wrong.

**Hard.** Which provider served, whether the cache answered instead of a
model, which of the eight document types was chosen, and whether the
arithmetic validator flagged what it should. A model has no vote on any of
these. Any failure fails the run.

The provider check is the reason this suite exists. The document cascade
fell through to the only billed key on the Space for weeks, and the only
symptom was an invoice from Google. Here, a paid provider serving is a
hard failure even when every extracted value is perfect — because right
answers from the billed key mean the two free providers ahead of it are
dead and nobody has noticed. It also bounds what a nightly run can cost.

**Scored.** The extracted values, compared as properties rather than
strings. A total of 1180.00 is correct as `1180`, `1,180.00`, `$1,180.00`
or `USD 1180.00`. Amounts are parsed and compared numerically, dates are
parsed and compared as calendar dates, and text passes if either value
contains the other. A model returning "Northwind Trading" or "Northwind
Trading Ltd." is right both times. The run is judged on the aggregate
match rate against `EVAL_THRESHOLD`, default 80%, because one missed field
on one night is noise.

**Inconclusive.** Nobody served. A free tier out of capacity is not a
regression in this repo, and reporting it as one is how a report becomes
noise people mute. These are counted and shown separately, and the run
still fails if every document came back this way — a whole cascade being
down is worth waking up for.

Nothing asserts on how many fields came back. The extractor is asked to
volunteer any extra sections it finds, so the count is a model's decision:
it moved 15 to 13 to 18 across providers, and a demo script that quoted
one of those numbers out loud had to be re-recorded.

## The cache

`routers/document/_cache.py` keys on the bytes of the uploaded file. A
committed fixture would be served from cache on every run after the first,
and the eval would stay green for weeks while the cascade rotted — the
exact failure it exists to catch. So the PDFs are built at run time with a
unique reference line stamped into the footer, and a cached answer is a
hard failure rather than a quiet pass.

## Adding a golden

Append to `GOLDENS` in `goldens.py`:

- `lines` must actually contain every `text` value it expects. A unit test
  enforces this, because asking a model to invent an answer and then
  calling the invention correct is worse than having no test.
- Field names must exist in that document type's schema. A typo can never
  match, so it would read as the model getting quietly worse.
- Use `must_flag` only for arithmetic the validator owns.
- Scanned documents are out of scope. That path needs a vision model,
  which is the paid key, and this suite must never reach it.
