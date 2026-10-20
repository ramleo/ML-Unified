Chapter 62TLS / Security-Headers Scanner


> Enter a domain and check its TLS and security headers the way Mozilla Observatory does. A real handshake verifies the certificate chain, expiry and protocol version, flagging deprecated SSLv3 and TLS 1.0/1.1, and a live request checks the six standard security headers. It refuses to connect to private, loopback or internal addresses, and gives a qualitative verdict with the actual warnings behind it rather than a numeric score.

## At a glance

| | |
|---|---|
| **Also called** | Live TLS + Headers · Zero ML |
| **Model or method** | ssl/socket + httpx (server-side, no ML) |
| **What you give it** | Domain name |
| **Headers Checked** | 6 |
| **Where it runs** | On the server, with a live external check |
| **Find it at** | `/tools/tls-security-headers-scanner` |

## Using the tool

### What this tool does
Type a domain and it's checked two real ways, the same audit style as
Mozilla Observatory or SSL Labs' Server Test: a real TLS handshake against
port 443 (checking certificate chain validity, expiry, and protocol
version), and a live HTTPS request checking for 6 standard security
response headers. Nothing is simulated — both checks make a genuine live
connection to the domain you type.

### The TLS check
- **Chain verification**: does the certificate actually chain up to a
  trusted root, the same check every browser does? A self-signed or
  otherwise untrusted certificate fails this — shown as the real
  verification error, not glossed over.
- **Expiry**: how many days until the certificate expires, flagged if
  already expired or expiring within 30 days.
- **Protocol version**: SSLv2/SSLv3/TLS 1.0/TLS 1.1 are all formally
  deprecated (RFC 8996) — flagged if negotiated instead of TLS 1.2/1.3.

When a certificate fails verification, its subject/issuer/expiry details
are deliberately **not shown** — those fields were never actually
validated, so displaying them would misleadingly suggest they're
trustworthy. The verification failure itself is the real finding.

### The security headers check
A live HTTPS request checks for 6 headers security-conscious sites set:
**Content-Security-Policy**, **Strict-Transport-Security** (HSTS),
**X-Frame-Options**, **X-Content-Type-Options**, **Referrer-Policy**, and
**Permissions-Policy**. This is the standard checklist real browser
security scanners use — not invented for this tool.

### Private/internal addresses are refused, not scanned
This tool opens a real network connection to whatever domain you type, so
before connecting it resolves the hostname and checks every resolved
address — if any of them is private, loopback, link-local, or otherwise
internal/reserved, the scan is refused with a clear message instead of
silently connecting. This prevents the tool being used to probe internal
network addresses it has no business reaching.

### Reading the result
One of five honest labels — never a fabricated numeric score:
- **Strong** — no issues found in either check.
- **Mostly good, one issue** — a single missing header or minor gap.
- **Weak configuration** — multiple missing headers or soft TLS issues.
- **Critical issues** — the certificate doesn't verify or has expired.
- **Could not fully scan** — the connection or HTTPS request itself
  failed (unrelated to the site's actual security posture, e.g. a
  timeout or the domain being unreachable).

### What this is (and isn't)
A passing TLS/headers check is a real, positive signal but not proof a
site has no other vulnerabilities — it says nothing about the
application's own code, authentication, or data handling. Conversely, a
"critical issues" result on TLS is a genuine, actionable finding (an
expired or untrusted certificate is a real problem any browser would also
flag), while a missing security header is a softer, defense-in-depth gap
rather than proof of an active vulnerability.

## What problem it solves

Two things about a website can be checked from the outside, before anyone logs
in, and both are commonly wrong:

**Is the TLS certificate healthy?** Expired certificates are one of the most
frequent outages there is, and they always expire at an inconvenient hour. A
chain that does not verify, or a connection that negotiates a protocol version
formally deprecated years ago, are quieter but worse.

**Does the site send the security headers browsers rely on?** Six headers do the
bulk of the work in stopping clickjacking, MIME sniffing, referrer leakage and a
good deal of cross-site scripting. They cost one line of configuration each and
are absent from a great many production sites, because nothing breaks when they
are missing.

This tool checks both. Give it a domain and it opens a real TLS connection,
inspects the certificate, fetches the site over HTTPS and audits the response
headers.

