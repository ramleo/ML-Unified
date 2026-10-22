Chapter 21Contract/Invoice Reconciliation Assistant


> Upload a contract, then the invoices billed against it, and see where they disagree. Mismatched amounts, dates and terms are flagged with both source passages side by side and an explanation of the conflict. Invoices are only ever checked against the contract, never against each other — they are supposed to differ.

## At a glance

| | |
|---|---|
| **Also called** | Discrepancy Report Across Documents |
| **Model or method** | Cohere / Mistral / Gemini |
| **What you give it** | PDF, PNG, JPG (contract + invoices) |
| **Doc Roles** | 2 |
| **Where it runs** | On the server |
| **Find it at** | `/tools/contract-invoice-reconciliation` |

## Using the tool

Upload a contract, then one or more invoices. This tool compares them and flags
places where an invoice states a different amount, date, or term than the
contract does — a discrepancy report, not a general chat.

### How it works

- The **first document you upload defaults to the contract**; every document after
  that defaults to an invoice. Click the role pill on any document chip ("Contract"
  / "Invoice") to flip it if that's wrong — for example if you uploaded an invoice
  first.
- Once you have exactly one contract and at least one invoice, click **"Check for
  discrepancies."** The tool compares the contract against every invoice
  individually — invoices are never compared against each other, since different
  invoices are supposed to differ from one another (that's not a discrepancy).
- Each flagged discrepancy shows the contract clause and the invoice line
  side-by-side, a short explanation of what disagrees, and a match-confidence
  percentage (how topically related the two passages are — not how confident the
  discrepancy itself is).
- Every flagged discrepancy is double-checked by a second, independently-worded
  pass. If that second check disagrees, the discrepancy still shows (nothing is
  ever silently hidden) but is marked **"Unconfirmed"** — worth reading the two
  passages yourself before trusting it.

### What it's good at

Numeric and date mismatches are the strongest case: "contract says \\$50,000,
invoice bills \\$52,500," or "contract says net-30, invoice says net-45." The tool
prioritizes checking passages that contain a detected amount or date first, since
those are the most likely genuine discrepancies.

### Limitations, honestly

- It only checks a bounded number of contract/invoice passage pairs per request
  (the same small budget the underlying contradiction-detection engine always
  uses) — a very long contract with many clauses may not have every clause
  checked against every invoice line in one pass.
- It reads free text, not structured line-item tables — a contract with a complex
  itemized schedule may not compare as cleanly as a simple "total amount due"
  clause.
- "No discrepancies found" means none were detected within what was checked — not
  a guarantee the documents fully agree everywhere.
- The confirmation pass reduces, but can't eliminate, false positives — two
  passages that state the same value in different wording ("30 days" vs. "30
  days from issue") have been observed to get flagged. It can also occasionally
  mark a genuine discrepancy "Unconfirmed" rather than dismiss it outright; this
  tool is built to surface a report for you to review, not to decide anything on
  its own.

## What problem it solves

A contract says the work costs £50,000, payable within 30 days. Three months
later an invoice arrives for £52,500, due on receipt.

Somebody has to notice. In practice that means a person holding two PDFs side by
side, reading a forty-page agreement and a two-page invoice, and comparing every
figure — for every invoice, against every contract. It is exactly the work people
stop doing carefully after the fifth one, and it is where overbilling survives.

This tool reads both and reports where they disagree. Not a summary of either —
a list of specific pairs of passages that name the same thing and state
different values for it, each with its page number.

## How it works, step by step

1. **Upload the contract and one or more invoices** into the same session.
2. **Take every chunk** of the contract and every chunk of the invoices.
3. **Pair contract chunks with invoice chunks only** — never invoice against
   invoice, never contract against contract.
4. **Score every pair by embedding similarity** and keep the ones in a band —
   similar enough to be about the same thing, not so similar as to be the same
   sentence.
5. **Rank the survivors,** putting pairs that contain a money or date entity
   first.
6. **Judge at most six of them.** One model call per pair: do these state a
   different *value* for the same thing?
7. **Re-check anything flagged,** with a differently-worded question.
8. **Report** each discrepancy with both passages, both page numbers, the
   similarity, an explanation, and whether the second check agreed.

## The model or algorithm

### A two-stage funnel, and why it has to be one

The naive approach is to ask a model about every pair of chunks. A forty-page
contract and three invoices is easily 200 × 60 = 12,000 pairs. At one call each
that is unaffordable, slow, and mostly wasted — the overwhelming majority of
pairs are about unrelated things.

So the pipeline is **cheap first, expensive last**:

**Stage 1 — embedding similarity, free.** The embedder is already loaded for the
RAG pipeline, so scoring every pair costs nothing but arithmetic. Pairs are kept
only inside a band:

| Threshold | Value | What it removes |
|---|---|---|
| `_SIM_FLOOR` | **0.45** | pairs about different topics — nothing to compare |
| `_SIM_CEILING` | **0.93** | near-duplicate text — trivially agrees, not worth a call |

Both were **calibrated against real `all-MiniLM-L6-v2` embeddings rather than
guessed**, the same discipline as the groundedness thresholds in the Multimodal
RAG chapter. The ceiling is the less obvious one and it is doing real work:
identical boilerplate appearing in both documents is a perfect match and a
completely useless comparison.

**Stage 2 — an LLM judge, capped at six calls.** `_MAX_PAIRS_TO_JUDGE = 6`,
regardless of how large the documents are. The cost of a reconciliation run is
therefore bounded by a constant, not by the size of the upload.

### Ranking decides what those six calls are spent on

Since only six pairs get judged, which six matters more than anything else. The
sort key is:

```python
candidates.sort(key=lambda x: (has_numeric_entity, similarity), reverse=True)
```

**Pairs containing a money or date entity come first**, ahead of pairs that are
merely more similar. The entities were already extracted at ingest, so this
costs nothing — and it encodes the actual domain knowledge: a reconciliation
discrepancy is almost always a *number* or a *date*, so a pair with no figure in
it is unlikely to be worth one of the six calls however similar it looks.

### The narrower question — and the false positive that produced it

There is a general contradiction detector in this codebase already, and
reconciliation could have reused its prompt. It does not, and the reason is
recorded from live testing.

A contract and an invoice are *supposed* to differ across most of their text —
different structure, different boilerplate, different purpose. Given a generic
"do these disagree?" prompt, a small model flagged:

> contract: *"due within 30 days of invoice date"*
> invoice: *"Due date: 30 days from issue"*

as a disagreement. Both state the same 30-day term. **The model was
pattern-matching on differing phrasing rather than comparing the underlying
value.**

So the reconciliation prompt is written against that specific failure. It names
the roles — *"Passage A is a clause from a CONTRACT. Passage B is a line from an
INVOICE"* — asks for a different **value** for the same amount, date, quantity or
term, gives a worked example of a real discrepancy (contract says $50,000,
invoice bills $52,500), and then gives the **counter-example above in full**,
spelled out as *not* a discrepancy, ending with: *"Judge the underlying value,
not the phrasing."*

The comment in the code says the quiet part: *"Spelling that exact failure mode
out is doing real work here, not decorative."* A worked negative example is
usually worth more than another rule.

### The confirmation pass, and what it is not allowed to do

A single small-model judgement is noisy. So any pair flagged positive gets **one
independent re-check**, with the question worded differently — *"a first pass
flagged these; double-check carefully: different value, or same value in
different words?"*

This only doubles the calls for pairs already flagged, not for the whole judged
set.

The important design decision is what happens when the two calls disagree. The
obvious move is to drop the flag. The code deliberately does not:

> *"Never silently drop a flagged pair on confirm_fn's say-so alone — live
> testing showed BOTH calls can independently miss the same real discrepancy
> (the small judge model is noisy in both directions, not just toward false
> positives), and this report exists for a human to review, not to act on
> unattended. A disagreement is surfaced as `confirmed: false` instead, so the
> reader can weigh it themselves rather than have it vanish."*

That is the correct instinct for a review tool. The system's job is to put
candidates in front of a person, and **suppressing a finding is a more expensive
error than showing an uncertain one.** The uncertainty is passed through as a
field rather than resolved by a coin flip.

### Contract-against-invoice pairing only

Invoice-versus-invoice comparison is excluded by construction, and the reason is
in the code: **different invoices are supposed to differ.** Two invoices for
different months naming different amounts is correct behaviour, and a generic
contradiction detector reports it as a finding — which is how a tool trains its
user to ignore it. Restricting the pairing to the comparison that has meaning is
what makes the output worth reading.

### Injected dependencies

`find_contradictions` and `find_reconciliation` take `embed_fn`, `judge_fn` and
`confirm_fn` as arguments rather than importing the embedder and provider
themselves. They depend on two contracts — `texts → embeddings` and
`(a, b) → verdict` — and nothing else, so a stronger judge or a different
embedder swaps in without touching the logic. That is dependency inversion used
where it actually pays: the judge model is the part most likely to change.

### Cost controls

The judge runs on a **fixed, server-key-only provider** — Mistral
`mistral-small-latest`, chosen because it is the proven-reliable fallback in
this app after Groq was dropped from the default path. It deliberately does not
share the rate-limit budget the user's own chat answers use: *a background
quality check must not consume the budget the foreground feature needs.* There
is also a daily call cap on top.

## How to read the output

- **Every discrepancy shows both passages and both page numbers.** Read them,
  not the explanation — the explanation is a small model's one-sentence summary.
- **`confirmed: false` means the two judge calls disagreed.** Weigh it yourself.
  It is shown rather than hidden on purpose.
- **`checked_pairs` tells you the denominator.** Six is the ceiling, and a run
  that judged six pairs on a long contract has looked at a small slice.
- **Nothing found is not proof of nothing.** With at most six judged pairs, a
  clean report means "no discrepancy in the six most promising comparisons".
- **Similarity is context, not evidence.** A high number means the passages are
  about the same subject, not that they conflict.
- **The tool finds mismatches, not omissions.** An invoice for work that was
  never in the contract at all has no similar contract chunk to pair with.

## Limits

- **At most six judged pairs per run,** whatever the document size. This is the
  binding limit and it is a cost decision, not an accuracy one.
- **A small judge model, noisy in both directions.** The confirmation pass
  reduces false positives; the code is explicit that both calls can also miss a
  real discrepancy.
- **Only same-session uploads are compared.** The knowledge base and other
  sessions' documents are excluded.
- **One contract per run**, against one or more invoices.
- **Chunk-level comparison.** A discrepancy spread across two clauses in
  different parts of the contract will not surface as one pair.
- **Similarity thresholds are fixed** and calibrated for one embedding model.
- **No arithmetic.** It does not total line items or recompute a balance — that
  is the Document Intelligence tool's job. This compares statements.
- **A review aid, not a control.** The output is for a person to check.

## Likely interview questions

**"Why not just ask the model to compare the two documents?"**
Context limits, cost, and precision. A forty-page contract and three invoices
will not fit reliably, and even where they do the model's attention over a long
context is uneven, so it misses things. Chunking and pairing means every part
gets compared explicitly rather than depending on the model to notice. And the
funnel bounds the cost — embedding similarity over 12,000 pairs is free, six
judge calls is affordable, 12,000 judge calls is not.

**"How do you decide which pairs to spend a model call on?"**
Two filters and a sort. A similarity band — above 0.45 so the passages are about
the same thing, below 0.93 so they are not the identical boilerplate — then sort
by whether the pair contains a money or date entity *before* sorting by
similarity. The entities are already extracted at ingest so it is free, and it
encodes the domain fact that a reconciliation discrepancy is nearly always a
number or a date.

**"You had a false positive. What did you do about it?"**
The model flagged "due within 30 days of invoice date" against "Due date: 30
days from issue" — the same term, different wording. It was pattern-matching on
phrasing rather than comparing values. I rewrote the prompt to name the document
roles, ask specifically for a different *value* for the same thing, and include
that exact pair as a worked counter-example labelled *not* a discrepancy. Then I
added an independent second call with a differently-worded question for anything
flagged. A worked negative example did more than another rule would have.

**"Why show a finding the confirmation pass rejected?"**
Because the two error directions are not equally costly. This is a review tool —
a human reads the output — so a false positive costs someone thirty seconds and a
suppressed true positive costs an overpaid invoice. Testing showed both calls
can independently miss the same real discrepancy, so the second call is not an
oracle. Surfacing the disagreement as a field lets the reader weigh it; deciding
it silently would be the system pretending to a certainty it does not have.

**"Why not compare invoices against each other?"**
Because different invoices are supposed to differ — different months, different
amounts, different line items. A generic contradiction detector reports every
one of those as a finding, and a tool that reports mostly noise gets ignored.
Restricting the pairing to contract-against-invoice is what makes the report
worth reading, and it was a real fix to a real false-positive problem, not a
simplification.
