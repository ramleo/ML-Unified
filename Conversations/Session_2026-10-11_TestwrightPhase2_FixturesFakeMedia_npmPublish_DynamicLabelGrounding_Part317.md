# Part 317 — Testwright Phase 2: fixtures + fake-media, npm publish, and the dynamic-label grounding fix

Continues [Part 316](Session_2026-10-11_AnalyticsUIRedesign_MockupToLivePort_GeoMap_SearchPrecision_Part316.md).
2026-10-11. "Do Phase 2" — the one parked Testwright item: make the **~34 upload/camera tools
testable** (fixtures + fake-media), plus the Run-Live **installer** and a **VS Code extension**.
All three shipped and verified live. Then a long, honest debugging arc on the user's own
**Real-Time Analytics** dashboard surfaced the real reason generated tests kept failing — and
ended in one consolidated grounding fix.

Through-lines:
- **"Testable" means a green test on the real runner, not just "the mechanism runs."** Proven with
  a live EDA CSV-upload test and a face-liveness camera test, both passing.
- **Deterministic beats a prompt the weak model ignores.** The free model kept emitting bad
  assertions/locators even when told not to; each real fix was a regex transform, not a prompt plea.
- **Stop patching symptoms — name the class.** Three "layers" of analytics-test failure were one
  root cause: the dashboard bakes *changing* values into control names.

---

## Arc 1 — fixtures + fake-media (the unlock)
~34 tools need a file upload or a camera before they do anything, so they were untestable (no file;
CI has no camera). Fix across three repos, deployed once, verified once:
- **`ml-qa-runner/fixtures/`** (+ companion copy) — small samples `sample.{csv,png,jpg,pdf,wav,mp4,txt}`
  + `fake-camera.y4m` + `fake-audio.wav` (~192K). `qa-run.yml` now **sparse-checks-out** `fixtures/`
  (it had **no checkout** before) and launches Chromium with `--use-fake-ui/-device-for-media-stream`
  + `--use-file-for-fake-video/audio-capture` (guarded by `fs.existsSync`). `--use-fake-ui…`
  auto-accepts the camera prompt, so a test just clicks capture — no permission boilerplate.
- **backend** — Discover captures each page's `input[type=file]` (accept + label) in the explore spec;
  new **`fixtures.py`** (catalog + single source of truth) turns them, plus a camera-control scan,
  into a `===MEDIA===` grounding block → `setInputFiles('fixtures/<name>')`. Author rule `14-media`,
  Discover rule `3a`. All HF-uploaded.
- **Verified live:** EDA CSV-upload test (`setInputFiles` + `toHaveValue`) ✓; face-liveness camera test
  (`Start camera` → button hidden = `getUserMedia` resolved on the fake stream) ✓ — both **pass green**.

A robustness fix fell out: the free model (Cohere) ended upload tests on a false `toBeHidden()` of a
permanent description paragraph it mistook for an empty-state → `strip_upload_assert_noise` drops that
and any visibility assertion on a hidden file input, keeping `setInputFiles`+`toHaveValue`.

## Arc 2 — Run-Live installer + VS Code extension
- **Launchers** (`companion/launchers/`): double-click `.command`/`.bat`/`.sh` → `npx @airaml/…`.
  Companion `v0.2.0`, `files` allowlist. README: three ways to start.
- **VS Code extension** (`vscode-extension/`): editor ▶ "Run this test (headed)" writes a throwaway
  project (fake-media config + bundled fixtures + the active spec) and runs `playwright test --headed`.

## Arc 3 — npm publish journey (companion → live for everyone)
Run-Live worked **only for the owner** until published (npx fetched nothing — the package was never on
npm). Publishing it, with the user driving the terminal:
- `npm publish` → **ENEEDAUTH** (not logged in) → `npm login`.
- → **E403: 2FA required to publish.** User didn't want an authenticator app → used a **passkey /
  Touch ID** (WebAuthn security key) as the second factor — no app needed.
