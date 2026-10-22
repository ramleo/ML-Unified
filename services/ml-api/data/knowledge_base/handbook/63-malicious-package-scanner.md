Chapter 55Malicious Package Scanner


> Paste a package.json, requirements.txt or a source file and see what a supply-chain reviewer would flag. Checks for npm install-script hooks, dependency names that typosquat well-known packages, dynamic execution calls (eval, exec, subprocess), obfuscated high-entropy strings, embedded URLs, hardcoded secrets, SQL built by string interpolation, and unsafe deserialization. It matches attacker techniques rather than known signatures, which is what lets it flag packages nobody has seen before. Every hit is real evidence to judge, never a safe/malicious verdict. Runs fully in your browser.

## At a glance

| | |
|---|---|
| **Also called** | Local · No API Cost |
| **Model or method** | Static heuristics (local) |
| **What you give it** | Pasted manifest or source code |
| **API Calls** | 0 |
| **Where it runs** | In your browser — the file never leaves your machine |
| **Find it at** | `/tools/malicious-package-scanner` |

## Using the tool

### What this tool does
Real supply-chain attacks against npm/PyPI use a small set of well-known
techniques over and over: a malicious install script that runs
automatically the moment a package is installed, or a package name that's
one keystroke away from a popular one (a typosquat). This tool
static-analyzes pasted manifest files and source code for those exact
techniques — the same approach open-source tools like Datadog's GuardDog
use: pattern-matching common attacker techniques, not comparing against a
database of known-malware signatures. That's what lets this kind of check
catch a malicious package that's never been seen before — it doesn't need
to have seen it.

### Two independent scan modes

