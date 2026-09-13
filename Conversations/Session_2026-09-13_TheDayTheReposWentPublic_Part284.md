# Part 284 — The day the repositories went public

Continues [Part 283](Session_2026-09-13_ThreeThingsCalledVerified_Part283.md).

2026-09-13, later the same day. Both repositories are now public: ML-Unified
under AGPL-3.0, ml-portfolio under MIT. Every item in section D of
`OPEN_ISSUES.md` closed, plus E7, E8, F1 and half of F2.

The tracker rows carry the detail and `THIRD_PARTY.md` carries the licence
reasoning, so neither is repeated here. What follows is the part that does not
fit in a table: two root causes that were nothing like what they looked like,
and one habit that failed three times in one session.

---

## 1. Going public was the fix, not the risk

The licence had been sitting in the tracker as "the blocker for going public"
and in memory as accepted risk. Both framings were backwards.

AGPL-3.0 §13 asks a hosted service for exactly one thing: that people using it
over a network can obtain its source. Private and hosted is the state that
cannot satisfy that. Public, licensed, with a link from the running
application, satisfies it completely and costs nothing for a free portfolio.
The exposure had been real for months precisely *because* the repositories were
private.

Two corrections to what the tracker claimed. It is three Ultralytics-derived
models, not two — `signature-detector.onnx` is a YOLO11s fine-tune, and the
Apache-2.0 and MIT claims on it and on the PPE model are each a fine-tuner's
statement about their own contribution, which cannot grant more than the base
weights allow. And D2, "provenance untraced", was never untraced: it had been
written into `mm_signatures.py` when the model was adopted and nobody had
looked. Both now live in `THIRD_PARTY.md`, where the next person will find them.

---

## 2. Dependabot did not commit the junk

D3 was 21 gitignored files tracked on main, about 50 MB. D4 was the question
that mattered: they all entered through `ff5f4c2`, the squash merge of
Dependabot PR #22, and a dependency bump cannot add binaries.

The PR's branch held **two** commits. Dependabot's httpx bump, and `fdaf6ce5` —
a hand-made commit dated 2026-08-30 whose message describes handbook work that
lives in the *ml-portfolio* repository, committed here, carrying
`services/ml-sql/requirements.txt` beside the junk.

So the Dependabot branch was checked out locally when a `git add -A` ran from
the wrong directory. It swept up everything untracked in this repository and
committed it under the other repository's message, onto that branch, where it
sat for two weeks until the squash merge folded both commits into main under
dependabot's name. That attribution is the only reason it read as impossible.

Same incident as the existing "never `git add -A`" rule, surfacing long after
the rule was written. No other branch carries `fdaf6ce5`.

The three root `test_*` files needed more than untracking, incidentally: they
were tracked but never matched by any ignore rule, so removing them from the
index alone would have left them sitting in the repository root ready to be
swept up exactly as before.

---

## 3. Seven failing tests, and four hundred meaningless passes

`pytest services/` reported seven ml-vision failures. They were not ml-vision
bugs.

ml-api and ml-vision are separate deployments that both own generic top-level
names: each has an `app.py` holding its FastAPI application, and each had a
`shared/` namespace package containing a **different** `progress.py` — 126
lines against 104. Each suite's conftest puts its own service directory on
`sys.path`, so in one interpreter only one of each name can win and the suite
collected second imports the other service's code.

The seven failures were the visible half. The worse half is that the four
hundred passes beside them proved nothing, because some were asserting against
the wrong application.

**The first fix made it worse.** Evicting the stale module from `sys.modules`
turned seven failures into sixty-one in the reverse collection order. No
`sys.path` trick can fix this; the names have to stop colliding. ml-vision's
modules became `vision_app` and `vision_shared`, which was nearly free because
ml-vision is not deployed anywhere — no Space exists for it and the live
backend has no `ML_VISION_URL`.

A `^`-anchored grep then reported no leftover references while missing five
indented `import app as app_module` calls inside test bodies, which broke
ml-vision's own suite until an unanchored search found them.

---

## 4. The assistant answering about Mastercard was not a jailbreak

Asked "what is mastercard?" inside the EDA assistant, it wrote a page on
payment networks. Nothing had been bypassed, because there was no rule to
bypass: `build_system_prompt()` described the tool, supplied retrieved text,
and gave formatting instructions. Not one line told the model to decline
anything. The only scope switch that existed, `restrict_to_uploads`, is set by
Multimodal RAG and nothing else. All 47 pages using `ToolsAIChat` behaved this
way, the 36 passing a `guide:` included — a guide is more context, not a
boundary.

**The exception was the harder half of the fix.** Every page except Multimodal
RAG carries a document-upload button, so a user genuinely can put a Mastercard
annual report into the EDA assistant, and refusing there would be a worse bug
than the original. Scope therefore follows what was *retrieved*, not what the
subject sounds like. Deliberately not a keyword blocklist: no word list decides
whether an assistant is being used for what it is for.

Proved end to end against the deployed Space rather than asserted — uploaded a
briefing naming Mastercard's settlement window, asked for it, got the answer
cited to the upload; deleted the upload, asked the identical question, got the
refusal.

A related trap: the EDA user guide could not go through `ToolsAIChat`'s `guide`
slot, which looks like exactly where it belongs. That slot hides the upload and
search-depth controls and has `buildToolContext()` rewrite the prompt into a
help bot that explicitly declines "general ML theory" — which is half of what
this assistant is asked. It goes in through `summary` instead, and the e2e test
asserts the chat is still the data assistant so that the obvious later "fix"
fails the suite.

---

## 5. Reading the last line is not reading the output

Three times in one session, a check reported success that it had not earned.

* `tail -1` on `check-file-length.sh` hid an outright failure. The length
  baseline still pinned `services/ml-vision/app.py`; after the rename that read
  as a brand-new 868-line violation and the gate exited 1. The line I printed
  happened to be blank.
* The first proof that the new full-history gitleaks job could fail planted
  AWS's own documented example key, which gitleaks allowlists. It came back
  clean and demonstrated nothing. A `ghp_`-shaped token committed and then
  deleted was caught (exit 1) and missed by a working-tree scan (exit 0), which
  is the actual argument for the job.
* The first live probe of the scope rule had a broken SSE parser — it read
  `ev['token']` where the event is `{"type":"token","text":...}` — and printed
  four blanks. Those calls still reached the model and populated the answer
  cache, so the *second* run returned `cache_hit=True` on everything. Reading
  cached text as evidence would have proved nothing. Every result finally
  reported came from a `cache_hit=False` call.

Part 283's lesson was to check the artefact the reader receives. This one is
narrower and more embarrassing: having run the check, read all of what it said.

---

## What going public changed immediately

GitHub Actions minutes stopped being a constraint — the 2,000-minute monthly
cap is a private-repository limit. The account had hit 90% of it, about 839
minutes spent in this single day across 109 runs, mostly the 28 Dependabot
merges each running CI twice. Every job bills rounded **up** to a whole minute,
so an 8-second check costs one, and parallel jobs bill separately, so a
four-minute run can cost eleven.

Swept again at the moment of flipping, because "private" had been doing part of
the work until then: full-history gitleaks clean on both repositories, no
token-shaped strings in either tracked tree, and the only tracked env file is
ml-portfolio's `.env.example`, holding placeholders.

Open after today: B2, E1–E6, and the handbook chapter half of F2.
