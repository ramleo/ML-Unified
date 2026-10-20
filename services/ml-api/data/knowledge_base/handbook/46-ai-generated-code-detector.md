Chapter 39AI-Generated Code Detector


> Paste a code snippet and see the stylometric signals people associate with AI authorship — comment density, generic naming, docstring formality, exception handling, boilerplate phrasing — alongside an independent LLM opinion, shown side by side. It deliberately never returns a probability or an 'AI-written' verdict, because no reliable general-purpose detector exists in the published research and a confidence number here would be invented.

## At a glance

| | |
|---|---|
| **Also called** | Signals, Not A Verdict |
| **Model or method** | Client heuristics + Mistral judge |
| **What you give it** | Text |
| **API Calls** | 0 |
| **Where it runs** | On the server |
| **Find it at** | `/tools/ai-code-detector` |

## Using the tool

### What this tool does
Paste a code snippet and see two independent, low-confidence signals side by
side: a **stylometric heuristic layer** (instant, client-side, checks for
documented stylistic tendencies) and an **independent LLM opinion**. Neither
one — separately or combined — produces a probability or a "written by AI"
verdict. This is a deliberate design choice, not a missing feature.

### Purpose
There is no reliable, published, general-purpose way to determine with
confidence whether a piece of code was written by an AI or a human. Style
alone isn't proof: a careful human can write clean, well-commented,
consistently-formatted code, and any LLM can be prompted to write messy,
inconsistent code. This tool exists to show what the actual, real signals
people point to look like — and, just as importantly, to demonstrate why
none of them, alone or combined, should be trusted as a verdict. It's an
honesty-first sibling to this site's other "documented, evadable heuristics
shown as raw evidence" tools (the Browser Extension Permission Risk
Analyzer, the LLM Prompt Injection Detection Playground).

### How to use it
1. Paste a code snippet, or click one of the three example buttons.
2. Click **Analyze code**.
3. Review the stylistic signals found (each with a plain-language "why" that
   also states its own weakness) and the LLM's independent read, then the
   qualitative overall label.