## How it works, step by step

1. **Normalise the host** — strip a scheme, a path, a port.
2. **Resolve it, and refuse private addresses.** This is a security control, not
   a convenience; see below.
3. **Open a real TLS connection** and read the certificate and the negotiated
   protocol version.
4. **Fetch the site over HTTPS** and look for the six headers.
5. **Build a warnings list**, then derive one qualitative verdict from it.

## The model or algorithm

No model. Two network checks, one refusal, and a verdict rule.

### The SSRF guard — the most important code in the tool

This endpoint takes a **user-supplied hostname** and makes the server open a TCP
connection to it. That is textbook **Server-Side Request Forgery**: the attacker
does not need network access themselves, they borrow the server's.

Left unguarded, this endpoint would let anyone:

- **port-scan the internal network** the server sits in, using connection
  success or failure as the oracle;
- **reach a cloud metadata endpoint** — `169.254.169.254` is the classic — which
  on many providers hands out instance credentials to anything that asks;
- **hit internal services** on `localhost` or a private range that were never
  meant to be reachable from outside.

So before any connection is made, the hostname is resolved and **every resolved
address is checked against private, loopback, link-local and reserved ranges**,
and the scan is refused if any match.

Two details in that sentence carry the weight.

**Check the resolved address, not the string.** Blocking the literal text
`localhost` or `127.0.0.1` is trivially bypassed — an attacker controls DNS for a
domain they own, and can point `scanner-test.example.com` at `127.0.0.1`. The
name looks perfectly public; only the resolution reveals the target.

**Check *every* address it resolves to.** A hostname can return several records,
and a check that only inspects the first can be defeated by a multi-record
response.

The docstring also draws the right contrast with the sibling tool: the email
authentication checker does DNS TXT lookups only and never opens a connection to
a user-supplied host, so it does not carry this risk. **The guard exists here
because this tool does something the other one does not.** Knowing which of your
endpoints have that property is most of the work.

The refusal message is written for the honest case too — a domain that does not
resolve to a public address may simply be internal, unreachable, or not real, and
the message says so rather than implying an accusation.

### The certificate checks

- **Expiry** — expired outright, or fewer than 30 days remaining, which is a
  warning rather than a failure because it is the actionable window.
- **Chain verification** — against `certifi`'s CA bundle. A failure here means
  self-signed, an incomplete chain, or an untrusted issuer.
- **Protocol version** — TLS 1.0, TLS 1.1 and SSLv3 are formally deprecated by
  **RFC 8996**, and negotiating one is reported with the RFC cited.

Citing the RFC is worth noticing: it turns "this looks old" into a checkable
claim against a published standard.

### The six headers

| Header | What it stops |
|---|---|
| `Content-Security-Policy` | controls which sources can load scripts and styles — the strongest single defence against XSS |
| `Strict-Transport-Security` | forces HTTPS on future visits, closing the downgrade window |
| `X-Frame-Options` | stops your page being framed — clickjacking |
| `X-Content-Type-Options` | stops the browser guessing a MIME type it was not given |
| `Referrer-Policy` | stops full URLs, and anything in them, leaking to other sites |
| `Permissions-Policy` | switches off camera, microphone, geolocation and similar |

The check is **presence, not correctness** — see *Limits*.

### The verdict rule

Written as a priority chain rather than a score, and the ordering is the
interesting part:

```
TLS connected but unverified or expired  →  "critical issues"
could not connect, or could not fetch    →  "could not fully scan"
two or more warnings                     →  "weak configuration"
exactly one warning                      →  "mostly good, one issue"
none                                     →  "strong"
```

The first branch has a comment explaining itself, and it is a genuinely good
catch:

> *A real TLS finding takes priority even if it also happens to block the header
> fetch — an expired or untrusted certificate usually causes exactly that. This
> is a genuine security issue, not merely "couldn't scan."*

Without that ordering, an **expired certificate would be reported as "could not
fully scan"**, because the expired certificate is what prevented the header
fetch. The tool would downgrade its most serious possible finding into an
inconclusive one. Distinguishing *"the scan failed"* from *"the scan succeeded and
the answer is bad"* is exactly the distinction a scanner must not get wrong.

