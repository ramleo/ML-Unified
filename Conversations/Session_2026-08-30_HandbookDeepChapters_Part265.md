# Session 2026-08-30 (Part 265) — the handbook's deep chapters, 39 of 50 written

Continues Part 264 / 264b
(`Session_2026-08-30_HandbookBookAndDeepDocsPlan_Part264.md`), which holds the
original plan, the chapter template, the code map and the standing decisions.
Read that first — this log records only what changed after it.

---

## 0. Where things stand in one paragraph

Every one of the 50 tools has a chapter in the book. **39 now carry a deep,
hand-written chapter** explaining how the tool actually works; the remaining 11
carry only the short in-app guide they already shipped. All 39 are committed and
pushed. The work stopped mid-run because the owner flagged the token burn rate,
and a decision on how to finish the last 11 is open.

---

## 1. The numbers

| | |
|---|---|
| Tools in `capabilities.ts` | 50 |
| Chapters in the book | 50 |
| **Deep chapters written** | **39** |
| Remaining | 11 |
| `public/handbook.md` | ~1,400 lines, roughly 700 KB |

Coverage by area, all verified by script against the real files:

| Area | Deep chapters | Left |
|---|---|---|
| ML Pipeline | 11 of 11 | 0 |
| Language & Documents | 4 of 4 | 0 |
| Computer Vision | 14 of 14 | 0 |
| Security & Trust | 10 of 21 | **11** |

---

## 2. Commits this session, newest first

| Commit | What |
|---|---|
| `6cfa73b` | Phishing Classifier, SIEM Triage, QR Phishing Detector |
| `f24bd5b` | DNS Tunneling, Malicious Package Scanner, Attack Surface |
| `af0c035` | YARA, TLS/Headers, Email Auth, Password Audit |
| `064ad25` | PPE, ASL, Movement Form — Computer Vision complete |
| `e0ad636` | Video Tracking, Gait, Astro Anomaly, Wildlife Re-ID |
| `4a05a78` | Real-Time Analytics, Crime Scene, Plant Growth, Photo Search |
| `6f301ad` | all four Language & Documents tools |
| `7b27397` | Text-to-Image, Face Liveness, Depth Parallax, Pose VJ |
| `6da6629` | Pipeline Builder, Pipeline Cinema |
| `24ccc36` | Feature Selection, Ensemble, Drift |
| `1eaf10e` | colour for the parts of the book that were still grey |
| `d9c5179` | preprocessing has 4 steps, not 5 |
| `7fed136` | repaired the reading page, gave the book its colour |
| `fb43cf6` | restored list markers, corrected two card descriptions |

All pushed to `github.com/ramleo/ML-Portfolio`.

---

## 3. UNCOMMITTED — one file

`docs/chapters/prompt-injection-playground.md` — written, complete, not
committed. It is the 40th chapter. Committing it is nearly free.

---

## 4. The 11 tools still without a deep chapter

All Security & Trust:

`ai-code-detector` · `keystroke-biometric-auth-risk` ·
`adversarial-robustness-lab` · `captcha-hardening-lab` · `malware-image-triage` ·
`face-deanonymization-demo` · `video-keystroke-inference` ·
`extension-permission-analyzer` · `face-cloak` · `style-cloak` ·
`prompt-injection-playground` *(written, uncommitted — see §3)*

So committing §3 leaves **10**.

**Half-read when work stopped:** the AI Code Detector. Its stylometry lives in
`src/app/tools/ai-code-detector/stylometry.ts` — signals are comment density,
generic names, boilerplate explanatory phrasing, formal docstrings, and absence
of mess with mechanically uniform spacing; the overall label is
`several`/`few`/`none` at 3+/1+/0 signals, deliberately never a probability. The
backend (`routers/ai_code_detector.py`) adds one LLM opinion on a fixed server
key whose prompt is written to answer "inconclusive" unless a tell is clear.
The module docstring's own line is the chapter's spine: *no peer-reviewed
benchmark validates a reliable general-purpose AI-vs-human code detector.*

---

## 5. THE OPEN DECISION — how to finish

The owner stopped the run: **21% of usage in about 10 minutes.**

No agents were used at any point. The cost is the method: for each chapter, read
the tool's real frontend and backend source (4–6 file reads), then write roughly
1,800 words. Times 39.

Three options were put to the owner and **none has been chosen yet**:

1. **Stop at 39/40.** The remaining tools keep their in-app guides in the book.
2. **Shorter chapters for the rest** — about half the length, less code reading:
   the mechanism and the interview questions, without the full
   limits-and-rationale treatment.
