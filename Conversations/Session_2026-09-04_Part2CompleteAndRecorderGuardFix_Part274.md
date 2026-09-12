# Part 274 — Part 2 completed, and a hole in the recorder's own safety check

**Date:** 2026-09-04
**Repos touched:** `ml-portfolio` only. **No backend file changed, so no HF Space
upload applies.**
**Commits:** `a3a8b8e`, `d11dd48`, `f55e95e`, `5322fc6` — all pushed to `main`.
**Paid API calls spent:** roughly 35, all Mistral small, none batched back to back.

---

## 0. Where things stand in one paragraph

Three chapters built, which took handbook coverage from 21 of 50 to **24 of 50**
and finished Part 2. The three of them cost about thirty-five paid calls between
them, most of that on probes rather than takes. The durable output is not the
clips: it is two facts about how this project's own machinery works that nobody
had written down, one of which had been silently limiting every demo that types
into a box, and one of which will bite again the next time anything compares two
PDFs. A stale plan file was also found to describe work that has entirely
shipped.

---

## 1. The commits

| Hash | What |
|---|---|
| `a3a8b8e` | fix(optuna): the AI panel was told every model was called "undefined" |
| `d11dd48` | feat(demo): Contract/Invoice Reconciliation (ch 12) |
| `f55e95e` | feat(demo): Document Intelligence (ch 13) |
| `5322fc6` | feat(demo): LLM Prompt Injection Detection (ch 41) |

---

## 2. What the owner asked for, in order

1. *"what you mean?"* about the live-Vercel verification pass — **withdrawn**, see §3.
2. *"do this one-line optuna/page.tsx:118 fix"*.
3. *"whats left in handbook?"* → *"what is your suggestion?"*
4. *"from part 3 and 4 what we should start?"*
5. Three separate go-aheads to build ch 12, ch 13, ch 41.
6. *"document the above conversations to Conversations/"*.

---

## 3. A recommendation withdrawn

For four sessions I had been carrying "verify Parts 269–272 against live Vercel"
as an open item. Asked to explain it, I did, and the owner pointed out those
features were done and confirmed. They were right, and the item was mine, not
theirs — it had never come from a session, only from me.

Withdrawn rather than deferred. There was no evidence anything was broken live,
the owner uses the site daily, and the one thing in that area with real evidence
behind it — the empty local Supabase keys — was already diagnosed in Part 273.

**Worth remembering:** a recommendation that survives four write-ups without ever
being acted on is usually not waiting for time. It is waiting to be dropped.

---

## 4. The stale plan

`~/.claude/plans/plan-multimodal-rag-curious-charm.md` describes an app-safeguard
plan: CORS wide open, no rate limiting, no auth, a cost-abuse vector on
server-key LLM routes, no frontend security headers, no Dependabot, no secret
scanning.

Checked before recommending any of it. **All of it has shipped:**

```
services/ml-api/security/  →  body_size.py  budget.py  events.py
                              file_gate.py  origin_policy.py  rate_limit.py
next.config.ts             →  headers() present
both repos                 →  .github/dependabot.yml, gitleaks in ci.yml
```

The plan file can be deleted. This is the third time the standing "verify pending
items before building" rule has paid for itself, and the first time it has caught
a whole plan rather than one item.

---

## 5. Chapter 12 — Contract/Invoice Reconciliation (`d11dd48`)

164 seconds, 11 steps. The tool had **zero anchors**; this added them to the doc
chips, their role toggles, the Check button, the report and each finding's
passage pair.

### 5.1 The samples are generated, and the generator carries the answer key

`scripts/make-reconciliation-samples.py` writes a contract and an invoice with a
planted ground truth, documented in its own docstring:

| clause | contract | invoice | expected |
|---|---|---|---|
| hourly rate | USD 145.00 | USD 165.00 | **discrepancy** |
| payment terms | Net 30 | Net 15 | **discrepancy** |
| fuel surcharge | capped at 4% | 4% | agrees — must NOT flag |
| interest | 1.0%/month | 1.0%/month | agrees — must NOT flag |

The two agreeing clauses are the control. A tool that flags four things is as
wrong as one that flags none, and only a document with a known answer shows that.