**And the verdicts are qualitative, never a fabricated letter grade or
percentage.** The docstring names this as the same pattern as the email
authentication checker: a warnings list and an honest label, not a number nothing
justifies.

## Why these choices

**Why a live check rather than a database.** Certificate expiry and header
configuration are both current facts about a running server. A cached answer is
wrong the moment either changes, and both change often.

**Why presence-only header checking.** Parsing a Content-Security-Policy and
judging whether it is *good* is a substantial piece of work with real
disagreement about the answer. Presence is unambiguous, and absence is the
common case worth reporting.

**Why cite RFC 8996.** So the finding is verifiable rather than an opinion about
what is old.

**Why a warnings list feeding a verdict**, rather than a score. Each warning is a
specific, actionable sentence; the verdict is a summary of them. A score of 63
would tell you nothing about what to fix.

## How to read the output

- **Read the warnings, not the verdict.** Each one names a specific thing to
  change; the verdict just counts them.
- **"Critical issues" means a real TLS finding**, and it takes priority over the
  header check having failed as a consequence.
- **"Could not fully scan" is a genuine unknown**, not a pass.
- **Missing headers are a list, and CSP is the one that matters most.** The
  others are one-line fixes; a good CSP takes real work.
- **A certificate expiring in under 30 days is a warning by design** — it is the
  window in which you can still act calmly.
- **Present is not correct.** A `Content-Security-Policy` of
  `default-src *; script-src 'unsafe-inline'` counts as present here and protects
  almost nothing.
- **A blocked scan is not a finding about the site.** It usually means the domain
  does not resolve publicly.

## Limits

- **Headers are checked for presence, not quality.** A permissive CSP passes.
- **One request to the root URL.** Different paths can send different headers,
  and no other page is checked.
- **No cipher-suite analysis, no certificate-transparency check, no OCSP
  stapling, no HSTS preload-list check** — all of which a full-scale scanner
  does.
- **The verdict is a warning count**, so two minor issues outrank one serious
  one that happens to be alone.
- **Public hosts only, by design.** You cannot scan your own internal estate
  with it, and that is the SSRF guard working.
- **A single point in time.** No monitoring, no expiry alerting — which is the
  thing that would actually prevent the outage.
- **Redirects and CDNs** mean you may be measuring the edge, not the origin.

## Likely interview questions

**"You take a hostname from a user and connect to it. What could go wrong?"**
SSRF. The attacker gets the server to make requests on their behalf, so they can
port-scan the internal network using connection success as an oracle, hit
internal services that were never externally reachable, or reach the cloud
metadata endpoint at 169.254.169.254 and get instance credentials. The mitigation
is to resolve the hostname first and refuse if **any** resolved address is
private, loopback, link-local or reserved.

**"Why check the resolved IP rather than blocklisting `localhost`?"**
Because DNS is controlled by whoever owns the domain. An attacker points
`something.example.com` at `127.0.0.1` and a string blocklist sees a perfectly
ordinary public hostname. Only the resolution reveals the target. And you have to
check every address a name resolves to, not just the first, or a multi-record
response defeats it.

**"An expired certificate stops you fetching the headers. What does your tool
report?"**
"Critical issues", not "could not fully scan" — and that ordering is deliberate.
The expired certificate is the reason the header fetch failed, so a naive
implementation reports an inconclusive result for its most serious possible
finding. A scanner has to distinguish "I could not check" from "I checked and the
answer is bad", and when the failure to check *is* the finding, the finding wins.

**"Which of the six headers matters most, and why?"**
Content-Security-Policy, by a distance. The others each close one specific hole
and are a single line of configuration; CSP controls which sources can execute
script at all, which is the strongest single defence against cross-site
scripting. It is also the hardest to deploy, because a real policy has to
enumerate everything your site legitimately loads — which is why it is the one
most often missing.

**"Presence-only checking seems weak. Would you improve it?"**
Yes, and I would be clear that it is the tool's main limitation. A CSP of
`default-src *` with `unsafe-inline` passes this check and protects almost
nothing. Parsing and grading a policy is a real piece of work with genuine
disagreement about what counts as good, so presence is a defensible first pass —
but the honest next step is at least flagging the known-useless patterns rather
than counting the header as present.
