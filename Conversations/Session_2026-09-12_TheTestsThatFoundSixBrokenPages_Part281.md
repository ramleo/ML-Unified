# Session 2026-09-12 — Part 281
## The tests that found six broken pages

Closed the handbook-clip backlog, repaired the document tool's provider chain
(which had been quietly spending money for weeks), and gave the frontend its
first automated tests — which found a defect on their first run.

Sixteen commits across both repos. Every one is listed in §8.

---

## 1. What was asked, in order

1. Summarise Parts 275–280, the clip status, and the pending list.
2. Record the `multimodal-rag` clip.
3. Fix the anchor it exposed, then re-record.
4. Explain the two non-blocking findings, and say whether they need fixing.
5. Reorder the document cascade so the paid key is last.
6. Record `text-to-sql`, then `document-intelligence`.
7. Fix the "Verify number" false positive.
8. Plan automation testing, an EDA card, and security work — with web research.
9. Build phase 1, then phase 2.

---

## 2. Three clips, three bugs in the tools

All 25 handbook clips now carry title and closing cards. The backlog that
opened in Part 275 is closed.

More usefully: **each of the three clips recorded today exposed a defect in the
tool, not in the clip.** That is now the rule rather than the exception —
Part 275 §16 said re-recording is a testing activity, and this session is the
strongest evidence yet.

### 2.1 multimodal-rag — four takes

The narration promised that clicking a citation "opens that page at the region
the passage was read from". Take one opened no region.

**Fix #1 was wrong, and the reason it was wrong is the find.** The anchor sat
on `i === 0`, so it pointed at whatever the reranker ranked first. I moved it
to the first source in `likelyUsedSources`. Take two: identical failure.

That signal was an **empty array**. `likely_used_indices()` compares 4-grams of
the answer against each chunk; a short one-sentence answer that paraphrases
rather than quotes matches nothing. So the anchor fell straight back to index
zero — and worse, `[]` is truthy, so the panel had been rendering a confident
**"Used in answer — no" under every citation of a correct answer**, for every
visitor. Empty means *could not tell*, never *no*.

**Fix #2 asked for the property the sentence depends on.** Only a citation
carrying a bbox has a region to open. Figure and table chunks get one from
`mm_pdf.py`; text chunks never do. The anchor now prefers a bboxed citation the
answer used, then any bboxed one, then any used one, then the first card.

Take three landed on the figure and opened `PAGE 1 · FIGURE` cropped to the
region — but narrated "the top citation" over a card numbered **2**. Changed
the words, not the anchor: moving the anchor back to rank one would reinstate
the original bug, and rank moves per run.

**Cost: four paid Gemini vision calls, not the one estimated.** The vision
cascade is mistral→gemini and Mistral 429s everything, so every take bills.
The overrun was entirely fix #1 addressing the wrong cause.

### 2.2 text-to-sql — the number on screen was wrong

Narration said "about three and a half thousand rows". The live schema endpoint
gives 15,607 across 11 tables; 3,503 is the Track table alone.

Take one then contradicted itself, because `DbConnectPanel.tsx` **hardcoded**
`11 tables · ~3.5k rows`. Every visitor had been told the demo database was a
quarter of its real size. The clip was reporting the tool honestly and the tool
was wrong — the same shape as the three code fixes in Part 271.

### 2.3 document-intelligence — a claim that cannot be true twice

This clip had been blocked since Part 280: the recorder aborted at step 7,
which asserted "need review" on screen when nothing was flagged.

The script said fifteen fields. An earlier run produced thirteen. Today's run
produces **eighteen**. The number moves with whichever provider serves.

- Removed the count from the blurb and from step 7. **"Nine" stays** — that is
  the invoice schema in `_schema.py`, a constant, not model output.
- Step 7's assertion was checking step 8's claim. "need review" only renders
  when something is flagged, so a run that flagged nothing failed an assertion
  about field counts. It now asserts "fields extracted".
- "One field is asking to be looked at" → "a line item". Two are flagged today.

Everything else was verified against a real run first: Invoice at 100%, due
date and total in their own slots, four line items, both arithmetic checks
balancing while the second opinion flags anyway.

**A count produced by a model does not belong in a fixed script.** Stated in
Part 275 §9.3 about a moving metric; it applies to counts too.

---

## 3. The document tool had been billing Gemini for weeks

Raised as a one-line reorder. It took four commits, and the ordering alone
fixed nothing.

### 3.1 The reorder

`_CASCADE_ORDER` was mistral → gemini → cohere → cerebras. Mistral has no
reserved free capacity and 429s essentially everything (Part 276 §15), so
*second* was in practice **first**: the only paid key in the project served a
public, unauthenticated endpoint by default, while free Cohere sat third and
was almost never reached.