### 5.2 LESSON — chunks are built one page at a time

The first draft was one page per document with all clauses on it. Each document
came back as **a single chunk**, so the judge was handed whole-contract versus
whole-invoice and could only ever return one finding.

`mm_ingest.py` builds chunks per page:

```python
for page_num in range(1, n_pages + 1):
    page_chunks, b64, page_summary = await loop.run_in_executor(...)
    chunks.extend(page_chunks)
```

Rebuilt as four pages, one clause each. Four chunks, and the rate clause pairs
with the rate clause.

**This will bite anything that compares two documents.** Page count, not word
count, is what decides how finely a PDF can be compared.

### 5.3 LESSON — two passages can be too similar to compare

After the split, the Net 30 versus Net 15 discrepancy still went unreported.

The cause was that the invoice's payment-terms page repeated the contract's
sentences **verbatim**. That scored above `_SIM_CEILING = 0.93` and the pair was
dropped before the judge ever saw it. Too similar, not too different.

Reworded realistically and it was found. Both findings are in the generator's
comments so the next person does not rediscover them.

### 5.4 The result, and why it is a better demo than a clean sweep

Both planted discrepancies found and **confirmed**. One extra finding — term cap
48,000 versus cumulative billings 31,210 — is not a discrepancy at all, and the
second-opinion pass caught it and badged it **Unconfirmed**.

The last two steps are about that badge. A demo where the tool is right about
everything teaches less.

### 5.5 The recurring `expect` trap, fourth appearance

Take one narrated the Unconfirmed badge while spotlighting the row **above** the
one carrying it. The guard passed because the word was elsewhere on the page.

Which finding comes back unconfirmed changes run to run, so an index anchor
cannot work. The badge and its passage pair got names of their own:

```tsx
<span data-wt="recon-unconfirmed" ...>
<div data-wt={d.confirmed ? `recon-passages-${i}` : "recon-unconfirmed-passages"}>
```

**The general rule, now stated four times across four sessions:** anything whose
position is decided by a model cannot be addressed by position.

---

## 6. Chapter 13 — Document Intelligence (`f55e95e`)

184 seconds, 12 steps. Part 2 complete at 4 of 4.

### 6.1 Two splits before anything else

| File | Before | After | Extracted |
|---|---|---|---|
| `DocFieldsPanel.tsx` | 367 | 267 | `DocExportDropdown.tsx` |
| `DocIntelRunner.tsx` | 363 | 326 | `DocProcessingRail.tsx` |

Both were over the 350-line threshold, so rule 3 applied before a single anchor
went in.

### 6.2 The sample carries two dates and three amounts on purpose

`scripts/make-document-intel-sample.py`, ground truth in the docstring: invoice
date 02 July and due date 01 August; subtotal 12,480.00, tax 1,029.60, total
13,509.60.

With one date and one amount there is no way to tell an extractor put the wrong
one in the wrong slot. It placed all five correctly, classified the document as
an Invoice unprompted at 99%, and returned **15 fields — the 9 the invoice schema
defines plus 6 it was never asked for** (VAT number, vendor email, PO reference).

### 6.3 A narration written from a cached artifact

Step 8 originally described the flag note in detail, read off an earlier probe.
Checking `_validate.py` showed the deterministic arithmetic checks only fire on a
**mismatch**:

```python
"note": f"Line items sum to {total:.2f} but subtotal is {sub}"
```

Here they matched, so the flag came from a model pass — and that wording is not
stable between runs. Rewritten to lead with the checks that always run and are
verifiable against the page (line items sum to the subtotal; subtotal plus tax
equals the total).

Both takes hit the 24-hour document cache — the panel reads *"via Mistral
(cached)"* in the frames — so the specifics happened to be right for this clip.
**Being right by cache is not being right.**

### 6.4 One step deliberately not built

Editing a field POSTs a correction that becomes few-shot guidance for later
extractions of that document type on the live Space. Not performed; the
capability is described in the closing narration instead. Teaching the deployed
tool something on the owner's behalf is not mine to do for a video.

---

## 7. Chapter 41 — LLM Prompt Injection Detection (`5322fc6`)

158 seconds, 12 steps. Part 4 goes to 9 of 21. No split needed — the whole tool
is 439 lines across four files.