3. **Carry on as-is** — roughly another 20% of usage.

Recommendation given: option 2 to finish, option 1 if the last ten are
low-value.

**The lesson to carry forward: flag the burn rate BEFORE starting a long
repetitive run, not 21% into it.**

---

## 6. What each chapter contains

The 7-point template from Part 264 §5, unchanged: what problem it solves; how it
works step by step; the model or algorithm; why these choices; how to read the
output; limits; likely interview questions with worked answers.

Two conventions held throughout:

- **Written from the code, never from the card.** Where they disagreed, the
  chapter describes the code and says the card is wrong.
- **Recorded failures are the most valuable content.** Every module docstring in
  this codebase that admits a rejected approach, a measured negative result or a
  disclosed limitation went into its chapter, with the numbers.

---

## 7. Findings worth keeping (a sample — each is in its chapter)

- **Feature Selection's "mutual information"** is `-0.5*log(1-r^2)` from a
  Pearson correlation — linear dependence only. Its "trees" are single stumps,
  its RFE never refits a model, and exhaustive search silently becomes forward
  selection above 15 columns.
- **The Ensemble page does not ensemble.** It runs the competition and reports
  diversity; voting and stacking are a Pipeline Builder stage.
- **Drift's baseline is not the training data** — a mean and standard deviation
  recovered from the fitted scaler, so every numeric test compares the batch
  against a Gaussian and the KS test draws 2,000 synthetic normal samples.
- **Text-to-Image's `generationConfig.seed` is accepted and does nothing** — two
  calls, same prompt and seed, different SHA-256 and different byte length.
- **Face Liveness returns a score, not a verdict**, because a live face scored
  52% "spoof" in dim light. The card's 98.2% is CelebA-Spoof's number.
- **ASL: rotation normalisation was tested and rejected** — held-out accuracy fell
  75.5% → 67.8%, because orientation carries real signal. k=1 beat k=3.
- **Astro: the meteor/satellite label is refused** — motion along a line is
  geometrically indistinguishable from no motion, tested against synthetic
  ground truth.
- **Attack Surface matches file content, not status codes**, because a large
  share of sites return 200 for everything; two checks use real magic bytes.
- **TLS reports an expired certificate as "critical issues", not "could not
  fully scan"**, even though the expired cert is what blocked the header fetch.
- **Phishing Classifier's real risk is training-serving skew** — the tokenizer
  exists in Python and in TypeScript, and a mismatch degrades accuracy with no
  error raised.

---

## 8. Also done this session, before the chapters

Recorded in Part 264b but repeated here because it is easy to lose:

- **The reading page was broken and is fixed.** `.hb-body h1 { display: none }`
  had hidden all 48 chapter, part and appendix titles; `.hb-body em` styled 233
  italic phrases as uppercase eyebrows; `thead { display: none }` removed the
  header from 49 tables to spare one.
- **The book has colour**, one per part, taken from `src/data/domains.ts` so it
  cannot drift from the site. Structure only — rules, numbers, table headings,
  folios, the appendix, the contents. Body text stays black.
- A `@page` margin box cannot read a custom property, so per-part folio colour
  needs a **named page** per part. That forces a break where the name changes,
  which is why the name is claimed by `.bk-part.bk-part-N` and not
  `.bk-part-N` alone, and why `.bk-partpage`'s own `break-before` had to go —
  the two together left four blank leaves. 139 pages → 135, none blank.
- **`preprocessing`'s "5 Steps" was wrong** and is now 4 — the count came from an
  old card description listing five operations, two of which never existed.

---

## 9. Commands

```bash
python3 scripts/build-handbook.py     # regenerate; CI fails if the .md is stale
npx next build
./scripts/check-file-length.sh        # 400-line gate
```

Coverage audit:

```python
import re, pathlib
root = pathlib.Path("."); src = (root/"src/data/capabilities.ts").read_text()
ids = re.findall(r'^    id: "([^"]+)"', src, re.M)
deep = {i for i in ids if (root/f"docs/chapters/{i}.md").exists()}
print(len(ids), len(deep), sorted(set(ids) - deep))
```

**Chapter files are named by capability id, not route** — `featureeng.md`, not
`feature-engineering.md`. Two ids differ from their route.

---

## 10. Standing constraints (unchanged)

- Ask before every `git commit`, in both repos.
- **Never spawn a subagent without asking.** None were used this session.
- Only delete files created this session, named explicitly.
- No file over 400 lines, every extension. `.md` is not gated.
- Use simple words.
- HF Space upload after any commit touching `services/ml-api/**`. No commit this
  session touched it.
