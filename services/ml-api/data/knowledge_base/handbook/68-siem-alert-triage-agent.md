Chapter 60SIEM Alert Triage Agent


> Paste raw alert lines and get them grouped and prioritised. Near-identical alerts are deduplicated by template in your browser first, so only the grouped summary — never your raw log — is sent on to an LLM for a priority, a one-line reason and a suggested next step per group. Advisory only: every suggestion is written for you to act on, never phrased as something already done.

## At a glance

| | |
|---|---|
| **Also called** | Grouping + LLM Judge |
| **Model or method** | Client-side grouping + Mistral small (server key) |
| **What you give it** | Pasted raw alert log |
| **Analysis Layers** | 2 |
| **Where it runs** | On the server |
| **Find it at** | `/tools/siem-alert-triage` |

## Using the tool

### What this tool does
Security teams get flooded with far more raw alerts than a human can
individually review — this is the real "alert fatigue" problem SOC
analysts deal with every day. This tool does what a real triage workflow
does: it collapses near-identical alerts into groups first, then asks an
independent LLM judge to prioritize each *group* (not each raw line) and
suggest what a human analyst should check next.

### Two layers, not one black box
1. **Deduplication/grouping (runs entirely in your browser)** — every
   pasted alert line is normalized into a "template" by replacing IPv4
   addresses and numbers with placeholders, so lines that only differ by
   an IP address, username, or count collapse into the same group. This is
   a simplified version of real log-template-extraction techniques (like
   the published Drain/IPLoM algorithms use) — not an exact implementation
   of either, but the same underlying idea. Only the **grouped summary**
   (template text, count, one real example line, and the unique IPs
   involved) is ever sent to the backend — never your full raw paste,
   and capped at the 20 largest groups so a huge log can't blow up the
   request.
2. **LLM judge (backend, second opinion)** — the grouped summary is sent
   to a second, independent LLM call that assigns each group a priority
   (critical/high/medium/low/noise) plus a one-sentence reason and a
   one-sentence suggested next step. This reuses the exact same
   fixed-server-key pattern already used by this site's Prompt Injection
   Playground and AI Code Detector tools — no API key of your own is
   needed.

### Advisory only — this tool never takes action
Every suggestion is phrased as something a human should do next
("investigate the source IPs," "likely safe to suppress") — never as
something this tool already did. There is no real firewall, EDR, or
Active Directory integration behind this: it cannot actually block an IP,
disable an account, or isolate a host. Treat every "suggested action" as a
starting point for a human investigation, not a completed remediation.

### How to use it
1. Paste a batch of raw alert lines, one per line — from any source
   (SIEM export, resolver log, application log, anything text-based).
2. Click **Triage alerts**. Click **Try a sample log** to see a worked
   example mixing a brute-force-style repeated pattern, a couple of
   genuinely distinct one-off alerts, and pure noise (repeated routine
   "backup completed" messages).
3. Results appear sorted by priority (critical first), each card showing
   the real grouping data (match count, unique IPs, one real example line)
   alongside the judge's reasoning and suggested action — never a bare
   priority label with nothing behind it.

### What this is (and isn't)
This is a real two-layer triage assistant, not a trained anomaly-detection
model and not a live SIEM integration. The grouping heuristic only
collapses alerts that share the same normalized template — a genuinely
different-looking alert about the same underlying incident won't be
grouped with it. The LLM judge's priority calls are a second opinion, not
ground truth — it has no context beyond what's in front of it (no
knowledge of your specific environment's baseline, no historical
correlation across sessions). If the judge is temporarily unavailable, the
grouping data is still shown on its own — the deduplication itself is
useful even without a priority opinion layered on top.

## What problem it solves

A security operations centre receives tens of thousands of alerts a day. A human
analyst can meaningfully triage perhaps a hundred.

That gap has a name — **alert fatigue** — and it is the defining operational
problem of the field. It is not that the alerts are wrong. It is that ten
thousand of them are the *same alert*, differing only by an IP address, and the
one that matters is somewhere in the middle. Analysts stop reading, and the
famous breaches are frequently ones where the alert fired and nobody looked.

The fix is not a better detector. It is **collapsing repetition** so a human
triages the *pattern* once rather than every instance of it.

