Chapter 50JWT / Token Security Analyzer


> Paste a JSON Web Token and it decodes the header and payload and audits them for the mistakes that cause real token breaches: alg:none, missing or over-long expiry, missing issuer/audience, and sensitive data sitting in the (unencrypted) payload. For HMAC tokens it runs a genuine weak-secret test in your browser with the Web Crypto API, trying a built-in list of default and common secrets plus any wordlist you paste — it catches guessable secrets but, honestly, cannot crack a strong random one. Everything runs locally; the token never leaves the page.

## At a glance

| | |
|---|---|
| **Also called** | Client-Side · Real Web Crypto |
| **Model or method** | Web Crypto HMAC (client-side) |
| **What you give it** | A JWT + optional wordlist |
| **Data Uploaded** | 0 |
| **Where it runs** | In your browser — the file never leaves your machine |
| **Find it at** | `/tools/jwt-analyzer` |

### What this tool does
Paste a JSON Web Token (JWT) and it decodes it and audits it for the
security mistakes that actually cause token breaches. Everything runs in
your browser — the token never leaves the page.

### Everything here is real
- **Decode** — the header and payload are genuinely base64url-decoded and
  shown. Note the payload is only *encoded*, never *encrypted*: anyone
  holding the token can read every claim in it.
- **Checks** — real structural checks: \`alg: none\`, missing or over-long
  expiry, missing issuer/audience, sensitive data sitting in the payload,
  and more.
- **Weak-secret test** — for HMAC tokens (HS256/384/512) the tool actually
  tries to reproduce the signature using the browser's Web Crypto. If a
  candidate secret matches, the token is genuinely signed with that secret.

### The weak-secret test, honestly
No tool can crack a strong, random secret — that is cryptography working as
intended. What this catches is the real-world failure: a developer shipping
a framework's default secret (like jwt.io's \`your-256-bit-secret\`) or a
human-chosen password. It tries:
1. A **built-in list** of well-known default and common secrets.
2. **Your own wordlist**, if you paste one — as large as you like (e.g.
   rockyou.txt). It runs in your browser, so it costs nothing and stays
   private.

A "secret not in the wordlist" result is a good sign but does **not** prove
the secret is strong — it only means it wasn't in what you tested.

### Try it
Use **Try a weak token** to see a token signed with the secret \`secret\`
get cracked, with several findings. Use **Try a strong token** to see a
well-formed token whose random secret is not crackable.

### Why it matters
If an attacker learns your HMAC secret, they can forge any token they want —
including \`role: admin\`. Always use a long, random secret (32+ random
bytes), set a short expiry, pin the algorithm server-side, and reject
\`alg: none\`.
