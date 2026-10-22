Chapter 61Secret & PII Leak Scanner


> Paste code, config, logs or any text and it flags leaked secrets and personal data — AWS access keys, GitHub and Google and Stripe and Slack tokens, private-key blocks, JWTs, passwords in URLs, hardcoded secret assignments, plus high-entropy strings that look like custom keys. It also finds PII: emails, phone numbers, IPs, US SSNs and credit-card numbers (Luhn-checked so random digits don't false-positive). A curated pattern + entropy demo detector, not exhaustive DLP — every finding shows its line and a masked preview. Everything runs in your browser; the text never leaves the page and is never logged.

## At a glance

| | |
|---|---|
| **Also called** | Client-Side · No Upload |
| **Model or method** | Regex + Shannon entropy + Luhn (client-side) |
| **What you give it** | Pasted code / config / logs / text |
| **Detectors** | 20+ |
| **Where it runs** | In your browser — the file never leaves your machine |
| **Find it at** | `/tools/secret-scanner` |

### What this tool does
Paste any text — a \`.env\` file, a code snippet, a log line, a config dump —
and it flags leaked secrets and personal data. Everything runs in your
browser; the text never leaves the page and is never logged.

### What it looks for
- **Known secret formats** — AWS access keys, GitHub tokens, Google API keys,
  Stripe keys, Slack tokens and webhooks, SendGrid/Twilio/npm keys, private-key
  blocks, JWTs, passwords embedded in URLs, and hardcoded \`secret = "…"\`
  assignments.
- **High-entropy strings** — long, random-looking tokens that match no known
  format but look like a key. Ordinary prose scores far lower, so this catches
  custom secrets without drowning you in noise.
- **PII** — email addresses, phone numbers, IP addresses, US Social Security
  Numbers, and credit-card numbers. Card numbers are **Luhn-checked**, so a
  random 16-digit string won't be reported as a card.

### How to read it
The summary counts secrets, possible secrets and PII. Each finding shows its
**severity**, the **line** it's on, and a **masked preview** of the match so
you can locate it without the full value being splashed on screen.

### Honest limits
This is a curated, pattern-based demo — the same idea as the gitleaks scan that
runs on this project's own commits, made interactive. It is thorough on the
patterns it knows, but it is **not** exhaustive data-loss prevention: it can
miss a cleverly disguised secret, and it can occasionally flag a false positive
(which is why every finding shows its line for you to judge). A clean result
does not prove the text is safe.

### Why it matters
Secrets leak constantly through committed \`.env\` files, screenshots, logs and
pasted snippets. Catching them before they're shared is the cheapest possible
fix — once a key is public, the only safe move is to rotate it.
