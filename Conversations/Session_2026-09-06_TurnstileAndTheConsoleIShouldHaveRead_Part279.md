# Session 2026-09-06 — Part 279

## Turnstile, and the console I should have read

Continues Part 278, which hit its 400-line limit at §12. Same day, same
thread: the security log went from "built" to "actually defended", and the
defending took three wrong guesses before I looked at the evidence that had
been there from the first run.

**7 commits.** 5 in `ml-portfolio`, 2 in `ML-Unified`.

---

## 1. The question that started it

Part 278 §11.2 described "two locks" keeping the security log unreadable. The
user read that and asked the obvious next thing:

> *"you said 'that file contains only code for writing', isn't it risky, what
> if someone unauthorized writes something harmful?"*

Two locks on reading. Nothing said about writing. §12 covered the first half
of the answer — the header comment claimed an origin check that did not exist.
This is the rest.

---

## 2. The rate limit that was decorative

The Origin check was never the weak point. **The rate limit was.** It lived in
a module-level `Map`, and serverless instances share no memory — so spreading
requests across instances walked straight through it. The "60/min" claim was
close to meaningless under precisely the condition it existed for.

Moved into the database: `log_security_event()` counts the caller's last
minute where every instance sees the same number, and returns false instead of
writing. The route calls it rather than inserting.

Counting a caller needs to identify one, hence a new `ip_hash` column — a
salted HMAC, never the address. Server-only salt, so a row cannot be reversed.
Recorded in §5b's column list and on the privacy page, because it is a new
fact about a person.

`abfc7a1`, `52cf37f`.

---

## 3. Why not proof-of-work

The user then asked for the residual risk — a forged Origin — actually fixed
rather than documented.

**Proof-of-work was considered and deliberately not built.** A browser can
afford roughly 200ms of hashing; a native attacker does the same work in
microseconds. It would have read as solved without being solved, which is
worse than the open hole, because nobody looks again at something that appears
handled.

The honest fix is browser attestation, and the free one is Cloudflare
Turnstile: verification happens on Cloudflare's side against signals the
client does not control, and the token is single-use and short-lived.

Built to **fail open** with no secret configured, so switching it on is
opt-in and nothing broke on deploy.

`d3a7a3f`.

---

## 4. Setup, and two things the dashboard said

- The button is **"Add widget manually"**, not "Add site".
- **Invisible mode requires the Turnstile Privacy Addendum to be linked from
  our own privacy policy.** Cloudflare states this as a condition. Added —
  and the first URL I used was a guess that 404'd. Verified the real one
  returns 200 before committing, because a dead link on a page whose premise
  is *"every claim here was checked against the source"* is worse than no
  link. `57746ba`.
- Vercel warns that `NEXT_PUBLIC_` exposes a value to the browser. For the
  Turnstile **site key that is correct and intended** — it appears in the page
  HTML by design. The **secret** key gets no prefix and stays private.

---

## 5. Four attempts, and the evidence I ignored

### 5.1 First live test: still open, and I polluted the table

`curl` returned `200 {"ok":true}`. Two things learned at once: Vercel only
picks up new environment variables on a **fresh deploy**, and the table
already existed because the user had run the SQL.

**That test wrote two junk rows into the security log.** My fault. Exactly the
pollution I had described as the risk two messages earlier, caused by me. The
user deleted them.

### 5.2 After redeploy: curl blocked

`403 Failed verification`. Half the job done.

### 5.3 But real browsers were blocked too

A real browser upload also returned **403, with no token**. Uploads kept
working and silently stopped being logged — the exact failure this log exists
to not have, introduced by me.

Two guesses, both plausible, both wrong:

1. `size: "invisible"` — not a client option; invisible is a dashboard widget
   mode. Passing it gets the widget rejected.
2. A `display:none` container — Turnstile refuses to execute inside a hidden
   element.

Both changes were correct in themselves and stayed. Neither was the cause.

### 5.4 The actual cause, which the console had said all along

```
Framing 'https://challenges.cloudflare.com/' violates the following
Content Security Policy directive: "default-src 'self'"
```

**Our own CSP.** `next.config.ts` had no `frame-src`, so framing fell back to
`default-src 'self'` and the Turnstile iframe was blocked outright. Everything
else looked healthy: the script loaded, `window.turnstile` existed, `render()`
did not throw — and no token was ever produced.

