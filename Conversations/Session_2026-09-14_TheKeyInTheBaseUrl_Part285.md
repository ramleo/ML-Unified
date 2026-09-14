# Part 285 — The key in the base URL

Continues [Part 284](Session_2026-09-13_TheDayTheReposWentPublic_Part284.md).

2026-09-14, the day after both repositories went public. Closed B2 and E1, and
found E9 — a server-key leak that had been reachable by anyone since the code
became readable.

`OPEN_ISSUES.md` rows B2, E1 and E9 carry the detail. What follows is what does
not fit in a row: how each cause was pinned down, and why the most important
fix of the day came from reading around a task rather than doing it.

---

## 1. B2: the build succeeded, then Vercel's step crashed

ml-portfolio PR #5 (next 16.2.7 → 16.3.4) passed every GitHub check and failed
only the Vercel deployment. Vercel does not publish the reason; its status
points at `vercel inspect --logs`, which needs an account login. The user
pasted the build log instead.

The log's shape mattered more than its error. The Next build **finished**;
the failure came after, in `Running onBuildComplete from Vercel`, with
`ENOENT .next/next-server.js.nft.json`.

Building the PR branch locally created that file, so the version alone did not
explain it. Reading Next's build source showed that `onBuildComplete` runs only
when an **adapter** is configured (`NEXT_ADAPTER_PATH`), and that the
`output: "standalone"` step right after it reads the trace file. Vercel always
injects an adapter; local builds never have one.

The proof was a no-op adapter:

```js
export default { name: "noop", async onBuildComplete() {} };
```

`NEXT_ADAPTER_PATH=./noop-adapter.mjs npm run build` reproduced the exact
Vercel error on the laptop. So the fault is Next 16.3.x combining standalone
output with any adapter — not the site's code and not a Vercel setting.

Standalone cannot simply go: the Dockerfile needs it. Vercel never uses it. Fix
`b3c3029`:

```ts
output: process.env.VERCEL ? undefined : "standalone",
```

Checked both ways before pushing — adapter build passes, plain build still
emits `.next/standalone/server.js`. Merged as `73f0fe9`, production deploy
green.

**Lesson:** when a platform build fails and the local one passes, find the one
thing the platform adds and add *only that* locally. A stub is enough.

---

## 2. E9: reading the routes for E1 found a key leak

E1 was "rate-limit the Vercel API routes". Before writing a rule, the routes
were read to see what each one calls. `/api/ai-tools` did this:

1. Take `provider`, `userKey` and `baseUrl` from the request body.
2. `resolveKey(provider, userKey)` — with no `userKey`, fall back to the
   server's env key for that provider.
3. If `baseUrl` is set, `fetch(baseUrl + "/chat/completions")` with
   `Authorization: Bearer <that key>`.

One request with `provider: "groq"` and `baseUrl` pointing at an attacker's
host handed over `GROQ_API_KEY` — or Gemini's, which is billed. The repository
had been public since the day before.

It was proven without sending a real key anywhere: a local dev server with a
**planted** key (`GROQ_API_KEY=SENTINEL_NEW`) and a local listener standing in
for the attacker. A copy of the old route delivered `Bearer SENTINEL_NEW` to
the listener; the fixed route returned 401 and the listener saw nothing more.
The first attempt ran the old code from a second worktree and failed to start —
Turbopack rejects a symlinked `node_modules` — so the old route was copied in
beside the new one on one server instead.

Fix `dc2bf19`: a caller-chosen URL only ever receives the caller's own key, and
must be `https`. The frontend's one `baseUrl` sender already sent a user key
with it, so nothing legitimate broke. The backend's equivalent
(`automl_explain`, provider `custom`) was checked and is safe: `custom` is not
in the server-key map, so it never gets one.

The user rotated the Gemini key. The free-tier keys were deliberately left
unrotated. E9 stays pending by the user's choice, and the one condition that
changes that is recorded: **rotate a key before enabling billing on it**, not
after.

**Lesson:** scoping a task is reading, and reading finds things. The rate limit
would have slowed an attacker; it would not have stopped a single request that
takes a key.

---

## 3. E1: one Hobby rule, and what it could not cover

The narrower-than-expected scope came first: browser calls to the ML backend go
straight to the Hugging Face Space, so a Vercel firewall rule only guards
ml-portfolio's own `/api/*`. Four routes matter — `chat`, `ai-tools` and
`ai-explain` call LLMs, `contact` sends email — and none had a limit.

Vercel's docs, checked rather than assumed: Hobby gets **one** rate-limit rule
per project, IP-keyed, 10s–10min fixed window. The dashboard did not match the
steps written from those docs, and the user corrected them with screenshots.
Two details from that exchange:

- The path operator had to be **Is any of**, not **Contains**. `Contains
  /api/` would also have matched `/api/track` and the other logging routes the
  site calls constantly, throttling real visitors.
- 20 requests per 60s per IP, because every caller sends one request per click.

Verified live with requests that cost nothing — empty `messages`, which the
route refuses before any LLM call: `400 ×20`, then `429 ×5`. `/api/news`
stayed 200.

One rule meant `contact` shared a limit that is loose for something that sends
email. Three options were weighed: Turnstile, a per-IP counter in code
(unreliable across serverless instances without a database), or leaving it
since Resend caps daily sends. Turnstile won because it stops scripts rather
than slowing them, and the project already had it for `security-log`.

`2790333` moved that route's verifier into `src/lib/turnstileVerify.ts`, called
it first in `contact`, sent a token from the form, and HTML-escaped the email
body, which had been interpolating visitor input raw. Tested locally against
Cloudflare's always-fail and always-pass test secrets, so the real verify call
was exercised; live, an empty request returns 403, which also proved the secret
is set in Vercel. The one thing no automated check covered — a person actually
sending the form — the user did, and the email arrived with its line breaks
intact.

The user then asked for a way back to the form after sending. `a9c3a6f` adds
**Send another message**, which clears the fields; checked in headed Chrome
with `/api/contact` intercepted so no email went out.

---

## Commits

| Repo | Commit | What |
|---|---|---|
| ml-portfolio | `b3c3029` | standalone output skipped on Vercel |
| ml-portfolio | `73f0fe9` | PR #5 merged, next 16.3.4 |
| ml-portfolio | `dc2bf19` | no server key to a caller-supplied URL |
| ml-portfolio | `2790333` | Turnstile on contact, escaped email HTML |
| ml-portfolio | `a9c3a6f` | Send another message |
| ML-Unified | `029eddb` `7e3888d` `577649d` | B2, E9, E1 in `OPEN_ISSUES.md` |

Still open: E9 (non-billed keys, by choice), E2–E6.