### A worked example
Click **AI-style snippet** — a Python example with dense Google-style
docstrings, generic variable names (\`result\`, \`data\`, \`output\`), a broad
\`except Exception\` block, and "Step 1/Step 2" comment framing. It correctly
surfaces 4 stylistic signals and an overall **"Several AI-style signals"**
label. Now click **Clean human snippet (should NOT flag)** — a tidy,
well-commented human function with a single clean docstring and no
boilerplate framing. It correctly returns **"No notable AI-style signals"**
— proof this tool doesn't punish a human for writing careful code. The third
example, **Messy human snippet**, has a TODO, a leftover debug \`print\`, and
inconsistent naming — also correctly returns no signals, since messiness is
itself just another style, not a determination of authorship either way.

### Reading the result
- **Overall label** — "Several," "A few," or "No notable" AI-style signals.
  Never a percentage, never "AI-written"/"human-written." A high signal count
  means "worth a second look for other reasons," not "confirmed."
- **Stylistic signals** — each one names what was found, a concrete detail,
  and an honest explanation of why it's only weakly suggestive.
- **Independent LLM opinion** — a second model's own read, instructed to
  answer "inconclusive" unless there's a genuinely distinctive tell (like an
  LLM chat artifact leaking into the code) — inconclusive is the expected,
  correct answer for most ordinary code, not a failure to decide.

### Notes & limits
- **No detector here is validated against a real benchmark of known
  human-vs-AI code samples.** This is disclosed prominently, not glossed
  over — the same reason two other candidate security tools for this site
  (a wildfire visual detector, a signature-verification tool) were rejected
  outright rather than shipped with a misleading confidence number.
- **Every signal is trivially fakeable in either direction.** Treat this as
  an educational demonstration of what people look for, not a way to catch
  anyone doing anything.
- **A high overall label is not evidence of wrongdoing** in any context
  (job interviews, academic integrity, code review) — using it that way
  would be exactly the overclaiming this tool is built to avoid.

## What problem it solves

A university wants to know whether a submission was written by a student. A
hiring manager wants to know whether a take-home was written by the candidate.
A maintainer wants to know whether a pull request from a stranger was typed or
generated.

All three want the same thing: a number that says *this is 87% AI*. That number
does not exist. **No peer-reviewed benchmark validates a reliable
general-purpose detector for AI-written code**, and the reason is structural
rather than a gap waiting to be filled by a better model:

- A careful human writes clean, uniformly named, thoroughly documented code.
  That is what good practice looks like, and it is also what generated code
  looks like.
- A language model can be asked for messy code, and will produce it — with
  inconsistent naming, a stray debug print, a TODO left in.
- Every formatter and linter in common use erases exactly the surface
  irregularities a detector would want to measure. Code that has been through
  Black or Prettier has had its handwriting removed.

So the honest tool is not a classifier. This one **never outputs a probability
and never says "AI-written"**. It shows the stylistic signals it found, states
next to each one why that signal is weak, and leaves the judgement with the
person reading it.

That refusal is the design. A confident detector here would be a tool for
accusing people wrongly.

## How it works, step by step

1. **Paste a snippet.** Python, JavaScript or TypeScript.
2. **Seven stylometric checks run in the browser.** No network call, nothing
   leaves the page.
3. **Each check that fires produces a signal card** with what was measured and
   a written caveat about why it proves little.
4. **A count becomes a qualitative label** — several / a few / no notable
   signals.
5. **Optionally, ask a second opinion.** One button sends the snippet to a
   language model whose instructions push it towards "inconclusive".
6. **The two layers are shown side by side, never merged** into a single score.

## The model or algorithm

### Layer one — stylometry, in the browser

Stylometry is the statistical study of writing style, the technique used in
authorship attribution for centuries. Applied to prose with a large sample and
a closed set of candidate authors, it works. Applied to a forty-line snippet
with an open set of authors, it does not — and the implementation is built to
say so.

Seven checks, each with a threshold chosen to be conservative:

| Signal | Fires when | Why it is weak |
|---|---|---|
| High comment density | over 30% of non-blank lines are comments | a well-documented human function looks identical |
| Generic naming | 3+ uses of `result`, `data`, `temp`, `value`, `output`… | short human scripts use these constantly |
| Uniform naming convention | 8+ identifiers, zero `snake_case`/`camelCase` mixing | every linter produces this |
| Formal docstring | a Google or NumPy `Args:`/`Returns:` block, or JSDoc `@param` | mandated by many real style guides |
| Broad exception handling | a catch-all `except:` or a `catch` that only logs | defensive programming is a human habit |
| Boilerplate phrasing | "This function…", "Here's…", "Step 3:" in a comment | tutorial authors write this way |
| No mess, uniform spacing | no TODO/FIXME/debug print/commented-out code **and** identical blank-line gaps between every function | a fresh, tidy script looks the same |

Two details in that table carry most of the weight.

**The last signal requires two conditions at once.** Absence of mess alone
proves nothing — a fifteen-line utility has had no time to accumulate any. The
check pairs it with *mechanically identical* blank-line gaps between every
function definition, computed by collecting the gap sizes and testing whether
the set of distinct values has size one. Tidiness plus metronomic rhythm is a
slightly stronger tell than either.

**The naming-convention check needs a minimum sample.** With three identifiers,
consistency is meaningless; the floor of eight is there so the signal cannot
fire on a snippet too small to have a convention.

The count maps to a label with no arithmetic in between:

```
3 or more signals  →  "Several AI-style signals"
1 or 2             →  "A few AI-style signals"
0                  →  "No notable AI-style signals"
```

Three thresholds, three words. There is deliberately no weighting, no
calibration, and no percentage — because any of those would imply a validation
exercise that was never performed and could not honestly be performed.

### Layer two — an independent language-model opinion

The second layer runs on the backend, because it needs an API key. Its system
prompt is the interesting part, and it is written to argue *against* the answer
a user wants:

> There is no reliable, published way to determine with confidence whether code
> was written by an AI or a human… Only answer "ai_leaning" or "human_leaning"
> if there is a genuinely distinctive tell (e.g. an artifact of an LLM chat
> response leaking into the code, like a trailing "Let me know if…" comment).
> Otherwise answer "inconclusive" — **this is the expected, correct answer for
> most ordinary code and is not a failure to decide.**

That last clause exists because models are agreeable. Asked "is this AI?", a
model will find reasons to say yes. The prompt has to state explicitly that
abstaining is success, or the layer becomes a machine for confirming whatever
the person already suspected.

The reply is required to be a JSON object with `assessment`, `confidence` and a
one-sentence `explanation`. Parsing is best-effort — a regular expression pulls
the first `{...}` out of the response, because models wrap JSON in prose or a
markdown fence often enough that strict parsing would fail on correct answers.
A missing `assessment` field returns nothing rather than a fabricated default.

The route is rate-limited and metered against a daily call budget, since it
runs on the project's own API key rather than the visitor's.

## Why these choices

**Why no confidence score, when every commercial detector has one?** Because a
score invites a decision, and the decision this tool would be used for is
accusing a person of dishonesty. Published AI-text detectors have documented
false-positive rates that fall disproportionately on non-native English
writers; the code equivalent would fall on anyone who follows a strict style
guide. A tool that cannot be validated should not present output that looks
validated.

**Why run stylometry client-side?** Two reasons. Privacy — the snippet may be
proprietary, and the heuristics need no server. And transparency: the checks
are plain functions in a file anyone can read, which matters for a tool whose
entire claim is that it is not a black box.

**Why keep the two layers separate rather than combining them?** They fail in
different ways. The heuristics are deterministic and evadable by anyone who
reads them. The judge is non-deterministic and can be influenced by the code it
is reading. Averaging them would produce a number that hides both failure
modes. Shown side by side, disagreement is visible — and disagreement is
information.

**Why is the strongest real signal not a style measurement at all?** The one
tell the judge is told to look for is a **chat artifact**: text that belongs to
a conversation with an assistant, pasted into a file by accident. "Let me know
if you'd like me to add tests!" in a trailing comment is not a stylistic
tendency, it is a provenance leak. Live testing confirmed the split — given a
tidy AI-style snippet the judge correctly stayed inconclusive; given the same
snippet with a chat artifact appended it flipped to `ai_leaning` at high
confidence.

## How to read the output

Read the **evidence**, not the label.

"Several signals" means several conservative thresholds were crossed. On a
well-documented, linted, freshly written human module, all of them can cross at
once. That is a known and expected outcome, not a bug.

"No notable signals" means nothing crossed. Generated code that has been edited,
reformatted, or simply asked to be terse will land here.

In other words the tool is neither sensitive nor specific, and it says so. It is
useful for one thing: giving a person a structured place to start looking, with
the reasons why each observation is thin printed alongside it.

The judge's `inconclusive` is not an error message. It is the answer for
almost all real code, and a judge that rarely says it would be broken.

## Limits

- **No validated accuracy figure exists**, because no honest one could be
  produced without a labelled corpus of human and AI code matched for language,
  domain, developer experience and formatter — and any such corpus would be
  stale within months.
- **Trivially evadable in both directions.** The checks are published; adding a
  TODO and one inconsistent name defeats them.
- **Language coverage is narrow** — the comment and docstring patterns assume
  Python, JavaScript or TypeScript.
- **Short snippets are hopeless.** Under roughly twenty lines there is not
  enough text for any check to mean anything, and several cannot fire at all.
- **The judge is a language model**, so it is non-deterministic and can be
  influenced by the content it reads.
- **This must not be used as evidence against a person.** The interface, the
  documentation and the backend docstring all say so.

## Likely interview questions

**"Build me a detector for AI-written code."**
The first answer is that a reliable general-purpose one is not currently
possible, and I would say that before writing anything. What is possible is a
transparency tool: measurable stylistic signals, each shown with its own
caveat, plus a second independent opinion, and no fused score. If the
requirement is genuinely a verdict, the honest engineering answer is provenance
rather than detection — commit history, keystroke or editor telemetry, an
interview about the code — because those observe the writing rather than
guessing from the artefact.

**"Why is a false positive worse than a false negative here?"**
Because of what each one costs. A false negative means generated code passes
unnoticed, which is the status quo. A false positive means a person is accused
of dishonesty on the basis of a number a machine produced, and the burden of
disproving it falls on them. When the error costs are that asymmetric, the
system should be built to abstain, which is exactly what the "inconclusive"
default and the missing probability are for.

**"Which of your signals is strongest, and why is it still weak?"**
The combined "no mess plus mechanically uniform spacing" one, because it
requires two independent conditions rather than one. It is still weak because a
formatter produces uniform spacing mechanically and a new file has had no
opportunity to accumulate mess — so the signal fires on any freshly written,
auto-formatted human module, which is a large fraction of all new code.

**"You used an LLM as one of the layers. How do you stop it agreeing with the
user?"**
By writing the system prompt against the grain: it states outright that no
reliable method exists, gives one concrete example of what a real tell looks
like, and — the important line — says that "inconclusive" is the expected
correct answer for most code and not a failure to decide. Without that last
sentence the model treats abstention as unhelpfulness and finds a reason to
pick a side.

**"How would you validate this if you had to?"**
I would need a corpus where provenance is known rather than assumed: code with
a full commit history and editor telemetry for the human half, and generated
code for the other, matched on language, task and formatter — then report
precision and recall per language with confidence intervals, and re-measure
whenever a major model or a formatter default changes. I would expect the
result to be close to chance on formatted code, and I would publish that
number. The absence of any such published result is the reason this tool
reports evidence instead of a verdict.

**"Stylometry works for prose. Why not for code?"**
Sample size and normalisation. Authorship attribution on prose uses thousands
of words, function-word frequencies, and a closed candidate set. Code snippets
are short, the vocabulary is largely fixed by the language and its libraries,
the candidate set is open, and — decisively — automatic formatters normalise
away whitespace, quoting and layout, which is where much of the individual
signal in written text lives.
