# Part 283 — Three things called verified

Continues [Part 282d](Session_2026-09-12_ThePhasesAndTheEDAFoldIn_Part282d.md).

2026-09-13. The EDA rebuild shipped, 28 Dependabot pull requests were resolved,
pandas 3 and numpy 2 and opencv 5 landed in both the repo and the Space, and
the backend went down for four minutes.

Most of that is in the commits and needs no retelling. Three findings do,
because each cost real work to locate and none is obvious from the code alone.

They share a shape. In each case something was checked against a thing that
resembled the deliverable rather than the deliverable, the check passed, and
the defect shipped.

---

## 1. thinc's numpy ABI, and why CI could not see it

Bringing the Space's requirements up to `numpy==2.4.6` killed the build:

```
thinc/backends/numpy_ops.pyx
ValueError: numpy.dtype size changed, may indicate binary incompatibility.
Expected 96 from C header, got 88 from PyObject
```

numpy 2 changed the size of an internal structure. thinc ships pre-compiled C
with the old measurement baked in, and the copy spacy 3.7.5 pulls was built
against numpy 1. pip installs it without complaint — it checks version
metadata, not what a wheel was compiled against — and it fails on the first
import. The Dockerfile's `python -m spacy download en_core_web_sm` is the
first thing that imports it.

**Raising thinc alone cannot work.** Every thinc 8.2.x pins `numpy<2.0.0`,
including the newest, and spacy 3.7 caps thinc below 8.3. A closed loop. The
fix is `spacy>=3.8.0,<3.9.0`, which requires thinc>=8.3.12, built against
numpy 2.

**Why CI stayed green for hours while main was un-deployable:** nothing in the
suite imported spacy. An import is the only thing that exercises a binary
interface. `services/ml-api/tests/test_native_abi.py` now imports all eleven
dependencies carrying compiled extensions, and asserts numpy really is 2.x so
the checks cannot pass vacuously under numpy 1.

**The other half of the lesson:** the rollback took about four minutes and was
a decision rather than a scramble, only because the Space's previous
requirements had been saved to the scratchpad *before* uploading. Do that
first, every time.

Related: there is a Docker on the development machine after all — the daemon
was merely stopped, and `docker version` fails identically for stopped and
absent. A local build of the Space's own image is the strongest pre-deploy
check available and was wrongly ruled out.

---

## 2. print-color-adjust does not survive Paged.js

The dark EDA report printed with its backgrounds but with near-black text on
them. Headings, stat values, narrative, table cells — all unreadable. What
stayed legible was the handful of elements carrying an explicit colour of
their own: section headings, table headers, the pass/warn/fail verdicts.

`print-color-adjust: exact` was declared inside the report stylesheet, which
is handed to Paged.js. Paged.js rewrites and rescopes what it is given, and
the declaration never reached the printed page, so Chrome applied its own
adjustment on the assumption of white paper. Anything inheriting its colour
was darkened.

It now lives in the host document's own stylesheet, which Paged.js never
touches and which is inserted at runtime so it lands last. Text colour is also
set on `.pagedjs_page_content`, so no body-level rule can reach inside a page
box by inheritance — `styles/10-print.css` forces near-black text site-wide
with `!important` for the handbook.

**A wrong theory worth recording**, because it was convincing: that same
`10-print.css` rule looked like the cause, and the symptom pattern fitted it
exactly. Measuring killed it — under `emulateMedia({media: 'print'})`,
`getComputedStyle` reported the correct colours throughout. The damage happens
in Chrome's print rasteriser, downstream of the cascade. Only rendering an
actual PDF reproduced it.

**A claim that was disproved by its own fix:** the dark theme warned that
browsers omit background colours unless "Background graphics" is ticked. With
the colours forced, a PDF generated with backgrounds explicitly off came out
correct. The warning was replaced.

---

## 3. `errors="coerce"` is the wrong fix for a removed pandas option

`df.apply(pd.to_numeric, errors='ignore')` was deprecated in pandas 2.2 and
removed in 3.0, where it raises `ValueError: invalid error value specified`.
Seven prediction tests went red on that one line, in two files.

The obvious replacement is wrong in a way no integration test notices quickly.
`errors="coerce"` also stops the crash, and it converts unconvertible values
to NaN instead of leaving the column alone — so a passenger's cabin letter or
an insurance region arrives at the pipeline as a blank and the model predicts
from nothing. It is a wrong answer, not an error.

`coerce_numeric()` in `routers/core/shared.py` restores the all-or-nothing
behaviour with a try/except around the raising form. Two of its six tests fail
against the `coerce` version, checked by actually swapping it in.

---

## The pattern

| What shipped broken | What it was checked against | What would have caught it |
|---|---|---|
| Missing Statistics panel | the build spec I wrote | the page being reproduced |
| Dark PDF, illegible text | the on-screen paginated preview | a rendered PDF |
| "No Docker on this machine" | a command that cannot tell stopped from absent | `command -v docker` |

Each took minutes to check properly once actually attempted. Two produced a
permanent guard — `test_native_abi.py`, and an e2e test that walks every nav
tab looking for a dead link. The third has no test, only the habit: a check
that cannot fail in the interesting case is not a check.

Open items are tracked in [OPEN_ISSUES.md](../OPEN_ISSUES.md).