- → **E404 "Scope not found"** → created the **`airaml` npm org** (free public plan).
- → `+ @airaml/testwright-companion@0.2.0` → **LIVE** (`npm view` confirmed after a few min propagation).
VS Code extension packaged to `.vsix` and installed via **Extensions ▸ … ▸ Install from VSIX** (the
`code` CLI wasn't on PATH; the GUI install sidesteps it). Left local, not Marketplace-published.

## Arc 4 — the analytics-test failures → one consolidated grounding fix
The user tested the Real-Time Analytics dashboard and tests kept failing. Two separate issues:
1. **"The failure wasn't logged."** It wasn't a website error — the test timed out on a **locator**.
   Three distinct logs were being conflated: the **Activity Log** = LLM calls only; the **Errors/Page
   Inspector** = real JS crashes + 500s (global `window.error` handler); **QA dashboard** = test
   pass/fail. A test failing to find a button is a *test* result, not a *site* error — so correctly in
   none of the error logs. (Also owned a wrong claim: "'30 days' doesn't exist" — it does; the first run
   just never navigated off the homepage.)
2. **Why the test kept failing — ONE root cause, three faces.** The dashboard bakes **values that change
   as you use it** into control/heading names. I patched each face separately (whack-a-mole), which the
   user rightly called out:
   - card titles are `<p>`, not headings, but the model typed `getByRole('heading')` → **nothing matches**
     (`fix_invented_heading_role`: rewrite to `getByText` when the context shows a paragraph).
   - headings carry a range suffix: `Activity Log — today` → `— 30d` after switching range (rule `10e-range`).
   - chips carry a **live count**: `Warnings 1` → `Warnings 3` over 30 days.
   **Consolidated fix** (`6ea5901`): **`stabilize_dynamic_control_names`** — match any getByRole/getByText
   name with a volatile tail (trailing count **or** ` — state` suffix) by its **stable prefix regex**
   (`Warnings 1` → `/^Warnings/`, `Activity Log — today` → `/^Activity Log/`); stable names and
   already-regex names untouched (verified: `30 days`, `Choose File`, `gemini-3.6-flash`, `Real-Time
   Analytics` all unchanged). Moved the name-grounding transforms to a new **`name_grounding.py`** to keep
   `locators.py` <400. **Verified green** end-to-end: `switch 30d → scroll Activity Log → click Warnings`
   passes all steps.

## Arc 5 — Run-Live watchability
A short test flashed by. Added a **Slow** toggle (`RunLiveButton`, sends `mode:"slow"`), raised slow
slowMo 600→1500ms, and a **3.5s end-of-run hold** so the final state lingers. Plus a **"why it failed"**
box that shows the real Playwright error (noise stripped) — the reason was captured but never displayed.

## Arc 6 — follow-on (2026-10-12): the user actually ran it, four real bugs fell out
Dogfooding the exact flow surfaced what unit tests didn't:
- **Run Live crashed on Node 26** — `ERR_UNSUPPORTED_NODE_MODULES_TYPE_STRIPPING`. The companion
  wrote its throwaway `playwright.config.ts` into `__dirname/.tw-run`, which under `npx` is **inside
  `node_modules`**, and Node ≥22 refuses to type-strip `.ts` there. Fix (`7ea4e11`, companion `v0.2.1`):
  run dir → **OS temp dir** (outside node_modules), **symlink** the real node_modules in so imports
  resolve, and call the Playwright **binary by resolved path** instead of relying on npx walking cwd.
  Verified by reproducing the exact write+load — config now loads, `.ts` spec is discovered.
- **"I can't see the logs."** The failure box only rendered on `passed === false`; the crash gave
  `passed === null`, so the captured output stayed hidden. Fix: show output on **any non-pass**
  (`null` crash *or* `false` fail). (`6485221`, ml-portfolio.)
- **Export test failed (1 of 6)** — `a[href="/api/events/export?range=today"]` not found after the test
  clicked "7 days". Same class as dynamic names, in the **href**: the export link's href encodes the
  selected range (`?range=${range}`), captured by Discover in the default state. Fix (`12636ef`,
  backend, HF-uploaded): **`stabilize_query_href_locators`** rewrites `a[href="/path?query"]` →
  `a[href^="/path"]` so it survives any state change. Unit-tested (real failure fixed, query-less +
  already-prefix untouched).
- **No line numbers in the Run editor** → new **`CodeEditor`** component: textarea + scroll-synced
  line-number gutter (extracted to keep `RunRunner` under the file-length limit). Verified live —
  numbers align (line-height/padding/line-count all match) and clear the gutter. (`6485221`.)

Lesson reinforced: **unit tests prove the transform; only dogfooding proves the product.** The
companion crash, the hidden-output gap, and the query-href class all needed a real run to surface.

## Key decisions / lessons
- **Deterministic transforms beat prompt pleas** for a weak free model — every real fix here was a regex
  in `name_grounding.py`/`locators.py`, not a prompt rule the model then ignored.
  [[project_testwright_run_perf]] (same TW-GROUND lesson).
- **Find the class, not the instance.** Heading-role, range-suffix and count were one problem (volatile
  values in names); one transform closed all three and the "next layer".
- **Three logs, three jobs** — don't conflate the LLM Activity Log, the website Errors log, and the QA
  dashboard. A failed test ≠ a website error. [[project_page_error_log_coverage]]
- **"Testable" is a green run on the real runner**, verified live, not "the mechanism executed."
  [[feedback_status_claims_need_evidence]]
- **npm now mandates 2FA to publish**; a passkey/Touch ID is the no-app second factor.
- File-length discipline held: `name_grounding.py` split keeps `locators.py` 260, `prompts.py` 313,
  `discover.py` 363 — all <400. [[feedback_file_length]]

## Commits
| Repo | Commits |
|---|---|
| ml-qa-runner | `76edb9a` fixtures+fake-media · `c03c0ab` launchers+VS Code ext · `5919274` slow-mode · `7ea4e11` **companion temp-dir fix (v0.2.1)** |
| ML-Unified (HF-uploaded) | `f89064d` fixtures.py+MEDIA grounding · `8894026` robust upload asserts · `3fe069f` rule 10e-range · `f1a4114` heading→getByText · `6ea5901` stabilize_dynamic_control_names + name_grounding.py split · `b998f46` docs (R14 + plan split) · `12636ef` **stabilize_query_href_locators** |
| ml-portfolio | `a741cc5` Run-Live Slow toggle · `4e5bd94` Run-Live failure-reason box · `6485221` **line-numbered editor + output-on-crash** |
| npm | `@airaml/testwright-companion@0.2.0` published + live; **`0.2.1` committed, republish pending** (fixes the Node-26 crash) |

## Open / next
- **R8 — scheduled monitoring** (run a saved test on a schedule, alert on failure): *in progress*,
  P0 locked, not built. **R5 — authenticated testing**: deferred (no logged-in app). (§9b/§9a in
  `docs/TESTWRIGHT_PHASE2_DETAILS.md`.)
- VS Code extension: local `.vsix` only; Marketplace publish not done (optional).

Related: [[project_testwright_phase2_fixtures]], [[project_testwright_qa_platform]],
[[project_testwright_run_perf]], [[project_page_error_log_coverage]], [[feedback_file_length]],
[[feedback_status_claims_need_evidence]], [[feedback_debug_first]].
