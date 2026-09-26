# Part 297 — Accessing the API docs, public-repo safety, and a full secret sweep

Continues [Part 296](Session_2026-09-24_ApiQuestionCoursesAndTheStackMap_Part296.md).
2026-09-26. A no-code, verification-heavy session: showed the user how to reach the
auto-generated FastAPI docs, answered whether public endpoints are safe, and ran a
full git-history secret sweep of both repos. Everything landed as new sections in
`TECH_STACK.md`. No app code changed, nothing deployed.

The through-line: **the security of a public API isn't in hiding endpoints — it's in
protecting them and keeping real secrets out of git. Verify both with evidence.**

---

## 1. Accessing the FastAPI docs

The user knew `<url>:<port>/docs` locally but asked how to reach the deployed docs.
Confirmed from the code that none of the three services disable docs (`docs_url` at
default), so `/docs`, `/redoc`, `/openapi.json` are all live. curl'd the live Space:
both `/docs` and `/openapi.json` return **200**.

- The port only appears **locally**; on a real domain it's implied (443) and drops
  out — use domain + `/docs`.
- Live: `https://wram1708-ml-unified.hf.space/docs` (+ `/redoc`, `/openapi.json`).
- Local: `uvicorn app:app --reload --port 8000` → `http://localhost:8000/docs`.
- `ml-sql` / `ml-vision` have their own `/docs` at their own URLs.

Written into `TECH_STACK.md` (commit `b765fc8`).

---

## 2. Is it recommended to push endpoints to a public repo?

Answer: **yes** — and ML-Unified is already public + AGPL by design.
- Hiding endpoint paths is security-through-obscurity and pointless here: the public
  `/openapi.json` already lists every route. The repo reveals nothing the live API
  doesn't.
- Security lives in **protection**, not concealment: Turnstile + rate limits, CORS
  allowlist (was `*`, now locked down — confirmed in `app.py`), Pydantic validation,
  no secrets in responses.
- The real rule: **secrets never in the repo** — they live in Vercel env / HF Space
  secrets. If one is ever committed, rotate immediately (history keeps it).

---

## 3. Full secret sweep of both repos (the verification worth keeping)

gitleaks isn't installed locally, but it **runs in CI on both repos**. Ran a manual
full-history sweep anyway, reporting filenames/counts only and redacting every value.

- **Scope:** 1,087 commits (ML-Unified) + 1,140 commits (ml-portfolio) = 2,227.
- **Result: no real credentials anywhere in history.**
- **Only matches** are intentional sample data inside the security tools that exist
  to *detect* secrets:
  - `jwt-analyzer/JwtAnalyzerRunner.tsx` — `SAMPLE_WEAK` / `SAMPLE_STRONG` demo JWTs.
  - `malicious-package-scanner/PackageScannerRunner.tsx` — `const awsKey = "AKIA…"`.
- **The AWS sample is the canonical AWS docs example key** (`AKIA…EXAMPLE`), which
  gitleaks and GitHub push protection explicitly **whitelist**. So the "split
  secret-shaped test data" convention does **not** apply — splitting it would add no
  value and make it less recognizable. Left as-is (correct).

Written into `TECH_STACK.md` as a "Public repo & secrets posture" section
(commit `cb92b05`).

---

## Commits (all docs-only, no deploy, no HF upload)

| Commit | What |
|---|---|
| `b765fc8` | TECH_STACK.md — how to access the auto-generated API docs |
| `cb92b05` | TECH_STACK.md — public repo & secrets posture (sweep verified clean) |

---

## Lessons

- **Verify the docs endpoint before pointing someone at it.** Checked `docs_url`
  wasn't disabled and curl'd a live 200 rather than assuming `/docs` was on.
- **"Is it safe to be public?" is answered by a scan, not an opinion.** Swept 2,227
  commits and classified every match instead of asserting the repos were clean.
- **Know when a convention does NOT apply.** The split-literal rule targets
  false-flag-prone fakes; the official `…EXAMPLE` key is already scanner-safe, so the
  right call was to change nothing. Checked the exact value before recommending.
- **Never print a matched secret.** The whole sweep redacted values and reported only
  file/count, even for fakes.
