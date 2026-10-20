Chapter 64YARA File Scanner


> Scan a file with real YARA — the same pattern-matching engine antivirus and threat-intel teams use to write and share detection rules. Run it against a small built-in rule set (EICAR, PowerShell LOLBin encoding, webshell and macro patterns, embedded-PE smuggling, an entropy rule), or write your own rule and test it, which is what YARA actually exists for. Your file is never executed, and every hit shows the matched string and offset rather than a bare verdict.

## At a glance

| | |
|---|---|
| **Also called** | Live Engine · Real YARA |
| **Model or method** | yara-python (real YARA engine) |
| **What you give it** | Uploaded file + optional custom rule |
| **Built-in Rules** | 7 |
| **Where it runs** | On the server, with a live external check |
| **Find it at** | `/tools/yara-file-scanner` |

## Using the tool

### What this tool does
Upload any file and it's scanned with the real, open-source **YARA**
pattern-matching engine — the actual industry-standard tool antivirus
vendors, EDR products, and threat-intel teams use to write and share
malware-detection rules. Scan with a small built-in educational rule set,
or write and test your own YARA rule against the file — the real everyday
workflow YARA exists for.

### Built-in rules — an educational demo set, not a production feed
These 7 rules are self-authored for this project, covering well-documented
indicator classes. They are deliberately small and disclosed as a demo,
NOT a pulled third-party threat-intel feed (whose licensing terms weren't
something to assume without checking):
1. **EICAR test signature** — the real, official antivirus test string.
2. **Suspicious PowerShell encoded command** — the \`-EncodedCommand\`/\`-enc\`
   flag combined with a long base64 run, a well-documented technique for
   hiding a malicious command line.
3. **Generic PHP webshell indicator** — \`eval()\`/\`base64_decode()\` combined
   with \`$_POST\`/\`$_GET\`, the standard webshell pattern.
4. **Office macro auto-exec indicator** — \`AutoOpen\`/\`Document_Open\`
   combined with \`Shell\`/\`CreateObject\`, the classic macro-malware pattern.
5. **Embedded PE smuggled in another file** — a Windows executable's own
   marker string found anywhere in the file, not just at the start.
6. **Possible Python reverse-shell pattern** — \`socket\`+\`subprocess\`+
   \`connect()\` co-occurring.
7. **High overall entropy** — uses YARA's own real \`math\` module to flag
   files with entropy above 7.5 bits/byte (near the theoretical max of 8).
   This is informational only — ordinary compressed formats (zip, jpg)
   also read this high, so it's shown as evidence, not a verdict.

### Custom rules — the real point of YARA
YARA's actual purpose is letting an analyst write a rule and test it
against real samples. Switch to "Write your own rule" to do exactly that:
type or paste a YARA rule (an example is pre-filled), and it's compiled
and run against your uploaded file on the server. A syntax mistake returns
the real compiler error rather than a generic failure — most first
attempts at a YARA rule have one, and seeing the actual error is part of
learning the syntax.

### How to use it
1. Pick a mode: **Built-in rules** or **Write your own rule**.
2. If writing your own, edit the rule text (the pre-filled example matches
   files containing the string \`SECRET_MARKER_XYZ\` — try it against a
   file you make containing that text).
3. Click **Choose file**, then **Scan**.
4. Each matched rule is shown with its description and the actual matched
   string, its identifier, and its byte offset in the file — real evidence
   for you to judge, never a fabricated malicious/clean score.

### Notes & limits
- The file is **never executed or written to disk** — only its raw bytes
  are read in memory for pattern matching.
- Files are capped at 5MB; custom rule source is capped at 20KB.
- A custom rule match runs under a 5-second timeout — a guard against a
  pathological pattern (e.g. a runaway regex) taking too long, not a
  limitation you should normally notice.
- **No result here is a verdict.** A match means the file contains a
  pattern that rule looks for — it's evidence for a human to weigh, the
  same way a real analyst reads YARA hits, not an automatic malicious/safe
  determination.

## What problem it solves

An analyst has a suspicious file. Not a known virus with a published signature —
something new, or something they only suspect. The question is not "does an
antivirus recognise this?" but *"does this file contain the specific thing I am
looking for?"*

That is what **YARA** exists for. It is a pattern-matching language for files —
often described as "grep for malware researchers", though it is considerably more
than grep. An analyst writes a rule describing a pattern, runs it against files,
and iterates. It is the standard way threat intelligence is written down and
shared: a YARA rule is a portable, executable description of what a family of
malware looks like.

This tool runs the real YARA engine, in two modes. Scan a file against a
built-in rule set, or — the more important half — **write your own rule and run
it**.

## How it works, step by step

1. **Upload a file**, up to 5 MB.
2. **Choose a rule source** — the built-in set, or your own rule text.
3. **Compile the rules.** A syntax error in a custom rule is reported as a
   compile error, which is exactly the feedback loop rule-writing needs.
4. **Match against the file's bytes in memory**, with a 5-second timeout.
5. **Return every matching rule**, its description, and where in the file the
   strings hit.

## The model or algorithm

### What YARA actually is

A rule has three parts:

```
rule Suspicious_PowerShell_EncodedCommand {
    meta:       description = "..."
    strings:    $a = "-EncodedCommand" nocase
                $b = "FromBase64String" nocase
    condition:  $a and $b
}
```

- **`meta`** — documentation, carried through to the result.
- **`strings`** — the patterns to look for: text, hex byte sequences, or regular
  expressions, with modifiers like `nocase`, `wide` (UTF-16) and `ascii`.
- **`condition`** — a boolean expression over which strings matched, and over
  file properties like size and entropy.

The condition is what raises YARA above plain string search. `$a and $b`,
`2 of them`, `$mz at 0`, `filesize > 256 and math.entropy(0, filesize) > 7.5` —
you are describing *co-occurrence and structure*, not just presence.

### The built-in rules, and why each one is written the way it is

Six rules, and each demonstrates a different YARA idea:

**EICAR test file.** The industry-standard harmless string every scanner is
expected to detect. It is here so you can prove the scanner works without going
near real malware.

**PowerShell encoded command.** `-EncodedCommand` together with
`FromBase64String`. Neither is suspicious alone — both are legitimate PowerShell
— but **co-occurrence** is the classic living-off-the-land pattern: run a
base64-blob so the command line does not reveal what it does.

**Generic PHP webshell.** Several patterns with a threshold condition rather than
a single match, because any one of them appears in ordinary code.

**Office macro auto-execution.** The `AutoOpen`/`Document_Open` family — macros
that run on open rather than on request.

**Embedded PE in a non-executable.** Looks for `MZ` *and* the string
`"This program cannot be run in DOS mode"` **anywhere in the file, not just at
offset 0**. That is the point: an executable at offset 0 is a normal `.exe`, and
the same marker buried inside a document is a Windows binary smuggled into
another file type.

**High overall entropy.** Uses YARA's `math` module:
`filesize > 256 and math.entropy(0, filesize) > 7.5`.

Entropy measures how unpredictable the bytes are, in bits per byte, with 8 as
the theoretical maximum. Encrypted or compressed data is near-random and scores
close to 8; English text scores around 4.5. Packed and crypted malware therefore
shows high entropy — and so does **any zip file or JPEG**. The rule's own
description says so, and calls itself *informational, not a verdict on its own*,
which is exactly the right framing for a signal with that false-positive profile.

### Why the rules are self-authored, and disclosed as such

The docstring is explicit: the built-in set is a **small, self-authored
educational set** covering well-documented indicator classes, and deliberately
**not** a pulled third-party threat-intelligence feed — because that feed's
licensing was not verified for this project.

The tool then calls that the same "curated, disclosed as not exhaustive" pattern
used by the QR Phishing Detector's brand list and the Malicious Package
Scanner's typosquat list. A short honest list is more useful than a long one of
uncertain provenance, provided you say which you have.

### The custom-rule endpoint is the real feature

The docstring names it: *"YARA's real-world purpose is letting an analyst write
and iterate on a detection rule, not just run a fixed scanner."*

A fixed scanner answers "is this one of the things I already know about?" — which
is what antivirus does, better. YARA answers "does this match the pattern *I*
just described?", and the value is in the loop: write a rule, run it, see what it
catches and what it misses, refine. Shipping only the built-in set would be
demonstrating the wrong half.

### The safety properties

Three, and each is deliberate:

- **The file is never executed.** YARA reads bytes; it does not run anything.
- **The file is never written to disk.** Bytes stay in memory, so there is
  nothing to accidentally leave behind or accidentally open.
- **Matching has a 5-second timeout** — YARA's own `timeout` parameter, not a
  wrapper. This guards against a pathological custom rule, such as a regular
  expression with catastrophic backtracking, hanging the request. Since the rule
  source is **user input**, that is a genuine untrusted-input path and needs a
  real bound.

Plus size caps: 5 MB for the file, 20 KB for the rule source — *"a hand-written
YARA rule is never this large"*.

## Why these choices

**Why the real YARA engine.** `yara-python` installs as a prebuilt manylinux
wheel with no `libyara` compile step, which is what makes it deployable here.
Reimplementing a subset would produce something that looks like YARA and behaves
differently — and the rules people already have would not run on it.

**Why in-memory only.** A malware-analysis tool that writes uploads to disk has
created a place where a malicious file now lives. Not writing it is simpler and
strictly safer.

**Why 5 MB.** Consistent with the byte-plot triage tool, and enough for the
document and script files this is aimed at.

## How to read the output

- **A match is a pattern hit, not a verdict.** Every rule here describes
  something *suspicious in context*, and several are outright dual-use.
- **Read the rule description.** It is carried through from the `meta` block and
  usually says what would make the match innocent.
- **High entropy on a zip or a JPEG is expected**, and the rule says so itself.
- **The Python reverse-shell rule fires on pentesting tools and on teaching
  material**, because they contain the same three tokens. Its description says
  so.
- **String offsets tell you where to look**, which is often more useful than the
  fact of the match.
- **Nothing matched means nothing matched.** Six rules is not coverage.
- **A compile error is normal when writing rules.** That is the loop working.

## Limits

- **Six built-in rules.** Self-authored, educational, explicitly not exhaustive.
- **No threat-intelligence feed**, by choice, on licensing grounds.
- **YARA is static pattern matching.** It does not run the file, so packed,
  encrypted or heavily obfuscated content hides its contents from every string
  rule — which is why the entropy rule exists as a weak proxy.
- **Signatures are inherently retrospective.** A rule describes something
  somebody already understood.
- **5 MB file, 20 KB rule, 5-second match.**
- **No archive extraction.** A zip is scanned as a zip, not as its contents.
- **Custom rules run server-side**, so the timeout and the size cap are the
  protection.
- **Not an antivirus.** No behavioural analysis, no sandbox, no reputation.

## Likely interview questions

**"What is YARA and when would you use it over an antivirus?"**
YARA is a pattern-matching language for describing families of files —
strings plus a boolean condition over them and over file properties. You use it
when you are hunting rather than blocking: an antivirus answers "is this a known
bad thing", and YARA answers "does this match the pattern I just described",
which is what you need when investigating something new or checking an estate for
a specific indicator. It is also how threat intelligence is shared, because a
rule is portable and executable.

**"Why is `-EncodedCommand` alone not a rule?"**
Because it is legitimate PowerShell and fires constantly. The rule requires it
*together with* `FromBase64String`, and the co-occurrence is what carries the
signal — running a base64 blob so the command line does not reveal the command.
That is the general principle in detection engineering: individual indicators are
usually dual-use, and the rule's value is in the condition, not the strings.

**"Explain the entropy rule and its weakness."**
Entropy is bits per byte, maximum 8, measuring how unpredictable the bytes are.
Encrypted and compressed data approaches 8; English text is around 4.5. Packed
malware is high-entropy — and so is every zip file and JPEG, which is the
weakness. The rule's own description calls itself informational rather than a
verdict, which is the right framing. It is useful as one signal among several,
never alone.

**"You let users upload a rule and run it server-side. What's the risk?"**
It is untrusted input reaching a compiler and a matching engine. The two real
risks are a rule that fails to compile — handled, and surfaced as feedback since
that is the rule-writing loop — and a rule that compiles but runs pathologically,
such as a regex with catastrophic backtracking. That is bounded by YARA's own
`timeout` parameter at 5 seconds, plus a 20 KB cap on the rule source. The file
itself is never executed and never written to disk.

**"Why write your own rules instead of importing a public rule set?"**
Because I could not verify the licensing of the feeds for this project, and I
would rather ship six rules I can explain than a thousand of uncertain
provenance. It is the same choice made for the typosquat list and the brand list
elsewhere in this app: a short curated set, disclosed as not exhaustive, is more
honest than an impressive list nobody has checked. And the built-in set is the
demonstration — the custom-rule endpoint is the actual tool.