### 7.1 The demo runs the control, not just the attack

The clip uses the **indirect** attack: a quarterly sales summary with real-looking
revenue figures above and below, and one line in the middle addressed to the AI
rather than the reader.

Then it runs the tool's own built-in benign control — a work email containing
*"please ignore my previous email"* — which comes back **Low risk, zero pattern
matches, judge clear**. A detector that cries wolf at that sentence gets switched
off by its users, and half the demo is showing that this one does not.

### 7.2 Unplanned and kept

The pattern list labels the attack `INDIRECT` while the judge labels it
`DIRECT OVERRIDE`, both visible in the same frame. They disagree on the name and
agree on the risk, which is worth more than two boxes that always match.

### 7.3 LESSON — `expect` could not see what you typed

Step 3 aborted asserting a string that was plainly on screen. The guard read only
`innerText`, and **a textarea's or an input's contents live in `.value`, not in
the DOM's text**. Every demo that loads a sample into a field or types into one
was unassertable, and had been since the guard was written.

```js
for (const root of roots)
  for (const f of root.querySelectorAll("input, textarea"))
    if (f.value) text.push(f.value);
```

The change only ever **adds** to what `expect` can see, so no existing assertion
can break. The trade-off is that a step could now satisfy its own assertion with
text it just typed — the same shape as the caption problem the original comment
warns about. All 24 demos were checked programmatically; none does this, and the
comment records it.

### 7.4 Second guard catch in the same chapter

Step 7 asserted `direct_override`; the badge renders `category.replace("_", " ")`
→ "direct override". Narration right, assertion wrong.

**Both aborts were cheap** — one stopped before any check ran, the other after
one. An assertion that fails early costs almost nothing; a clip that ships a
false claim costs a re-record and, if unnoticed, a viewer's trust.

---

## 8. The coverage picture

| Part | Coverage | Was |
|---|---|---|
| Part 1 · ML Pipeline | 11 / 11 | 11 / 11 |
| Part 2 · Language & Documents | **4 / 4** | 2 / 4 |
| Part 3 · Computer Vision | 0 / 14 | 0 / 14 |
| Part 4 · Security & Trust | **9 / 21** | 8 / 21 |
| **Total** | **24 / 50** | 21 / 50 |

Counted from the tree, not from the last log. Note the handbook's slug generator
truncates long anchors — chapter 34's is `ch-34-browser-extension-permission-risk-analyz`
— so a naive match against the contents undercounts by one.

---

## 9. Part 3 is blocked, and not on effort

`scripts/record-demo.mjs` line 130:

```js
const browser = await chromium.launch();   // headless, bundled Chromium
```

Headless Chromium renders WebGL as blank on this machine — already established in
memory. Depth Parallax, the strongest visual candidate in Part 3, is entirely
WebGL and would record as an empty canvas.

Recording it needs `chromium.launch({ channel: "chrome", headless: false })`.
That is a small change but it alters how **every** demo records, so it needs
verifying against an existing clip before being trusted. Treated as its own task,
not part of a chapter.

---

## 10. What a demo is actually for

Three chapters, three real defects found — the page-per-chunk limit, the
similarity-ceiling drop, the `expect` blind spot — plus a shipped bug fixed on the
way in (`a3a8b8e`: the optuna AI panel was being handed
`undefined=0.8114, undefined=0.7902`).

None of those came from reading code. They came from planting a known answer in a
document and believing the disagreement.

**Building a demo is a testing activity that produces a video as a by-product.**
That is the honest case for continuing, and also the reason the marginal clip is
worth less than the early ones: the tools most likely to be hiding something have
mostly been walked through now.

---

## 11. Recording recipe (unchanged)

```
NEXT_PUBLIC_ML_UNIFIED_URL=https://wram1708-ml-unified.hf.space \
NEXT_PUBLIC_ML_SQL_URL=https://wram1708-ml-sql.hf.space \
  npx next build && npx next start -p 3300
DEMO_BASE_URL=http://localhost:3300 node scripts/record-demo.mjs <demo>
```

Port **3300** is required — `security/origin_policy.py` rejects any other Origin.
Frame review at **88%**, one frame per step, read against that step's `say`.