### 3.2 The reorder did not change who served

Verified with one real upload rather than assumed. Still Gemini. The Space log
said why:

```
Cohere failed: Client error '404 Not Found' for url 'https://api.cohere.ai/v2/chat'
Cerebras failed: 401 - {'message': 'Wrong API Key', 'code': 'wrong_api_key'}
cascade fell back to gemini after 3 failed attempt(s)
```

**Cohere had been dead.** This file asked for `command-r-plus`, a retired name.
The other nine Cohere call sites in the backend use `command-a-03-2025`, which
was verified serving on this same Space hours earlier. One name, one file.

After the swap a fresh upload reported `"provider": "cohere"`. The leak closed.

### 3.3 Cerebras: the key was fine, the account is not

The user's console showed the key active, so the 401 meant the **Space held a
different value**. They replaced it. The next probe returned:

```
Cerebras failed: 402 - 'Payment required to access this resource.'
```

Valid credential, free account, no service. A provider that cannot succeed is
not a fallback — it is a guaranteed wasted round trip in front of the paid key.
Dropped from the cascade, kept selectable by name.

Also found: `_provider_map` listed every cascade provider **except** Cerebras,
so the only way it ever ran was as a fallback after two others failed. That is
precisely how a broken key sat unnoticed — nothing could call it directly to
find out.

### 3.4 Lesson

**A free provider that fails silently is indistinguishable from a paid one
working.** Two different causes here — a retired model name and a stale secret
— produced the same single symptom: a bill. Neither raised anything.

---

## 4. "Verify number" flagged figures nobody had misread

Two independent false-positive sources, both reproduced locally with **zero API
calls**.

1. **The percent sign was part of the number token.** A caption reading `65.8`
   and an OCR reading `65.8%` — the same value off the same bar — compared as
   different numbers.
2. **The check ran on whole-page captions.** Its own docstring says "the SAME
   figure", but the single-visual path deliberately captions the entire page to
   keep a chart's title. The Northwind sample holds a percentage chart *and* an
   unrelated cost table in pounds: no shared numbers, both reads correct.

`_caption_page` now takes `scoped=`, and only the cropped-region caller can
flag. Verified with five cases including a genuine 42-vs-24 misread that must
still fire — a fix that only silences the check would pass a test asserting
"no warning".

---

## 5. The frontend had no tests at all

CI proved the site **compiled**. It never proved a page worked. Three times
this project has shipped a page broken for every visitor with nothing to catch
it: `/models` 500ing, `/api/ai-explain` dead behind a retired model name, and a
prompt-injection judge that could not run behind an HTTP 200.

### 5.1 Phase 1 — the harness

`@playwright/test` as an exact devDependency. Checked before adding that
neither `playwright` nor `playwright-core` has a postinstall at 1.62.1, so
`npm ci` does not download browsers and Vercel is unaffected — which was the
original reason the recorder's copy was kept out of `package.json`.

Port 3300, because ml-api's origin policy rejects every other local origin.
Production build, not the dev server. Two retries in CI and none locally, so
flakiness stays visible while it is being written.

**Tests select on the existing `data-wt` anchors.** They are already stable and
maintained, because a broken one fails a demo recording. A parallel set of
test-only ids would be a second thing to keep in sync with nothing watching it.

Proved the tests could fail before trusting them: a selector that does not
exist fails, and a planted exception is caught by the `pageerror` collector, so
that assertion is not vacuous.

### 5.2 Phase 2 — and six pages with no heading

56 tests over all 51 tool routes, about 7 seconds. The route list is read from
the **filesystem**, so a tool added next month is covered the day its route
exists. `capabilities.ts` would be the other obvious source but it imports
React icon components, and a test list should not need a UI library to resolve
in Node. A guard asserts the list is non-empty — a moved directory would
otherwise yield zero tests, which reads as green.

First run: **six pages render no heading element anywhere.** Not an `h1`, not
any level. `automl`, `ensemble`, `feature-engineering`, `feature-selection`,
`optuna`, `shap` — the pipeline tools that open into a modal wizard, each
rendering its title as a styled `<span>`. A screen reader got no document
outline. Every other page had one.

The assertion was **not** weakened. The six went into a visible `NO_HEADING_YET`
list with a second test that fails if it grows, then were fixed in the next
commit: `<span>` → `<h1>`, same text, size, weight and colour, `margin: 0`
since h1 carries a large default. Screenshotted two of the six to confirm
nothing moved. The list is now empty and its guard asserts zero.

### 5.3 Two CI faults found on the way

**The handbook check had been red for hours and I pushed past it four times.**
`c0d4b4a` changed a model name in `capabilities.ts` and never regenerated
`public/handbook.md`, so the handbook kept advertising a retired model. The
check was doing its job; not reading the result was the failure.

