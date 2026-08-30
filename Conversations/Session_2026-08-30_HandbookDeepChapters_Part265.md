# Session 2026-08-30 (Part 265) — the handbook's deep chapters, 50 of 50 written

*Amended after the run resumed the same day and finished. The counts below are
final; §5 records how the open decision was resolved.*

Continues Part 264 / 264b
(`Session_2026-08-30_HandbookBookAndDeepDocsPlan_Part264.md`), which holds the
original plan, the chapter template, the code map and the standing decisions.
Read that first — this log records only what changed after it.

---

## 0. Where things stand in one paragraph

Every one of the 50 tools has a chapter in the book, and **all 50 now carry a
deep, hand-written chapter** explaining how the tool actually works. All are
committed and pushed. The run was paused mid-way when the owner flagged the
token burn rate; it resumed the same day, in batches of five at full depth, and
finished. The coverage audit reports no gaps.

---

## 1. The numbers

| | |
|---|---|
| Tools in `capabilities.ts` | 50 |
| Chapters in the book | 50 |
| **Deep chapters written** | **50** |
| Remaining | 0 |
| `public/handbook.md` | 1,443 lines, 863 KB |

Coverage by area, all verified by script against the real files:

| Area | Deep chapters | Left |
|---|---|---|
| ML Pipeline | 11 of 11 | 0 |
| Language & Documents | 4 of 4 | 0 |
| Computer Vision | 14 of 14 | 0 |
| Security & Trust | 21 of 21 | 0 |

---

## 2. Commits this session, newest first

| Commit | What |
|---|---|
| `3e165ae` | Face Cloak, Face Deanonymization, Style Cloak, Video Keystroke Inference, Extension Permission Analyzer — **50 of 50** |
| `50d3383` | AI Code Detector, Keystroke Biometric Auth-Risk, Adversarial Robustness Lab, CAPTCHA Hardening Lab, Malware Image Triage |
| `65a50cf` | Prompt Injection Playground (was §3's uncommitted file) |
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

## 3. UNCOMMITTED — none

`docs/chapters/prompt-injection-playground.md` was the one outstanding file when
this log was first written. It was committed as `65a50cf`. Both repos' working
trees are clean.

---

## 4. The tools still without a deep chapter — none

The eleven listed here originally were all Security & Trust:

`ai-code-detector` · `keystroke-biometric-auth-risk` ·
`adversarial-robustness-lab` · `captcha-hardening-lab` · `malware-image-triage` ·
`face-deanonymization-demo` · `video-keystroke-inference` ·
`extension-permission-analyzer` · `face-cloak` · `style-cloak` ·
`prompt-injection-playground`

All eleven are now written and committed. A coverage script that reads the tool
ids straight out of `src/data/capabilities.ts` and compares them against
`docs/chapters/*.md` reports **50 of 50, missing: NONE**.

---

## 5. THE OPEN DECISION — resolved

The owner stopped the run at **21% of usage in about 10 minutes.**

No agents were used at any point. The cost is the method: for each chapter, read
the tool's real frontend and backend source (4–6 file reads), then write roughly
1,800 words.

Three options were put to the owner:

1. **Stop at 39/40.** The remaining tools keep their in-app guides in the book.
2. **Shorter chapters for the rest** — about half the length, less code reading.
3. **Carry on as-is** — roughly another 20% of usage.

**The owner chose option 3, with one modification: batches of five, committed
between batches.** "let the chapters be detailed, do in batches of 5 chapters."
Two batches finished the job. Batching turned out to be the useful part — it
gives a natural checkpoint, a clean commit boundary, and a place for the owner
to stop the run without losing work.

**The lesson to carry forward: flag the burn rate BEFORE starting a long
repetitive run, not 21% into it.** The batch structure is the practical form of
that lesson — propose the batch size up front and let the owner set the pace.

---

## 6. Verification run after each batch

Same four checks both times, all passing:

- `python3 scripts/build-handbook.py` — regenerates `public/handbook.md`
- the coverage audit above — ids in `capabilities.ts` vs. files in `docs/chapters/`
- `./scripts/check-file-length.sh` — 627 tracked source files, none over 400
  lines except pinned debt (`.md` is not gated, which is why the chapters
  themselves are exempt)
- `npx next build` — compiled successfully

No backend files were touched in either batch, so no HF Space upload was
required.

---

## 7. What each chapter contains

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

## 8. Findings worth keeping (a sample — each is in its chapter)

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

## 9. Also done this session, before the chapters

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

## 10. Commands

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

## 11. Standing constraints (unchanged)

- Ask before every `git commit`, in both repos.
- **Never spawn a subagent without asking.** None were used this session.
- Only delete files created this session, named explicitly.
- No file over 400 lines, every extension. `.md` is not gated.
- Use simple words.
- HF Space upload after any commit touching `services/ml-api/**`. No commit this
  session touched it.