---

## 12. Still open

- **Five left on the Part 4 shortlist**, in recommended order: Adversarial
  Robustness Lab, SIEM Alert Triage, Binary Byte-Plot & Entropy Triage, QR
  Phishing Detector, Attack-Surface Scanner. **The last three cost nothing** —
  local or live DNS, no API spend.
- **Part 3 needs the headed-Chrome recorder change first** (§9).
- **`QueryResultPanel.tsx` (403) and `UserGuideModal.tsx` (403)** — still over the
  400-line limit. Pre-existing, worked around three times now.
- **A pre-existing lint error** in `document-intelligence/DocHistory.tsx:44`
  (setState synchronously within an effect). Verified present on HEAD before this
  session's changes; not touched.
- **The hosted TTS path** has still never run against a live paid vendor.
- **No site-wide emoji-as-icon audit.**
- **The stale plan file** at `~/.claude/plans/plan-multimodal-rag-curious-charm.md`
  (§4) — safe to delete.
- Three untracked `test_*` files in the ML-Unified root — still the owner's call.

---

## 13. Cleanup done

The reconciliation work left six uploads on the Space across probes and takes;
all six were deleted by name and `/rag/uploads` returns `{"sources":[]}`. Document
Intelligence stores nothing beyond a 24-hour in-memory cache. The prompt injection
tool stores nothing at all.

---

## 14. After the log — the two plan files, deleted

Written up after §13 was committed (`abec086`), so this section is appended
rather than woven in.

### 14.1 What was deleted

Both files in `~/.claude/plans/`, leaving that directory empty:

| File | Written | What it was |
|---|---|---|
| `plan-multimodal-rag-curious-charm.md` | 2026-08-28 23:08 | the App Safeguard Plan (§4) |
| `plan-multimodal-rag-curious-charm-agent-a910e50e588d79f52.md` | 2026-08-28 23:07 | a subagent's `slowapi` verification plan |

The second one was not in §4's write-up. It surfaced only because the deletion
was verified with an `ls` rather than assumed, and it was one minute older than
the file it belonged to.

### 14.2 Why the second file existed, and why that is worth knowing

The `-agent-<hash>` suffix marks a **subagent's own plan file**. It exists
because of a specific collision: the safeguard planning needed to know whether
`slowapi` was safe to adopt, and the honest way to find out is to install it —
but **plan mode is read-only**, so the check could only get halfway.

The half that ran is the half that mattered:

> `slowapi` 0.1.10 — pure-Python wheel. `limits` 5.8.0 — also pure Python.
> **No compiler toolchain invoked.**

That is what made `slowapi` the safe pick over hand-rolled throttling: a package
needing a C compiler is a real risk on a HF Space build. The rest of the file —
start a scratch server, fire five rapid requests, confirm `200,200,200,429,429`
— was parked as a resumable recipe and never needed, because implementation
started and `rate_limit.py` now runs the real version of that test in production
at `LLM_LIMIT` = `10/minute`.

**The general shape, worth recognising again:** plan mode produces artifacts that
look like open work but are actually paused *verification*. They go stale the
moment the thing they were verifying ships, and nothing deletes them.

### 14.3 A claim corrected

Recommending the second deletion, this session said the pure-Python wheel
finding was "already recorded in `project_app_safeguards_shipped.md`". **It was
not** — that memory listed the shipped modules and `LLM_LIMIT`, but not the
wheel evidence or the versions.

Caught before the file was gone for good and added to that memory, which is now
the only copy. Deleting the last record of a finding while claiming it is stored
elsewhere is a cheap mistake to make and an expensive one to discover later.

---

## 15. Memory written this session

| File | Status | Why |
|---|---|---|
| `project_demo_clip_audit.md` | updated | recount to 24/50; the `expect` value fix; index-vs-name rule (4th statement); page-chunking trap; Part 3 WebGL blocker |
| `project_app_safeguards_shipped.md` | **new** | the plan file read like a to-do list; now carries the slowapi/limits wheel evidence too (§14.3) |
| `feedback_withdraw_stale_recommendations.md` | **new** | the §3 lesson — my suggestions are not the owner's backlog |

Both new files indexed in `MEMORY.md`.