**secret-scan failed on every pull request and never on main.** gitleaks lists
a PR's commits so it scans only what the PR adds; that reads pull-request data,
which the repo's default token scope does not include:

```
GET /repos/ramleo/ML-Portfolio/pulls/6/commits
"Resource not accessible by integration"   403
```

Main has no PR to list, so main passed. **Eight Dependabot PRs had been red
since 2026-08-29** — including a Next.js bump and two updates to the actions
this CI itself depends on. Fixed with a job-scoped `permissions` block rather
than widening the repo-wide default, and PR comments disabled deliberately:
they need write, and GitHub hands Dependabot runs a read-only token regardless,
which would reinstate the same 403 on exactly the PRs being fixed.

Proven by asking Dependabot to rebase PR #2 — the only one failing both jobs —
and watching all five checks go green.

---

## 6. Watching the tests run

They are headless by default, which is right for CI and invisible on a desktop.
The user asked, fairly, how they were meant to see any of it.

```
npm run test:e2e         # run them, pass/fail in the terminal
npm run test:e2e:ui      # Playwright's own UI — pick tests, watch the
                         # browser, step through a timeline of what it did
npx playwright test --headed    # the normal suite, visible browser window
npx playwright test --debug     # step through one test line by line
```

`test:e2e:ui` is the one worth knowing. The others are for a specific question.

**And how to know the runs are honest**, which is the better question and was
asked directly:

- **Run it yourself.** One command, same result, depends on nothing I say.
- **CI runs it without me**, on every push, and the Actions log is a permanent
  record I cannot influence.
- **Read the tests** — two files, ~165 lines including comments.
- **Watch a planted failure.** A test that cannot fail passes forever.

And the honest limit: **green means only what the tests check.** The assertions
are deliberately narrow — page answers, heading renders, no uncaught error. A
tool whose button does nothing would still pass.

---

## 7. Lessons

1. **Ask for the property the sentence depends on, not for a rank.** Rank is
   the model's opinion and moves per run; "has a bbox" is a fact about the
   chunk. Fifth time an index-based demo anchor has cost takes.
2. **An empty result is not a negative result.** `[]` rendered as a confident
   "no" under every citation of a correct answer.
3. **A fix that only silences a check is not a fix.** Prove the check can still
   fail on a real fault.
4. **Verify the fix changed the outcome, not just the code.** Reordering the
   cascade was correct and achieved nothing, because the newly-first provider
   was 404ing.
5. **Read CI.** Four pushes went out while it was red.
6. **A count produced by a model does not belong in a fixed script.**

---

## 8. Commits

**ml-portfolio** — `15b9332` citations no longer claim "not used" when nothing
was measured · `72143e2` multimodal-rag re-recorded · `8d69ec9` demo database
row count was four times too small · `0828a0a` text-to-sql re-recorded ·
`43730ae` document-intelligence re-recorded · `0e8939f` Playwright harness and
CI job · `62889a4` handbook regenerated · `03865f4` secret-scan permissions ·
`0bcd734` a smoke test for every tool page · `0444fb7` six pages had no heading

**ML-Unified** — `a24e583` try every free provider before the paid one ·
`94ddb05` Cohere model was retired, so the paid key was serving · `5a1a810`
Cerebras selectable, three stale notes corrected · `e60d7b0` Cerebras dropped
from the cascade · `94660be` "Verify number" fired on figures nobody had
misread

---

## 9. Open at the end of this part

- **`mm_pdf.py` 373 lines, `_generate.py` 366** — both over the 350 threshold,
  splits deferred by explicit instruction, noted in their commits.
- **The "Verify number" fix is unverified against a live document** — proving
  it costs a paid vision call.
- **Handbook coverage is 25 of 50 chapters.** Never agreed as a goal; the
  standing recommendation is eight to ten more, not all of them.
- **`services/ml-eda` is orphaned** — 35 passing tests, no tool page, not
  deployed. Plan B of the hardening document covers it.
- **Seven Dependabot PRs still open** in ml-portfolio, now unblocked; twenty in
  ML-Unified, which were never blocked.
- **Phase 3 not started** — the deterministic shell: cascade order, fallback,
  budget caps, schema validation. Where every bug in this session actually
  lived, and none of them needed a language model to reproduce.
- Full plan: the **Portfolio Hardening Plan** artifact, published 2026-09-12.

---

**Continues in [Part 282a](Session_2026-09-12_ThePhasesAndTheEDAFoldIn_Part282a.md)** — phases 3 and 4, the ml-eda fold-in, and the spec for tomorrow's Plotly rebuild.
