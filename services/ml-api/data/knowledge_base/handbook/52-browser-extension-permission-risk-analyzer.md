Chapter 44Browser Extension Permission Risk Analyzer


> Paste a Chrome or Edge extension's manifest.json and see what it is allowed to do. Checks individually-risky permissions (debugger, nativeMessaging, webRequestBlocking, cookies, history), broad host access, and dangerous combinations — broad host access plus network interception plus cookies together enable session hijacking on any site. This reads declared permissions, not behaviour: a legitimate password manager needs much the same access, so findings are framed as worth a closer look, never a judgement of intent.

## At a glance

| | |
|---|---|
| **Also called** | Local · No API Cost |
| **Model or method** | Rule-based (local) |
| **What you give it** | Text |
| **API Calls** | 0 |
| **Where it runs** | In your browser — the file never leaves your machine |
| **Find it at** | `/tools/extension-permission-analyzer` |

## Using the tool

### What this tool does
Paste the contents of a Chrome/Edge extension's \`manifest.json\`. The tool
parses its declared permissions, host access, and content-script injection
points, then checks them against a documented risk taxonomy: individually
risky permissions (\`debugger\`, \`nativeMessaging\`, \`webRequestBlocking\`,
\`cookies\`, \`history\`, \`tabs\`, \`proxy\`, \`clipboardRead\`,
\`management\`, and more), broad host access (\`\`,
\`*://*/*\`), and a fixed list of known **dangerous combinations** —
permission pairs that together unlock a real capability neither one grants
alone.

### Purpose
An extension's manifest is a public, honest declaration of what it's
*allowed* to do — before you install anything, that's real, checkable
information. This tool makes that declared-permission surface legible at a
glance, based on real documented Chrome-extension security research (in the
spirit of published studies like Duo Labs' extension permission analyses),
so you can spot combinations worth a closer look before granting them.

### How to use it
1. Open the extension's \`manifest.json\` (from its source, an unpacked
   \`.crx\`, or the Chrome Web Store's "view source" option where available)
   and copy its full contents.
2. Paste it into the text box and click **Analyze permissions**.
3. Review the overall risk verdict, any triggered dangerous combinations,
   and the full per-permission breakdown.

### A worked example
Click **Load sample manifest** to load a synthetic example declaring
\`\` + \`webRequestBlocking\` + \`webRequest\` + \`cookies\` +
\`tabs\` + \`history\`. Clicking **Analyze permissions** returns **High
risk**, driven by the "Broad host access + network interception + cookie
access" combination — the tool explains that this combination can
intercept network traffic AND read/write cookies across every site, enough
to hijack sessions on any site the user visits. Now try a manifest
declaring only \`storage\`, \`notifications\`, and \`contextMenus\` — the
verdict correctly drops to **Low risk**, since none of those imply any data
access.

### Reading the result
- **Overall risk** (low/medium/high) — driven by the single
  highest-severity permission or combination found; never averaged down,
  so one critical combination makes the whole result high even if every
  other permission is harmless.
- **Dangerous permission combinations** — the specific documented combos
  that fired, each with a plain-language explanation of the real
  capability they unlock together.
- **Declared permissions** — every named permission found, each with its
  own individual risk level and a one-line explanation.
- **Warnings** — call out broad host access specifically, since it's the
  ingredient most combinations depend on.

### Notes & limits
- **Static declared-permission analysis only — not a behavioral scan.**
  This does not inspect the extension's actual code or runtime behavior,
  and cannot tell you whether a permission is being misused versus
  legitimately needed.
- A high-risk result is "worth a closer look," not proof of malicious
  intent — a password manager, for example, can legitimately need broad
  host access and cookie access to do its actual job.
- Supports both Manifest V2 (URL patterns inside the single \`permissions\`
  array) and V3 (\`host_permissions\` as a separate field) formats.
- Entirely client-side — nothing you paste is sent anywhere.

## What problem it solves

A browser extension is the most privileged software most people install
casually. It sits inside the browser, past every network boundary, past TLS,
inside the authenticated session. An extension with the right permissions can
read your email as you read it, take your session cookies, watch every request
you make, and change any page before you see it.

Chrome does show a permission dialog at install time. It has two problems.
Nobody reads it, and even read carefully it says things like "Read and change
all your data on the websites you visit" — technically accurate and almost
content-free. It also lists permissions **individually**, which is exactly the
wrong granularity: the danger is usually in the combination.

This tool takes a `manifest.json` — the file every extension ships, obtainable
from any unpacked extension or GitHub repository — and explains what the
declared permissions actually allow. Each permission gets a risk level and a
sentence about the concrete capability it grants, broad host access is flagged
separately, and a set of rules looks specifically for **dangerous
combinations**.

Everything runs in the browser on pasted text. No upload, no network call, no
store lookup.

## How it works, step by step

1. **Paste a `manifest.json`.**
2. **Parse it**, with a clear message if it is not valid JSON or not an object.
3. **Classify each declared permission** against a documented risk taxonomy.
4. **Detect broad host access** across the three separate places it can hide.
5. **Evaluate the combination rules.**
6. **Report** every finding with its reasoning, sorted worst first, plus a
   single overall level.

## The model or algorithm

### The permission taxonomy

Twenty-three commonly seen permissions, each with a level and an explanation of
the capability rather than a restatement of the name. The classification
reflects Chrome's own permission-warning tiers and independent extension
security research, notably the Duo Labs studies — not an invented scale.

The **high** tier is worth reading in full, because each entry is there for a
specific reason:

| Permission | What it actually allows |
|---|---|
| `debugger` | Full Chrome DevTools Protocol access to any attached tab — read or modify anything on the page, intercept all traffic, execute arbitrary code in page context |
| `nativeMessaging` | Exchange messages with a native application on the machine — **escapes the browser sandbox entirely** |
| `webRequestBlocking` | Synchronously intercept, block or rewrite every network request the browser makes |
| `proxy` | Redirect all browser traffic through an arbitrary proxy server |
| `cookies` | Read and write cookies for any site it has host permission for, **including session and auth cookies** |
| `history` | Read the entire browsing history |

Two distinctions in the taxonomy are more instructive than the list itself.

**`webRequest` versus `webRequestBlocking`.** Observation is medium; the
ability to block and rewrite is high. Read-only visibility into traffic is bad;
the power to modify responses before the page sees them is a different
category.

**`clipboardRead` versus `clipboardWrite`.** Reading is medium, writing is low.
The clipboard frequently holds a password or a 2FA code that was copied seconds
ago. Writing is not harmless — clipboard-hijacking scams that swap a
cryptocurrency address are real — but it is a smaller exposure.

**`declarativeNetRequest` is low while `webRequestBlocking` is high**, and that
gap is the entire security argument for Manifest V3. Declarative rules are
declared statically up front and evaluated by the browser; the extension never
sees the request and cannot write a rule at runtime from data it scraped off a
page. Same broad purpose, far less capability.

**`activeTab` is low by design.** It grants access to one tab, only after the
user clicks the extension. It is the model everything else should aspire to, and
an extension using it instead of `` is telling you something good
about its authors.

An unrecognised permission is reported as **unclassified**, not flagged. The
alternative — treating anything unknown as suspicious — would bury the real
findings under noise from every ordinary permission not on the list.

### Broad host access, and the three places it hides

This gets its own detection path because a manifest can request access to every
site in three separate keys, and checking only the obvious one misses the
others:

- `host_permissions` — the Manifest V3 home for it.
- `permissions` — where Manifest V2 put host patterns, still seen in the wild.
- `content_scripts[].matches` — a content script's own match patterns, which
  grant page access independently of anything in either list above.

All three are collected and tested against a broad-pattern check. The literals
``, `*://*/*`, `http://*/*` and `https://*/*` are obvious. Less
obvious, and caught by a regular expression, is the **wildcard second-level
domain** — `*://*.com/*`, or `http://*.co.uk/*`. That is not narrow access. It
is every commercial site on the internet, written in a way that looks specific
at a glance.

### Combination rules

This is the part the browser's own dialog does not do, and it is the tool's
main contribution.

The framing matters: **broad host access alone is often legitimate, and a
sensitive permission alone is often legitimate.** A password manager genuinely
needs `` and `cookies`. An ad blocker genuinely needs to see every
request. Flagging either in isolation produces a warning on almost every useful
extension, which trains people to ignore warnings.

What is worth flagging is the specific pairing that unlocks a capability
neither permission provides alone:

| Combination | Risk | The capability it unlocks |
|---|---|---|
| Broad hosts + webRequest(Blocking) + cookies | high | Intercept traffic *and* read/write cookies on every site — enough to hijack sessions anywhere the user goes |
| Broad hosts + script injection | high | Run arbitrary JavaScript in any page — effectively full control of every site's content |
| `nativeMessaging` + `downloads` | high | Pass data to a native application *and* read/write downloaded files — a plausible exfiltration or local-tampering path |
| Broad hosts + `clipboardRead` | medium | Read the clipboard while present on every site |
| `debugger` | high | Listed as a rule of one, because it is already full remote control of any attached tab and needs no partner |

Script injection is tested as either a non-empty `content_scripts` array **or**
the `scripting` permission, because Manifest V2 and V3 express the same
capability differently and an extension can use either.

### The overall level

The maximum across all findings — permissions and combinations alike. Not an
average, not a count.

A single `debugger` permission in an otherwise clean manifest is a critical
finding, and averaging would dilute it into "mostly fine". For a risk summary,
the maximum is the only defensible aggregate: what matters is the worst thing
present, not the general tenor.

## Why these choices

**Why static manifest analysis and not the extension's code?** Because the
manifest is a **declaration of capability**, and capability is the thing worth
reasoning about. Code review of a minified, obfuscated bundle is a much larger
job and can be defeated by remote code loading — but an extension cannot
exercise a permission it never declared. The manifest is the honest upper bound
on what the extension can ever do, however its code changes.

**Why explain rather than score?** A number invites a threshold and nothing
else. The purpose here is for someone to read "can read and write session
cookies on every site you visit" and decide whether their note-taking extension
should be able to do that. The reasoning is the product; the level is just
sorting.

**Why fully client-side?** No good reason to send it anywhere. It is pasted
text and a lookup table, and keeping it local means it works offline and stores
nothing.

**Why include `optional_permissions`?** Because optional means "requested
later", not "not requested". An extension that can prompt for `debugger`
after installation can obtain `debugger`, and a review that ignores the
optional list misses the whole point of that mechanism.

**Why exclude host patterns from the permission list?** Entries containing
`://` or equal to `` are filtered out of the permission classification
because they are handled by the dedicated host-access path. Without that filter
they would appear twice — once as an unclassified permission and once as broad
host access.

## How to read the output

**Start with the combinations, not the permission list.** The list tells you
what was asked for; the combinations tell you what those requests add up to.

**Then apply the only test that matters: does this extension need this to do
its stated job?** A password manager with `` and `cookies` is
expected. A colour-picker with the same pair is not, and the tool cannot tell
the difference because it has no idea what the extension claims to do. That
judgement is yours and it is the whole point of showing the reasoning.

**A "low" overall level is not an endorsement.** It means nothing in the
declared set matched a documented high-risk pattern. The extension can still
exfiltrate everything it legitimately touches, and can still be sold to a new
owner tomorrow.

**Unclassified permissions are worth a look.** Not flagged, but not vetted
either.

## Limits

- **The manifest is a declaration, not behaviour.** It bounds what an extension
  *can* do. What it *does* with those permissions requires code review, and a
  benign-looking extension can be updated into a malicious one without changing
  a single permission — which is precisely how several real extension
  compromises played out.
- **Chrome and Edge only.** Firefox's WebExtensions manifest overlaps heavily
  but is not identical, and Safari's model differs more.
- **The taxonomy is not exhaustive.** Twenty-three permissions; anything else
  is reported as unclassified, and a genuinely dangerous new permission would
  be missed until the list is updated.
- **The combination rules are a fixed, hand-written list.** Real dangerous
  pairings outside those five exist.
- **No remote-code-loading detection.** An extension with modest permissions
  that fetches and evaluates code from a server is a well-known pattern and is
  not visible in the manifest.
- **No context about the extension's purpose**, which is the input a real
  judgement needs most.
- **No supply-chain signal** — nothing about the publisher, ownership changes,
  update history or reputation, all of which matter as much as the manifest.

## Likely interview questions

**"Why analyse combinations instead of individual permissions?"**
Because individual permissions are usually justifiable and the danger is
emergent. A password manager legitimately needs broad host access and cookie
access; an ad blocker legitimately needs to see every request. Flagging either
alone produces a warning on nearly every useful extension, and a warning that
always fires is ignored. Broad hosts *plus* request interception *plus* cookies
is different in kind — that specific set is enough to hijack a session on any
site the user visits, and it is worth interrupting someone for.

**"What is the difference between `webRequest` and `declarativeNetRequest`, and
why does it matter?"**
`webRequest` with blocking lets the extension's own code see and modify every
request synchronously — full visibility and full control, with the logic
running in the extension. `declarativeNetRequest` has the extension declare
static rules up front which the browser evaluates itself; the extension never
sees the request and cannot generate rules at runtime from data it scraped.
That shift is the central security argument for Manifest V3: same broad
functionality for content blocking, dramatically less capability and less
visibility into user traffic. It is also why the transition was contested — the
constraint that improves security also limits what sophisticated blockers can
do.

**"Someone requests `*://*.com/*`. Is that narrow access?"**
No, and it is designed to look like it is. That pattern matches every `.com`
domain, which is most of the commercial web. The tool has a specific regular
expression for wildcard second-level domains because reading the pattern
casually gives entirely the wrong impression — it looks like a scoped request
and is nearly equivalent to ``.

**"Your tool says low risk. Is the extension safe?"**
No, and the output is worded to avoid implying it. Low means nothing in the
declared permissions matched a documented high-risk pattern. It says nothing
about what the code does with the permissions it has, nothing about a future
update, and nothing about the publisher. The most common real-world extension
compromise is a popular, modestly-permissioned extension being sold or having
its developer account phished, then shipping a malicious update to an existing
install base — none of which a manifest can reveal.

**"Why the maximum rather than an average or a weighted score?"**
Because risk is not additive. An extension with one critical permission and
twenty harmless ones is critical, and averaging would report it as mild. There
is also no principled weighting available — the weights would be invented, and
inventing numbers to produce a more sophisticated-looking output is worse than
reporting the worst finding plainly.

**"How would you extend this?"**
Three directions, in order of value. Diff two manifests to show what a version
bump changed, since permission creep across updates is where a lot of real risk
appears. Cross-reference the store listing so the tool knows what the extension
claims to do — the need-versus-request judgement is currently entirely on the
reader. And static analysis of the bundle for remote-code-loading patterns,
because that is the main way a low-permission extension does something the
manifest cannot predict.
