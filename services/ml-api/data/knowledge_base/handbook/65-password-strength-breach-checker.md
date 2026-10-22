Chapter 57Password Strength & Breach Checker


> Check how strong a password really is. Scored in your browser by zxcvbn, the pattern-matching algorithm behind many real password meters — dictionaries, keyboard walks, dates, repeats — rather than naive character-class counting. You can also check it against Have I Been Pwned using k-anonymity: only the first five characters of its SHA-1 hash ever leave your machine, never the password itself. Nothing is stored.

## At a glance

| | |
|---|---|
| **Also called** | Local · No API Cost |
| **Model or method** | zxcvbn-ts + HIBP k-anonymity range API |
| **What you give it** | Password (never stored) |
| **API Calls** | 0 |
| **Where it runs** | In your browser — the file never leaves your machine |
| **Find it at** | `/tools/password-audit` |

## Using the tool

### What this tool does
Type a password and it's scored two independent ways, both without ever
sending the actual password anywhere: a real-time strength meter (runs
entirely in your browser) and an on-demand breach-exposure lookup against a
public database of previously leaked passwords (only a tiny hash fragment
ever leaves your device — see below for exactly what that means).

### Strength meter
Scoring uses **zxcvbn**, the same pattern-matching algorithm behind many
real password meters (originally built at Dropbox). Unlike a naive
character-class count (uppercase + lowercase + digit + symbol = "strong"),
zxcvbn actually checks the password against common dictionaries, keyboard
walks (\`qwerty\`, \`asdf123\`), dates, repeats, and common substitutions
(\`p@ssw0rd\`) — the kind of real password an attacker's cracking tool would
try first. This is why something like \`Password1!\` scores low here despite
looking "complex" on paper: it hits every character-class box but is still
a very common, predictable pattern. This scoring runs 100% in your browser;
nothing about your password is sent anywhere for this part.

### Breach exposure check
Click **Check breach exposure** to look up whether this exact password has
appeared in a known data breach, via Have I Been Pwned's Pwned Passwords
database — using a technique called **k-anonymity**:
1. Your password is hashed locally in your browser (SHA-1 — this is Have I
   Been Pwned's own API requirement, not a general security recommendation).
2. Only the **first 5 characters** of that hash are sent to Have I Been
   Pwned's API — never the password, and never the full hash.
3. The API returns every breached password hash that starts with those same
   5 characters (often hundreds of them). The match against your password's
   actual full hash happens locally, in your browser.

This is a real, published privacy-preserving technique (not something built
for this project) — it's the same design Have I Been Pwned's own password
manager integrations use.

### Reading the result
- **Not found** — this exact password isn't in Have I Been Pwned's breach
  corpus. Reassuring, but not proof the password is strong — a password can
  be unbreached and still weak (a strength score of 0-1 above still means
  it's easy to guess or crack, breached or not).
- **Found in N breaches** — this exact password is known to attackers from
  real leaked-credential dumps. Change it immediately anywhere it's used,
  regardless of what the strength meter says.

### What this is (and isn't)
Two independent signals, not one combined verdict: the strength meter
estimates how hard this password would be to *crack* (guess offline); the
breach check tells you whether it's already *known* from a real leak. A
password can score well on one and poorly on the other — a strong, unique
password can still show up in a breach if it was reused somewhere that got
compromised, and a weak password won't show up in this breach corpus if
literally no one else has ever used it before.

### Privacy
Nothing here is stored — no scan history, no localStorage entry, unlike
some of this site's other local-history tools. The password field is
cleared with the **Clear** button and never persisted between visits. The
only network request this tool ever makes is the 5-character hash-prefix
lookup to \`api.pwnedpasswords.com\`, and only when you click the breach
check button — never automatically, and never on every keystroke.

## What problem it solves

Password strength meters are mostly wrong. The familiar rule — eight characters,
one uppercase, one number, one symbol — produces `P@ssw0rd1`, which satisfies
every requirement and is one of the first passwords any attacker tries. Meanwhile
`correct horse battery staple` fails the rules and is enormously stronger.

The rules are wrong because they measure **composition**, and what matters is
**guessability**. An attacker does not enumerate the character space; they work
through leaked password lists, then dictionary words with predictable
substitutions, then keyboard patterns, then dates. A password's real strength is
how deep into that ordered search it sits.

There is also a second question the rules cannot touch: **has this exact password
already appeared in a breach?** A password can be structurally excellent and
still be in a leaked dump, at which point its strength is irrelevant — it is on a
list.

This tool answers both, and it does the second one **without ever sending your
password anywhere**.

## How it works, step by step

1. **Type a password.** It stays in the browser.
2. **Score it with zxcvbn**, which estimates how many guesses it would take.
3. **Optionally check it against breach data** using a **k-anonymity** lookup —
   only the first five characters of a hash ever leave the machine.
4. **Report** a score, an estimated crack time, specific warnings, and whether
   the password appears in known breaches and how often.

## The model or algorithm

### zxcvbn — scoring by guessability

Dropbox's estimator, and the idea is a genuine improvement on entropy rules. It
tries to model **how an attacker would actually guess**, by decomposing the
password into recognisable patterns and costing each one:

- **Dictionary words** — English, common names, and importantly a list of the
  most common passwords. A word's cost is its **rank**: `password` is guess
  number one, an obscure word is far deeper in.
- **`l33t` substitutions** — `@` for `a`, `0` for `o`. These are *unmasked* before
  the dictionary lookup and add only a small multiplier, because everyone does
  them and every cracking tool tries them.
- **Keyboard patterns** — `qwerty`, `asdfgh`, and any adjacency walk, using a
  real keyboard adjacency graph.
- **Sequences and repeats** — `abcdef`, `123456`, `aaaa`.
- **Dates** — recognised in many formats, and a small space because there are not
  many plausible years.

The estimator finds the **cheapest decomposition** of the whole password — the
route an attacker would take — and multiplies the parts. So `P@ssw0rd1` decomposes
into a top-ranked dictionary word, standard substitutions and a trailing digit,
and costs almost nothing. Four uncommon words concatenated have no cheap
decomposition at all.

The output is a **score from 0 to 4** and a **crack-time estimate**, and it comes
with **specific feedback** — "this is a top-10 common password", "predictable
substitutions do not help much" — which a percentage bar cannot give.

### The k-anonymity breach lookup — the interesting part

Checking whether a password appears in a breach seems to require sending the
password to whoever holds the breach data. That is obviously unacceptable.

Have I Been Pwned's Pwned Passwords API solves it with **k-anonymity**:

1. Hash the password with SHA-1 locally → 40 hex characters.
2. Send **only the first 5 characters** to
   `api.pwnedpasswords.com/range/{prefix}`.
3. The server returns **every** hash suffix it holds beginning with that prefix —
   typically several hundred to a few thousand.
4. Search that list locally for your suffix.

The server learns that someone was interested in one of roughly 800 hashes and
cannot tell which — or whether yours was in the list at all, because the same
response is returned either way. **The password never leaves the machine, and
neither does its full hash.**

That is the property worth being able to explain: the privacy comes from the
*response being independent of the answer*, not from encryption or trust.

**Why SHA-1, when SHA-1 is broken.** Because it is the API's contract, not a
security choice, and the code says so explicitly. It is used as a lookup key over
a public dataset, not to protect anything — a collision would let an attacker
learn that one of two passwords they already know is in a public breach list,
which is worth nothing. Being able to say *why* a deprecated primitive is
acceptable in a specific context is more useful than reflexively objecting to it.

**A count comes back too.** Not just "breached" but "seen 3,861 times", which is
a much better signal — a password in a dump 20,000 times is in every cracking
list in existence.

### What the two checks each miss

They are complementary, and neither is sufficient:

- zxcvbn can score a password highly that has **already leaked**, because
  strength says nothing about exposure.
- The breach check passes any password not yet in a dump, including
  `Summer2025!` if that exact string has not been dumped — which is not the same
  as being unguessable.

## Why these choices

**Why zxcvbn rather than a composition rule.** Composition rules measure the
wrong thing and actively push people toward predictable passwords, because
`P@ssw0rd1` is the shortest path to satisfying them. Guessability is the property
that matters and zxcvbn estimates it directly.

**Why the browser.** A password typed into a web form that then posts it
somewhere is exactly the pattern people should be taught not to trust. Everything
runs client-side, and the only network request carries five characters of a hash.

**Why show the crack-time estimate.** Not because the number is precise — see
*Limits* — but because "centuries" and "three seconds" communicate to a
non-specialist in a way a 0-to-4 score does not.

**Why report the count, not just a boolean.** Frequency is the actionable part.

## How to read the output

- **Score 3 or 4 is the target.** Below 3 means zxcvbn found a cheap
  decomposition.
- **Read the warning and suggestions.** They name the *specific* weakness — a
  dictionary word, a keyboard walk, a date — and that is more useful than the
  score.
- **Any breach count is disqualifying**, whatever the strength score. It is on a
  list.
- **Crack time is an order of magnitude, not a measurement.** It depends
  entirely on assumptions about attacker hardware and whether the target used
  slow hashing.
- **"Not found in breaches" is not a pass.** It means this exact string has not
  appeared in the datasets HIBP holds.
- **A long passphrase of uncommon words usually beats a short complex string**,
  and the tool will show you that directly.

## Limits

- **zxcvbn's dictionaries are English-centric.** A password built from words in
  another language is scored as more random than it is.
- **Crack-time estimates are assumption-dependent** — attacker hardware, the
  hashing algorithm the target site used, whether it was salted.
- **The breach check only covers HIBP's corpus.** Absence means "not in these
  datasets".
- **SHA-1 is used as an API contract.** Correct here, and not a general
  endorsement.
- **The prefix lookup leaks the prefix**, which is the whole design — k-anonymity
  reduces the leak to one bucket, it does not eliminate it.
- **No password-manager integration, no reuse detection across your accounts, no
  storage.** One password at a time.
- **Nothing here checks whether the *site* stores passwords properly**, which is
  frequently the thing that actually fails.
- **It requires you to type a real password into a browser**, which is a habit
  worth being uneasy about even when the implementation is sound.

## Likely interview questions

**"Why are the usual password composition rules wrong?"**
Because they measure the wrong property. Requiring an uppercase, a number and a
symbol produces `P@ssw0rd1` — which satisfies every rule and is among the first
things any cracking tool tries — while rejecting a four-word passphrase that is
orders of magnitude stronger. Attackers do not enumerate the character space;
they work through leaked lists, dictionaries with substitutions, keyboard
patterns and dates. What matters is where a password sits in that ordered search,
and composition rules do not measure that at all.

**"How does zxcvbn work?"**
It decomposes the password into recognisable patterns — dictionary words scored by
rank, `l33t` substitutions unmasked and barely credited, keyboard adjacency
walks, sequences, repeats, dates — and costs each one by how many guesses it would
take. Then it finds the *cheapest* decomposition, which is the route an attacker
would take, and multiplies. That is why `P@ssw0rd1` scores near zero: it has a
very cheap decomposition even though it satisfies every composition rule.

**"How do you check a password against a breach database without sending it?"**
k-anonymity. Hash the password locally with SHA-1, send only the first five hex
characters, and the server returns every suffix it holds under that prefix —
several hundred to a few thousand. You search that list locally. The server
learns you were interested in one of roughly 800 hashes and cannot tell which,
and crucially cannot tell whether yours was present, because the response is
identical either way. The privacy comes from the response being independent of
the answer.

**"SHA-1 is broken. Why use it?"**
Because it is the API's contract, and here it is a lookup key over a public
dataset rather than a security primitive. Nothing is being protected by its
collision resistance — a collision would let an attacker learn that one of two
passwords they already know appears in a public breach list, which is worth
nothing. The question to ask about a deprecated primitive is what property you
are relying on, not whether the name appears on a list.

**"A password scores 4 out of 4 and appears in a breach. What do you tell the
user?"**
Change it, immediately, and the strength score is irrelevant. Strength estimates
how hard it is to *guess*; a breach means it does not need to be guessed, because
it is already on a list that every cracking tool loads first. The two checks
measure different things and the breach result always wins — which is exactly why
the tool does both rather than only scoring.