Fixed with `frame-src 'self' https://challenges.cloudflare.com`, scoped to
that one origin rather than relaxing framing to `https:`. `704710c`.

**The lesson is not the CSP.** The browser console printed that message on the
very first debug run, before either wrong guess. Two commits were spent not
reading it. Part 278 §5 is about lists being wrong; this is the same habit
pointed at evidence — acting before looking.

---

## 6. A test that could never have passed

After the CSP fix, the browser still returned no token — but with a new error:
**Turnstile `600010`**.

Researched rather than assumed: the 600xxx family means the challenge could
not complete in the visitor's environment, and reported triggers include
restricted or automated browsers, and even devtools being open.

**Playwright is an automated browser. Turnstile's entire purpose is to reject
those.** The tool was working; the test method could not possibly succeed.

So the happy path is not machine-verifiable here, and saying so mattered more
than producing a green tick. The user ran it manually in real Chrome, and the
row appeared:

```
2026-09-06 16:14:48   yara-file-scanner   meridian-invoice-2291.pdf   pdf   4264
```

**Both directions confirmed:** real browser logs successfully, curl gets 403.

Worth keeping: an entire class of protection cannot be verified by the
automation normally used to verify things, because it is specifically designed
to defeat it. Recognising that is different from a test failing.

---

## 7. Failing closed, and what it costs

Once configured the endpoint fails closed: no token, no row. A visitor who
blocks Cloudflare — an ad-blocker will — can still use every tool, but their
uploads go unlogged.

For a security log that is the right way round; the alternative is accepting
unverified rows. But it means **the log is a record of what most visitors
uploaded, not provably all of them**, and that belongs written down rather
than discovered later by someone trusting it too much. §6 rule 2 still holds:
the upload never fails, only its log entry.

---

## 8. Reading the tables in IST

`+00` is UTC. The SQL editor was showing every timestamp 5.5 hours off from
readable.

**Storage stays UTC** — unambiguous, unaffected by daylight saving, still
correct if read from another country. Three views convert on display:
`security_log_ist`, `llm_calls_ist`, `events_ist`. `86907ac`.

### 8.1 The line worth reviewing

Every view carries `security_invoker = true`, and it is load-bearing. **A view
runs with its OWNER's permissions by default** — so a plain view over
`security_log` would let the browser's anon key read the table straight
through it, undoing the RLS that is the entire reason it is locked.

A view is a completely ordinary way to undo that protection without noticing.

### 8.2 The global change, rejected

`alter database ... set timezone` was the alternative. Rejected: two pg_cron
jobs run at 03:17 and 03:41, and I could not say without testing whether that
setting would shift them. **Guessing about a scheduled DELETE is the wrong
place to guess.**

### 8.3 Verified, not assumed

| Check | Result |
|---|---|
| `purge-old-analytics` | `17 3 * * *` · active |
| `purge-security-log` | `41 3 * * *` · active |
| `events_ist` | `security_invoker=true` |
| `llm_calls_ist` | `security_invoker=true` |
| `security_log_ist` | `security_invoker=true` |
| timezone | `UTC` |

`security_invoker` exists only in Postgres 15+, so the views creating without
error also proved the option was supported rather than silently ignored.

---

## 9. Where the endpoint stands

| Attack | Result |
|---|---|
| Read the table | blocked — RLS, no policies, and no GET handler |
| curl / scripts writing | blocked — Turnstile |
| Flooding it | blocked — 60/min counted in the database |
| Oversized payload | blocked — 4KB cap |
| Cross-site POST from a browser | blocked — Origin allow-list |
| Password tool | excluded — client and server |

Real visitors are unaffected: Turnstile runs invisibly, nothing to click.

---

## 10. Still open

Unchanged from Part 278 §10 — all decisions rather than construction:

- Search queries as a salted hash rather than a length.
- Whether to store uploaded content at all (§10 of the spec).
- Two naming conventions in `events`: `tool_open` carries display names, run
  events carry slugs. Renaming orphans existing rows.
- `demo_abandon` — reasoned about, never exercised.
- Site chatbot still defaults to Gemini; Cohere is not wired into
  `/api/chat`.
- Returning visitors keep their old provider via localStorage.
- `verify-recon-warning.mjs` — still untracked in `ml-portfolio`.

New from this part:

- **Ad-blocker users' uploads go unlogged** (§7). Accepted deliberately, not
  an oversight.
