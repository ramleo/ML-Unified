Chapter 41Attack-Surface / Exposed-Path Scanner


> Enter a domain and see what it exposes to the open internet. Four passive checks run live: sensitive paths like .git/HEAD and .env (only flagged when the response really is that file, not merely a 200), Apache/nginx directory listings, CMS fingerprinting from the standard generator tag, and a short common-port connect check. It refuses to touch private, loopback or internal addresses, and reports real findings for you to weigh rather than a made-up risk score.

## At a glance

| | |
|---|---|
| **Also called** | Live Recon · Zero ML |
| **Model or method** | httpx + socket (server-side, no ML) |
| **What you give it** | Domain name |
| **Passive Checks** | 4 |
| **Where it runs** | On the server, with a live external check |
| **Find it at** | `/tools/attack-surface-scanner` |

## Using the tool

### What this tool does
Type a domain and four real, entirely passive checks run against it —
the same kind of misconfiguration checks a real recon phase (or a
legitimate bug-bounty researcher) starts with. Nothing here is
exploitation: every check is a plain GET/HEAD request or a bare TCP
connect, never an attempt to actually breach anything.

### The four checks

#### 1. Exposed sensitive paths
Checks for a curated list of commonly-exposed files: \`.git/HEAD\`,
\`.git/config\`, \`.env\`, \`.DS_Store\`, \`.svn/entries\`, \`backup.zip\`,
\`.aws/credentials\`. A path is only flagged when the response is a real
200 **and** its content actually looks like the real file (e.g.
\`.git/HEAD\` containing \`ref: refs/\`, a ZIP file's real magic bytes) —
this avoids false-flagging sites that return 200 for every URL with a
custom "not found" page instead of a real 404.

#### 2. Directory listing
Checks a few common directory paths (\`/uploads/\`, \`/backup/\`,
\`/images/\`, \`/files/\`) for the standard Apache/nginx "Index of /"
autoindex page — a real, well-known misconfiguration that exposes a raw
file listing to anyone.

#### 3. CMS fingerprint (passive only)
Fetches the homepage once and looks for the standard
\`\` tag — the same passive technique
real tools like Wappalyzer use. Only reports a CMS/version if the site
actually declares one in that tag; never guesses.

#### 4. Common ports
A short, well-known list of ports (FTP 21, SSH 22, Telnet 23, SMTP 25,
MySQL 3306, PostgreSQL 5432, Redis 6379, MongoDB 27017) gets a plain TCP
connection attempt — reporting only open/closed. No banner is read, no
protocol handshake beyond the raw TCP connect itself.

### Private/internal addresses are refused, not scanned
This tool opens real connections to whatever domain you type, so before
connecting it resolves the hostname and checks every resolved address —
if any is private, loopback, link-local, or otherwise internal/reserved,
the scan is refused with a clear message instead of silently connecting.
Same protection as this site's TLS/Security-Headers Scanner.

### What this is (and isn't)
This is real, non-exhaustive recon — a genuinely clean result across all
four checks is a real positive signal, but it is **not** proof a site has
no vulnerabilities. It doesn't check application logic, authentication,
input handling, or anything beyond these four specific, well-known
misconfiguration classes. An open port isn't automatically a problem
either — plenty of legitimate servers run SSH or a database port openly
by design; it's evidence worth reviewing in context, not an automatic
verdict.

## What problem it solves

Most sites are not compromised through a clever exploit. They are compromised
because something was left where anyone could reach it.

A `.git` directory deployed to production, so the entire source history —
including the credentials someone committed and later removed — can be
reconstructed by anyone who asks for it. A `.env` file served as static content,
containing the database password. A directory with autoindex on, listing every
uploaded file. A database port open to the internet because a firewall rule was
never applied.

None of these requires an attacker to break anything. They require an attacker to
**look**, which is the first thing any of them does. This tool looks in the same
places, so you find them first.

Everything it does is **passive**: GET and HEAD requests, and plain TCP connects.
No exploitation, no fuzzing, no interaction beyond what a browser does.

## How it works, step by step

1. **Resolve the host and refuse private addresses** — the same SSRF guard as the
   TLS scanner, from the same shared module, because this tool opens sockets to a
   user-supplied host and has the identical risk profile.
2. **Request each sensitive path** and check whether the response *content*
   actually looks like the real file.
3. **Request common directories** and look for an autoindex page.
4. **Fetch the homepage** and read the `` tag, if there is
   one.
5. **Attempt a TCP connect** to eight common service ports, concurrently.
6. **Return a findings list** — never a score.

## The model or algorithm

### Content matching, not status codes — the key idea

The obvious way to check for an exposed `.env` is to request it and see if the
status is 200. That approach is close to useless, and the reason is the most
transferable thing in this chapter.

**Very many sites return 200 for every path**, serving a custom error page or a
single-page application's `index.html` for anything unmatched. A status-code
check against such a site reports every sensitive path as exposed, and the tool
is immediately worthless.

So each path is paired with a **content pattern that only the real file would
match**:

| Path | Pattern | Why it identifies the real file |
|---|---|---|
| `/.git/HEAD` | `ref:\s*refs/` | Git's HEAD file always begins with a ref pointer |
| `/.git/config` | `\[core\]` | every Git config has a `[core]` section |
| `/.env` | `^[A-Za-z_]\w*\s*=` (multiline) | dotenv's `KEY=value` line structure |
| `/.DS_Store` | `Bud1` | the real macOS DS_Store **magic bytes** |
| `/backup.zip` | `^PK` | the real ZIP **magic bytes** |
| `/.aws/credentials` | `\[default\]` or `aws_access_key_id` | the AWS credentials file format |
| `/.svn/entries` | `^\d+$` | Subversion's numeric first line |

Two of these use **magic bytes** — the file-format signature at the start of the
file — which is as close to unambiguous as this gets. An HTML error page does not
begin with `PK`.

The general principle: **verify the thing you are claiming to have found, not a
proxy for it.** A 200 status is a proxy. The file's own content is the thing.

### Directory listing

Apache and nginx autoindex pages have a consistent tell: `Index of
/…`. A handful of commonly-exposed directories are checked for it.

Autoindex matters because it turns "an attacker must guess filenames" into "an
attacker is handed the list" — which is often the difference between a
misconfiguration and a breach.

### CMS fingerprinting, and its deliberate restraint

Only the standard `` tag is read. The docstring is
explicit: it **never guesses a CMS or version that is not actually declared.**

That restraint is the point. Real fingerprinting infers a platform and version
from asset paths, header quirks, cookie names and response timing — and infers
wrongly a fair amount of the time. A tool that reports "WordPress 5.8, known
CVEs" from a guess sends someone chasing a vulnerability in software they do not
run. Reading a tag the site chose to publish is a fact; everything else here would
be an inference presented as one.

### Port scanning, and the concurrency fix

Eight ports, each a plain TCP connect with a 2-second timeout: FTP, SSH, Telnet,
SMTP, MySQL, PostgreSQL, Redis, MongoDB.

Three of those are the ones that matter most — **MySQL, PostgreSQL, Redis and
MongoDB should never be reachable from the internet**, and Redis and MongoDB
historically shipped with no authentication by default, which is how a great many
databases were found and ransomed.

**No banner grab and no protocol interaction.** The tool learns whether a
connection is accepted and nothing more. That keeps it passive: connecting is
what any client does; speaking the protocol is interaction.

There is a good performance note in the code. Sequential checks would take up to
`2s × 8` because a **firewall that silently drops** a probe, rather than actively
refusing it, makes you wait the whole timeout. Measured at roughly **18 seconds**
for this check alone against a real host. Running them in a thread pool makes it
one timeout instead of eight.

That detail is also a small lesson in network behaviour: a closed port refuses
immediately, a *filtered* port says nothing at all, and the difference is entirely
in how long you wait.

### The SSRF guard, shared

Same module as the TLS scanner — resolve first, refuse any private, loopback,
link-local or reserved address. The comment notes the identical risk profile,
which is the right way to think about it: the guard belongs to the *capability*
of opening a socket to user-supplied input, not to a particular tool.

Here it is arguably even more important, because this endpoint **is a port
scanner**. Unguarded, it would let anyone scan the internal network the server
sits in.

## Why these choices

**Why passive only.** Passive checks are the ones you can legally and ethically
run against a host — they are what a browser or a search engine already does.
Anything active is unauthorised testing, and a demo tool has no business doing
it.

**Why a findings list and no score.** Same pattern as the TLS and email tools.
Each finding is a specific thing to fix; a score of 71 tells you nothing and
invites arguing with the number rather than fixing the problem.

**Why so few paths.** The list is the high-value, low-false-positive set. A
thousand-path wordlist is what a dedicated tool does, and it turns a passive
check into something that looks like an attack in the target's logs.

## How to read the output

- **An exposed `.git` is the most serious finding here.** The whole repository
  history is reconstructable — including secrets that were committed and later
  removed, which are still in the history.
- **An exposed `.env` is the fastest to exploit.** It is credentials, in plain
  text.
- **An open database port is a finding even if authentication is on.** It should
  not be reachable at all.
- **A closed port is not proof.** The tool distinguishes accepted from
  not-accepted, and a filtered port simply times out.
- **A generator tag is a fact, not a vulnerability** — it tells an attacker what
  to research.
- **No findings means these specific checks found nothing.** Seven paths, four
  directories and eight ports is a small surface.

## Limits

- **Seven paths, four directories, eight ports.** Deliberately narrow.
- **Passive only** — no exploitation, no fuzzing, no authentication testing.
- **Root domain only.** No subdomain enumeration, and subdomains are where
  forgotten infrastructure usually lives.
- **CMS detection reads a declared tag** and nothing else, so a site that removes
  it is invisible to this check.
- **No version-to-CVE mapping.**
- **Ports are checked on one resolved IP.** Behind a CDN you are scanning the
  edge, not the origin — and finding nothing is then expected regardless.
- **Public hosts only**, by design.
- **A point-in-time check.** The value of this class of tool is running it
  continuously; this runs once.

## Likely interview questions

**"Why check the response content instead of the status code?"**
Because a very large share of sites return 200 for every path — a custom error
page, or a single-page app's index.html for anything unmatched. A status-code
check against one of those reports every sensitive path as exposed and the tool
is worthless. So each path has a content pattern only the real file matches:
Git's HEAD begins `ref: refs/`, a DS_Store starts with the magic bytes `Bud1`, a
zip with `PK`. Verify the thing you are claiming to have found, not a proxy for
it.

**"Why is an exposed `.git` directory so bad?"**
Because it is not one file, it is the entire repository. With `.git` served as
static content an attacker can reconstruct the full source and its complete
history — which means every secret that was ever committed, including the ones
someone noticed and removed in a later commit. The removal does not delete it
from history. It is one of the highest-value findings in web recon and it is
purely a deployment mistake.

**"You're port scanning from your server. What's the risk?"**
SSRF, and here it is acute because the tool literally is a port scanner. Without
a guard, anyone could point it at `localhost` or a private range and scan the
internal network the server sits in, or reach a cloud metadata endpoint. The
mitigation is shared with the TLS scanner: resolve the hostname first and refuse
if any resolved address is private, loopback, link-local or reserved — checking
the resolution rather than the string, because whoever owns a domain controls
where it points.

**"Your port scan took 18 seconds. What was wrong?"**
Sequential checks against a host with a firewall that *drops* rather than
*refuses*. A closed port refuses immediately, but a filtered one says nothing, so
you wait the full 2-second timeout — eight times over. Running the connects
concurrently in a thread pool makes it one timeout total. It is also the
practical difference between "closed" and "filtered" in a scan result: it is
entirely a matter of how long you waited.

**"Why won't you fingerprint the CMS properly?"**
Because proper fingerprinting is inference — asset paths, header quirks, cookie
names, timing — and it is wrong often enough to matter. Reporting "WordPress 5.8
with known CVEs" from a guess sends someone chasing a vulnerability in software
they do not run, which wastes their time and damages trust in the tool. Reading
the `generator` tag the site chose to publish is a fact. I would rather report
less and have it be true.