This tool does that in two stages: deduplicate by structure in the browser, then
ask a language model to prioritise the handful of groups that remain.

## How it works, step by step

1. **Paste an alert log**, one alert per line.
2. **Normalise each line into a template** — variable parts replaced by
   placeholders.
3. **Group identical templates**, counting members and collecting the distinct
   IP addresses involved.
4. **Keep at most 20 groups**, largest first.
5. **Send the groups** — template, count, one real example, the IPs — to a model.
6. **Get back a priority, a reason and a suggested action per group.**

## The model or algorithm

### Log template extraction

The grouping is the substantive part, and it happens entirely client-side.

Two alerts like:

```
Failed login for admin0 from 192.168.1.44 (attempt 3)
Failed login for admin7 from 10.0.0.19 (attempt 12)
```

are the *same event type*. What differs is the variable content. Normalising it
away:

```
failed login for admin# from <IP> (attempt #)
```

collapses both — and the other 9,998 like them — into one group with a count.

The transformation is three substitutions, and the second one carries a comment
worth reading:

- **IPv4 addresses → ``**, done first.
- **Any digit run → `#`.** The comment explains why there is deliberately **no
  word-boundary requirement**: a digit run inside an alphanumeric token —
  `admin0`, `server7` — has no `\b` before it, because the preceding letter is
  also a word character. A blanket replacement handles both `attempt 3` and
  `admin0` correctly, and it is safe precisely *because* IPs were stripped in the
  previous step.
- **Whitespace collapsed, lowercased.**

That ordering matters: replace digits first and an IP becomes `#.#.#.#`, losing
the information that it was an address at all.

**This is a simplified version of a real technique**, and the code says so. SIEM
correlation engines use published log-template algorithms — **Drain**, which
builds a fixed-depth parse tree over log tokens, and **IPLoM**, which partitions
iteratively by token count and position. This is a heuristic normalisation, not
an implementation of either, disclosed as such rather than borrowing their names.

The IPs are collected per group rather than discarded, which keeps the detail
that matters: *"one alert, seen 4,000 times, from a single IP"* and *"one alert,
seen 4,000 times, from 3,800 distinct IPs"* are completely different incidents.

### Why 20 groups

Two reasons at once. A human can look at twenty things; and the model receives
twenty short items instead of ten thousand lines, which keeps the request inside
a sane context and a predictable cost. Ordering by count means the twenty you get
are the twenty largest.

### The model's role, deliberately narrow

The model is not the detector and not the deduplicator. It sees an
already-condensed list and adds **a second, independent opinion** about
prioritisation.

The system prompt is the interesting artefact:

- It is told **exactly what it is looking at** — a deduplicated group, with a
  count, one real example line and the IPs — rather than raw alerts.
- It must return a **fixed JSON array, one object per input group, in the same
  order**, so results line up with the groups without any matching logic.
- Priority comes from a **closed set**: `critical`, `high`, `medium`, `low`,
  `noise`. Including `noise` matters — the correct answer for most groups is that
  they are not worth attention, and a scale without a bottom rung forces
  everything to look like something.
- And the constraint the whole design rests on:

> *"You are advisory only — you do not take any action yourself, and must never
> phrase a suggestion as something already done (say 'investigate the source IP',
> never 'blocked the IP')."*

**That is there because there is no firewall, Active Directory or EDR integration
behind this tool.** A model asked to suggest remediation will naturally write
*"blocked the offending IP"*, and an analyst reading that reasonably assumes the
IP is blocked. It is not. The prompt forbids the phrasing that would create that
belief.

It is a good example of a prompt constraint that exists for a **safety** reason
rather than a quality one: the danger is not a bad suggestion, it is a
well-phrased false statement about the world.

### Cost and abuse controls

The judge runs on a **fixed server-side key** — the same pattern as the AI code
detector and the prompt-injection checker — with rate limiting and a daily budget
cap. Input fields are length-capped: 300 characters for a template, a bounded
example, at most 100 IPs per group.

## Why these choices

**Why deduplicate before the model, not with it.** A model asked to group ten
thousand lines would cost a fortune, be slow, be non-deterministic, and be worse
at it than three regular expressions. Template extraction is exact, instant and
free. **Use the model for judgement, not for work a deterministic transformation
does better.** The 10,000-to-20 reduction happens before a single token is spent.