#### Manifest scan (package.json / requirements.txt)
- **Suspicious lifecycle scripts** — npm's \`preinstall\`/\`install\`/
  \`postinstall\` fields in \`package.json\` run automatically the instant a
  package is installed, before any of its actual code is even imported.
  This is a real, repeatedly-abused technique in genuine npm supply-chain
  incidents. Any of these three script fields being present is flagged,
  with the actual script content shown so you can judge it yourself.
- **Typosquat check** — every dependency name is compared (via edit
  distance) against a curated list of ~150-200 well-known real npm/PyPI
  package names. A name 1-2 characters off from a well-known one (like
  \`lodahs\` vs \`lodash\`, or \`reqeusts\` vs \`requests\`) is flagged as a
  possible typosquat.

#### Source code scan (JS/TS or Python)
- **Suspicious API calls** — \`eval(\`, \`new Function(\`,
  \`child_process.exec\`, Python \`exec(\`/\`eval(\`/\`subprocess.*\`/
  \`os.system(\` — real techniques for running dynamically-constructed or
  fetched code, rather than the package's own plainly-readable source.
- **Obfuscation tells** — long string literals with unusually high
  character-level entropy (the same Shannon-entropy technique this site's
  DNS Tunneling Detector and Malware-Image-Triage tools use) — a common
  tell for a base64/hex-encoded payload sitting next to an \`eval\`/\`exec\`
  call, the classic "decode, then run" pattern.
- **Embedded URLs** — any hardcoded network address found in the source,
  surfaced as evidence worth reviewing (not scored or judged — that's a
  different job from this tool's).
- **Hardcoded secrets** — recognizable real secret formats (AWS
  \`AKIA...\` access key IDs, GitHub \`ghp_\`/\`github_pat_\` tokens, Slack
  \`xox...\` tokens, PEM private-key blocks) plus a generic
  \`api_key\`/\`password\`/\`token\` \`= "..."\` assignment pattern — obvious
  placeholder values (\`changeme\`, \`your-password\`, etc.) are skipped to
  cut noise from docs/config examples. Matched values are shown partially
  masked in the UI.
- **SQL-injection-shaped query building** (CWE-89) — a line naming a SQL
  keyword (\`SELECT\`/\`INSERT\`/\`UPDATE\`/\`DELETE\`) combined with an
  f-string, template-literal, string-concatenation, or \`%\`-format
  interpolation, rather than a properly parameterized placeholder.
- **Insecure deserialization** (CWE-502) — Python's classic, well-documented
  unsafe patterns: \`pickle.loads(\`/\`pickle.load(\`, \`marshal.loads(\`, and
  \`yaml.load(\` used without \`SafeLoader\` (PyYAML's own documented fix).

### What this is (and isn't)
Every result here is a **signal, not a verdict** — real, non-fabricated
evidence for a human to weigh, never a fabricated "malicious"/"safe"
label. A flagged lifecycle script might be completely legitimate (many
real packages compile native code on install); a flagged typosquat could
just be a name that happens to be close to a popular one; a high-entropy
string could be a genuine cryptographic key or compressed asset, not a
payload. Conversely, a clean result here is **not proof of safety** — this
only sees what's pasted, checks a curated (not exhaustive) list of
well-known package names, and cannot detect more sophisticated evasion
(code that's obfuscated below the entropy threshold, or a malicious
payload fetched at runtime from a URL that isn't hardcoded in the source).

## What problem it solves

A modern application depends on hundreds of packages it never reads. `npm
install` on a typical project pulls in a thousand or more transitive
dependencies, each one arbitrary code from a stranger, each one running with your
permissions.

That is the **software supply chain**, and it is the most productive attack
surface there is. The known incidents are not theoretical — `event-stream`,
`ua-parser-js`, `colors`, `node-ipc` — and the pattern repeats: the package
itself is fine, the maintainer's account is compromised or the maintainer turns,
and a malicious version publishes to a package that a million projects already
trust.

Signature-based scanning cannot catch a new one, because there is no signature
until someone has been hit. This tool takes the other approach: **look for the
techniques**, not the specimens.

Everything runs in the browser on pasted text. No network, no upload, no
registry lookup.

## How it works, step by step

1. **Paste a `package.json`, a `setup.py`, or source code.**
2. **Check dependency names** against a curated list of well-known packages,
   flagging near-misses.
3. **Check install-time lifecycle hooks** — `preinstall`, `install`,
   `postinstall`.
4. **Scan the source for suspicious API calls**, hardcoded secret formats,
   unsafe deserialisation and encoded blobs.
5. **Report each finding** with its line and what makes it suspicious.

## The model or algorithm

The approach follows the published static-analysis style used by open-source
tools like Datadog's **GuardDog** — pattern-matching attacker *techniques* rather
than comparing against known-malware signatures. That is precisely why it can
catch a package nobody has seen before.

### Typosquatting, via Levenshtein distance

An attacker publishes `reqeusts` and waits for someone to mistype `requests`.
Install-time code runs, and the package may even re-export the real library so
nothing appears broken.

Detection is edit distance — the minimum number of single-character insertions,
deletions or substitutions to turn one string into another, computed with the
standard dynamic-programming table:

| Pair | Distance |
|---|---|
| `reqeusts` → `requests` | 2 (a transposition) |
| `loadash` → `lodash` | 1 |
| `crossenv` → `cross-env` | 1 |

A **distance of 1 or 2 from a well-known name, while not being that name**, is
the signal. Small distance means plausible typo; being on the list means somebody
would actually make that typo.

**The reference list is curated and disclosed** — the popular npm and PyPI
packages — with the explicit caveat in the code that *a typosquat of a name not
on this list will not be flagged by this check*. Same honest-list pattern as the
QR detector's brands, the YARA rule set, and the DNS tool's public suffixes.

### Install-time lifecycle hooks — the highest-value check

`preinstall`, `install` and `postinstall` in a `package.json` run **automatically
when the package is installed**. Not when you import it. Not when you call it.
The moment `npm install` completes.

That is what makes them the classic malicious-package vector, and why they
deserve their own check:

- Code executes before anyone has read a line of the package.
- It runs in CI, on developer laptops, and in Docker builds.
- It has the environment — which means `.npmrc` tokens, AWS credentials, SSH
  keys, environment variables.

Plenty of legitimate packages use install hooks to compile native extensions, so
it is not a verdict. But it converts "this is a dependency" into "this is code
that will run on my machine today", which changes what needs reading.

### Suspicious API patterns

Grouped by what an attacker needs, which is the useful way to read them:

**Dynamic execution** — `eval(`, `new Function(`, Python's `exec(`. Turning a
string into code at runtime is how an obfuscated payload is unpacked, and it is
rare in honest library code.

**Command execution** — `child_process.exec`, `subprocess.run`, `os.system`. A
library that needs a shell is a library doing something beyond its stated job.

**Unsafe deserialisation** — `pickle.loads`, `marshal.loads`, and
`yaml.load(` **without** `SafeLoader`. Python's pickle executes arbitrary code
during deserialisation by design, and `yaml.load` without a safe loader can
instantiate arbitrary objects.

The `yaml.load` rule is worth pointing at as a piece of detection design: it
carries a `requireAbsent` condition, so the pattern only fires if `SafeLoader` is
**not** present. Checking for the *absence of the mitigation* rather than the
presence of the call is what keeps it from firing on every correct use.

### Hardcoded secret formats

Credentials have recognisable shapes, and that makes them findable:

| Credential | Shape |
|---|---|
| AWS access key | `AKIA` + 16 uppercase alphanumerics |
| GitHub token | `ghp_`/`gho_` + 36 characters, or `github_pat_…` |
| Slack token | `xoxb-`, `xoxp-`, `xoxa-`… |
| Private key | `-----BEGIN … PRIVATE KEY-----` |

These are structural formats, not guesses, which is why they can be matched with
confidence. In a package, a hardcoded credential is either an accident worth
knowing about or an exfiltration destination.

### Encoded blobs

Long base64 or hex strings — the standard way to hide a payload from a reader,
usually paired with an `eval` or `exec` a few lines away. High entropy in
source code is not normal and is worth surfacing.

## Why these choices

**Why techniques rather than signatures.** A signature database only contains
packages someone has already been attacked by. Attacker techniques change far
more slowly than payloads, so a technique-based scanner catches the *next* one.
The cost is false positives, which is why every finding is shown with its line
and its reason rather than as a verdict.

**Why in the browser.** A `package.json` is not especially sensitive, but source
code often is, and there is no reason for it to leave the machine when the whole
analysis is regular expressions over text.

**Why no registry lookup.** No network means no rate limits, no dependency on a
registry being up, and nothing revealed about what you are inspecting. It also
means no package age, download count or maintainer history — genuinely useful
signals that are unavailable offline, and that is the trade.

**Why disclose the list is partial.** Because a scanner that implies completeness
is worse than one that states its scope. A user who knows the reference list is
curated will check an unusual dependency by hand; one who believes it is
exhaustive will not.

## How to read the output

- **Install hooks are the thing to read first.** They are the difference between
  code you might run and code that *will* run.
- **Every finding is dual-use.** `eval` appears in real libraries; `child_process`
  is legitimate in build tools. The question is always whether *this* package has
  a reason.
- **Look at the combination.** A postinstall hook plus base64 plus `eval` plus an
  outbound request is not four findings, it is one attack.
- **A typosquat flag is high-signal.** Distance 1 from a hugely popular package
  is rarely innocent — but check the direction, since a legitimate fork can look
  the same.
- **Nothing found means nothing matched.** Obfuscation defeats pattern matching
  by design.
- **Line numbers are the point.** Go and read the line.

## Limits

- **Static analysis only.** No execution, no sandbox, no behavioural
  observation.
- **Obfuscation beats it.** String concatenation, character-code arrays and
  encoding all evade regular expressions — and a package doing that is itself a
  signal, which this tool does not currently score.
- **The known-package list is curated**, so typosquats of anything else are
  invisible to that check.
- **What you paste is what is scanned.** It does not walk a dependency tree, and
  the real risk is usually transitive — the package you audited is fine and its
  fourteenth-level dependency is not.
- **No registry metadata** — no package age, no download counts, no maintainer
  change history, no version diffing. Comparing a new version against the
  previous one is one of the strongest available signals and needs the network.
- **npm and PyPI shapes only.**
- **False positives are expected**, by design; the alternative is missing novel
  attacks.

## Likely interview questions

**"Why heuristics instead of a malware database?"**
Because a database only contains what has already been used against someone. In
supply-chain attacks the package is usually trusted right up until the malicious
version publishes, so there is no signature at the moment it matters. Attacker
*techniques* — install hooks, dynamic execution, encoded payloads, credential
exfiltration — change far more slowly than payloads, so matching those can catch
the first victim's case. The cost is false positives, and that is the right trade
for a tool that shows you lines to read rather than issuing a verdict.

**"Why are install hooks singled out?"**
Because they run automatically on `npm install`, before anyone has read the
package or imported it — in CI, on laptops, inside Docker builds — with full access
to the environment, which is where the `.npmrc` token, the AWS credentials and
the SSH keys live. Every other suspicious pattern requires the code to be called;
an install hook does not. Legitimate packages use them to compile native
extensions, so it is not a verdict, but it changes what you need to read before
installing.

**"How does the typosquat detection work?"**
Levenshtein distance — the minimum number of single-character edits between two
strings — against a curated list of very popular package names. Distance 1 or 2
while not being an exact match is the flag: `reqeusts` is two edits from
`requests`, `loadash` is one from `lodash`. Small distance means it is a
plausible typo, and being near a *popular* name means somebody will actually make
it.

**"Your `yaml.load` rule has a `requireAbsent` condition. Why?"**
Because `yaml.load` is only dangerous without a safe loader — with `SafeLoader` it
is the correct call. Flagging every occurrence would fire on all the correct uses
and train people to ignore the finding. Checking for the *absence of the
mitigation* rather than the presence of the call is what makes the rule
precise, and it is the same instinct as requiring co-occurrence in the YARA rules.

**"What's the biggest gap?"**
Transitive dependencies. This scans what you paste, and the real risk is almost
always four levels down in a tree you never look at — the package you audited is
fine and its dependency's dependency is not. Closing that needs a lockfile walk
and registry metadata: package age, download counts, maintainer changes, and
diffing a new version against the previous one, which is one of the strongest
signals available and needs the network this tool deliberately does not use.
