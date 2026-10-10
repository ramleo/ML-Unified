"""
Testwright — a cheap, deterministic syntax guard for generated/healed test code.

A model occasionally emits code that cannot parse — a `{ name. 'x' }` typo, an
unbalanced brace. Shipped to the CI runner, it fails the WHOLE spec with the
opaque "No tests found", which reads like the feature is broken. We cannot run a
real TypeScript parser in this Space, but a small structural check catches the
failure modes that actually occur, so Heal/Author can fall through to another
provider instead of handing the user a spec that compiles to zero tests.

This is a REJECTION filter, not a fixer (the fixer is
locators.sanitize_option_punctuation, which runs first). Kept conservative: it
only rejects code it is confident is broken, so a valid heal is never discarded.
"""

import re

# A leftover `{ <option-key>. <literal>` the sanitizer did not catch (e.g. a key it
# does not know). An option key followed by `.` and a literal value is never valid.
_OPT_KEY_DOT_LEFT = re.compile(
    r"\{[^{}]*\b\w+\s*\.\s*(?=['\"`]|\d|true\b|false\b)[^{}]*\}"
)


def _unbalanced(code: str) -> bool:
    """True if (){}[] are not balanced, scanning OUTSIDE string and comment bodies.
    Generated tests use only simple `/^text/i` regexes (no brackets inside), so not
    tracking regex literals is safe in practice; strings and // and /* */ comments
    are skipped so their braces/parens never count."""
    pairs = {")": "(", "]": "[", "}": "{"}
    opens = {"(", "[", "{"}
    stack: list[str] = []
    quote: str | None = None
    i, n = 0, len(code)
    while i < n:
        c = code[i]
        if quote:
            if c == "\\":
                i += 2
                continue
            if c == quote:
                quote = None
            i += 1
            continue
        if c in ("'", '"', "`"):
            quote = c
        elif c == "/" and i + 1 < n and code[i + 1] == "/":
            j = code.find("\n", i)
            i = n if j < 0 else j
            continue
        elif c == "/" and i + 1 < n and code[i + 1] == "*":
            j = code.find("*/", i + 2)
            i = n if j < 0 else j + 2
            continue
        elif c in opens:
            stack.append(c)
        elif c in pairs:
            if not stack or stack[-1] != pairs[c]:
                return True
            stack.pop()
        i += 1
    return bool(stack or quote)


def _blank_strings(code: str) -> str:
    """Replace the CONTENTS of string/template literals with spaces (keeping the quote
    delimiters and all structure), so a check for code punctuation isn't fooled by
    punctuation INSIDE a string value — e.g. a heading name that ends in a period right
    before its closing quote (`'… get a prediction.'`) is not a `name.` option-key typo.
    Without this, any grounded locator whose text ends in '.' was wrongly rejected."""
    out = list(code)
    quote: str | None = None
    i, n = 0, len(code)
    while i < n:
        c = code[i]
        if quote:
            if c == "\\":
                i += 2
                continue
            if c == quote:
                quote = None
            else:
                out[i] = " "
        elif c in ("'", '"', "`"):
            quote = c
        i += 1
    return "".join(out)


def looks_syntactically_valid(code: str) -> bool:
    """A best-effort gate: the code defines a test and has no structural break we can
    detect cheaply. False => reject this candidate and let the cascade try another."""
    if not code or "test(" not in code:
        return False
    # Check option-key-dot typos against string-blanked code so a legitimate string
    # value ending in '.' (a sentence-shaped locator name) is not a false positive.
    if _OPT_KEY_DOT_LEFT.search(_blank_strings(code)):
        return False
    if _unbalanced(code):
        return False
    return True