**Why client-side grouping.** Security logs contain internal hostnames, usernames
and network structure. Only the condensed groups are transmitted, so the raw log
never leaves the machine.

**Why send one real example line.** The template alone is lossy — `failed login
for admin# from ` does not convey severity. One real line gives the model
concrete detail without sending the other 9,999.

**Why a closed priority set.** Free-text severity is unsortable and inconsistent.
Five levels including an explicit `noise` are comparable across groups.

## How to read the output

- **The counts are the finding.** A group of 4,000 is noise or an incident; a
  group of 2 that looks like credential theft is where to start.
- **Read `unique_ips` against the count.** Many alerts from one IP is a
  misconfiguration or a single actor. The same count from thousands of IPs is
  distributed and different.
- **`noise` is a real and common verdict**, and getting it is useful — it is
  permission to stop looking.
- **Suggested actions are suggestions.** Nothing was done, and the prompt exists
  to keep the wording honest about that.
- **The model saw a template, a count, one example and some IPs.** It did not see
  your network, your asset criticality, or what is normal for you.
- **Twenty groups is a cap.** A long tail exists below it, and rare events are
  exactly what a count-ordered list buries.

## Limits

- **Grouping is heuristic** — IPs and digit runs only. IPv6, hostnames, GUIDs,
  usernames and file paths are not normalised, so alerts differing by those do
  not collapse.
- **Not Drain or IPLoM**, and disclosed as such.
- **20 groups**, ordered by count, so the tail is cut.
- **No correlation across alert types.** Real SIEM value is in linking a failed
  login to a later privilege escalation on the same host; this triages each
  group in isolation.
- **No timestamps.** Rate and burst are among the strongest triage signals and
  are not used.
- **No environment context** — no asset criticality, no baseline, no knowledge of
  which server matters.
- **The model can be wrong**, and its confidence reads the same either way.
- **Advisory only.** No integrations, nothing is acted on.
- **A pasted log, once.** Not a live pipeline.

## Likely interview questions

**"What is alert fatigue and how do you actually address it?"**
Too many alerts for a human to triage, so analysts stop reading — which is how
breaches happen where the alert did fire. The fix is not a better detector, it is
reducing what a human has to look at. Deduplication by log template is the
highest-leverage step: ten thousand near-identical lines differing only by an IP
become one group with a count of ten thousand, and the analyst triages the
pattern once. That is a reduction of three orders of magnitude before any
cleverness is applied.

**"How does log template extraction work?"**
Replace the variable parts with placeholders so structurally identical lines
collapse. Here that is IPv4 addresses to `` first, then any digit run to `#`,
then whitespace and case normalised. The order matters — replace digits first and
an IP becomes `#.#.#.#` and you have lost that it was an address. The published
algorithms, Drain and IPLoM, do this more robustly with parse trees and iterative
partitioning; this is a heuristic version and says so.

**"Why not just give the whole log to the model?"**
Cost, latency, determinism and quality. Ten thousand lines is an enormous number
of tokens, it is slow, the grouping would differ between runs, and a model is
worse at exact deduplication than three regular expressions. The right division
is deterministic work done deterministically and judgement given to the model —
so the log is reduced to twenty groups before a single token is spent.

**"Your prompt forbids the model from saying 'blocked the IP'. Why does that
matter?"**
Because there is no firewall integration behind this tool. A model asked to
suggest remediation naturally writes in the past tense — "blocked the offending
IP" — and an analyst reading that reasonably concludes the IP is blocked. It is
not. The risk is not a bad suggestion, it is a well-phrased false statement about
the state of the world, and the fix is a prompt constraint on the phrasing rather
than on the content.

**"Why include `noise` as a priority level?"**
Because for most groups it is the correct answer, and a scale without a bottom
rung forces everything to look like something. An analyst's most valuable output
is often "this is not worth your time", and a tool that cannot say so just
relocates the fatigue from raw alerts to triaged ones.

**"What's the biggest thing missing?"**
Timestamps, and therefore correlation. Rate and burst are among the strongest
triage signals available — four failed logins over a week and four in one second
are completely different — and neither is visible here. Beyond that, the real
value of a SIEM is linking events across types on the same host over time: a
failed login, then a success, then a privilege escalation. This triages each
group in isolation, which is one useful step and not the whole job.
