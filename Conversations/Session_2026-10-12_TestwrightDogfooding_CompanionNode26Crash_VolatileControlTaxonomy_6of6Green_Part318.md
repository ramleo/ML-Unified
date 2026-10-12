# Part 318 — Testwright dogfooding: the companion crash, the volatile-control taxonomy, and 6/6 green

Continues [Part 317](Session_2026-10-11_TestwrightPhase2_FixturesFakeMedia_npmPublish_DynamicLabelGrounding_Part317.md).
2026-10-12. The user actually **ran** Testwright end-to-end against their own Real-Time Analytics
dashboard — Discover → Author → Run — and it surfaced a cascade of real failures that unit tests never
would. Each one became a **deterministic transform**, ending in **6/6 green**.

The one big lesson, relearned the hard way:
- **A prompt rule the weak free model ignores is not a fix.** I shipped a prompt-only rule
  (`15-livedata` / `3b`) for the live-data class; the model ignored it and still wrote
  `selectOption('ml-pipeline')` / "filter by US". The real fix was enforcing it **in code**.
  Deterministic beats prompt — again. [[project_testwright_run_perf]] (TW-GROUND), [[feedback_debug_first]].

---

## Arc 1 — the companion crashed before any test ran (Node 26)
Run Live died immediately: `ERR_UNSUPPORTED_NODE_MODULES_TYPE_STRIPPING`. The companion wrote its
throwaway `playwright.config.ts` into `__dirname/.tw-run`, which under `npx` is **inside node_modules**,
and Node ≥22 refuses to strip `.ts` types there. Fix (`7ea4e11`→`23e2115`, companion **v0.2.2**): run dir
→ **OS temp dir**, **symlink** the real node_modules in so imports resolve, call the Playwright **binary
by `require.resolve`'d path**. Verified by reproducing the exact write+load. Also surfaced a UI gap — the
"why it failed" box only showed on `passed===false`; a crash gives `passed===null`, so output was hidden
→ now shows on any non-pass (`6485221`). Plus a **line-numbered Run editor** (`CodeEditor.tsx`, extracted
to keep `RunRunner` under the limit), verified live (gutter aligns, numbers clear the text).

## Arc 2 — dogfooding the analytics page: one failure at a time, each a deterministic class
The dashboard is a *hard* target — it's built from live data. Running the Discover suite repeatedly
exposed a **taxonomy of volatile controls**, each closed with a central transform (not a per-test patch):

| Failure (live-verified) | Why it broke | Deterministic fix |
|---|---|---|
| `a[href="/api/events/export?range=today"]` not found after "7 days" | export href encodes `?range=${range}`, captured in default state | `stabilize_query_href_locators`: `a[href="/p?q"]`→`a[href^="/p"]` (`12636ef`) |
| `selectOption('ml-pipeline')` timed out | Tool `<select>` options are tools seen recently; live combobox had only `realtime-analytics` | `stabilize_data_driven_select`: `selectOption('x')`→`{index:0}`, paired `toHaveValue`→`/.+/` (`32adfe0`) |
| `getByRole('button',{name:'US'})` timed out | country chips render only when the feed has 2+ countries — **entire group absent** at run time | `guard_noop_visibility_click`: a click whose only follow-up is "still visible" → wrapped in `if (await x.isVisible())`, skips when absent (`32adfe0`) |
| `getByRole('button',{name:'Open chat'})` not found (5s) | chat launcher is `dynamic(ssr:false)`, home-page only, mounts a beat after SPA nav | expect timeout 5s→**15s** in generated configs (`23e2115`) |
| `✦ AI Explain ▼` not found after click | the disclosure caret flips `▼`→`▲` on expand — a volatile suffix in the name | extend `stabilize_dynamic_control_names` to strip a trailing caret → `/^✦ AI Explain/` (`bc1049c`) |

Every fix was **verified against the exact generated code** (pasted by the user) and **unit-tested** to
confirm it (a) fixes the failure and (b) leaves valid cases untouched — the search box's
`toHaveValue('Data Drift')`, the real `trace` click, and stable names (`30 days`, `Export CSV`,
`ML Pipeline`, `Toggle theme`) are all unchanged. **Result: 6/6 green.**

## Why this won't recur
These are classes, not instances — the transforms run in the Author post-process on **every** future
generated test, any page. The only honest caveats: a genuinely *new* kind of volatile control would be a
small addition to one central transform (not a per-test chase), and the country filter shows as **skipped**
when the live feed has <2 countries (by design — you can't click a chip the data didn't create).

## Method note (what went right after what went wrong)
- Shipped a prompt-only fix → it failed in production → **owned it**, pivoted to code enforcement.
- Then stopped guessing: **verified every cause against the live page** (combobox had 1 option; country
  chips absent; chat button is lazy/ssr:false; caret flips) *before* writing a transform.
- **Batched** the deploy (rule 5): gathered all fixes, deployed once, verified once — instead of a
  rebuild per failure (the user's time is the scarce resource).

## Commits
| Repo | Commits (this day) |
|---|---|
| ml-qa-runner | `7ea4e11` companion temp-dir fix (v0.2.1) · `23e2115` 15s expect timeout (v0.2.2) |
| ml-portfolio | `6485221` line-numbered editor + output-on-crash |
| ML-Unified (HF-uploaded) | `12636ef` query-href · `ad09126` prompt rules 15-livedata/3b (ignored by model) · `32adfe0` data-driven select + chip-guard (in code) · `bc1049c` disclosure-caret suffix |
| ML-Unified (docs) | `98c41d3` Part 317 update · (this Part 318) |

## Open / next
- **npm republish** `@airaml/testwright-companion@0.2.2` — PENDING (needs the owner's Touch ID). Until
  then plain `npx` serves the broken `0.2.0`; the owner is unblocked via the local `node server.js`.
- R8 scheduled monitoring / R5 authenticated testing still parked (Part 317).

Related: [[project_testwright_phase2_fixtures]], [[project_testwright_qa_platform]],
[[project_testwright_run_perf]], [[feedback_debug_first]], [[feedback_status_claims_need_evidence]],
[[feedback_use_playwright]], [[feedback_file_length]].
