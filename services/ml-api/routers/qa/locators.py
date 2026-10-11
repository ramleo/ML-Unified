"""
Testwright — deterministic locator/code post-processing.

These transforms run on every generated AND healed test. They are deliberately
deterministic (not prompt-nudging) because a regex fix is far more reliable than
asking the model to remember a rule: the model repeatedly emits the same brittle
patterns (hard sleeps, sentence-long names, ambiguous locators, wildcard names).

Ground truth for the *grounded* transforms is the live page context Discover
captured (an ARIA snapshot + a link accessible-name -> href map); the purely
syntactic transforms (hard waits, href `.first()`, junk names) need no context.
"""

import re
from collections import Counter

# A whole-statement hard sleep, e.g. `await page.waitForTimeout(500);`. Matched only
# as a standalone line, so an inline/embedded use is left alone (conservative).
_HARD_WAIT_LINE = re.compile(
    r"^[ \t]*(?:await\s+)?page\.waitForTimeout\s*\([^)]*\)\s*;?[ \t]*(?://.*)?$"
)

# Accessible names in the page context: ARIA-snapshot role lines (e.g. `link "X"`)
# carry one entry PER element (so nav+footer duplicates are counted), plus the
# link map's left-hand side (`X -> /href`).
_CTX_ROLE_NAME = re.compile(
    r'(?:link|button|heading|tab|menuitem|checkbox|option|textbox|searchbox|radio)'
    r'\s+"([^"\n]{1,120})"'
)
# A full getByRole call whose options object has ONLY a name (no `exact`/extra),
# so we can either add `exact: true` inside it or append `.first()` after it.
_GETBYROLE_NAME = re.compile(
    r"getByRole\(\s*(['\"])(\w+)\1\s*,\s*\{\s*name:\s*(['\"])(.*?)\3\s*\}\s*\)"
)

_LONG_NAME = 60
_RE_SPECIAL = re.compile(r"[.*+?^${}()|[\]\\/]")

# A model typo that writes `.` where an options-object key needs `:`, e.g.
# `getByRole('searchbox', { name. 'Search…' })`. A SINGLE such slip makes the whole
# spec fail to parse (the runner reports "No tests found"), and it slips past every
# other transform here because they all require a well-formed `name:`. Only known
# option keys followed by a LITERAL value are matched, so a legitimate method chain
# (`page.getByRole`, `expect.soft`) is never touched.
_OPT_KEY_DOT = re.compile(
    r"\b(name|exact|hasText|hasNotText|level|checked|pressed|selected|expanded"
    r"|disabled|includeHidden|timeout|setChecked)\s*\.\s*"
    r"(?=['\"`/]|\d|true\b|false\b)"
)


def sanitize_option_punctuation(code: str) -> str:
    """Repair `{ <key>. <value> }` -> `{ <key>: <value> }` for known locator option
    keys the model sometimes mis-punctuates with a period. Deterministic and safe:
    only a known key immediately followed by a literal value start is rewritten."""
    return _OPT_KEY_DOT.sub(lambda m: m.group(1) + ": ", code)


def strip_hard_waits(code: str) -> str:
    """Remove hard-coded `page.waitForTimeout(...)` sleeps — the #1 cause of flaky
    tests. Playwright's auto-waiting and web-first assertions make fixed sleeps
    unnecessary, and a deterministic strip is more reliable than asking the model
    not to emit them. Only whole standalone statements are removed."""
    lines = code.split("\n")
    kept = [ln for ln in lines if not _HARD_WAIT_LINE.match(ln)]
    return "\n".join(kept)


def shorten_long_names(code: str) -> str:
    """A `getByRole` whose `name` is a whole sentence (a card's full paragraph text)
    is brittle and usually resolves to nothing. Replace an over-long exact name with
    a short `^prefix` regex + `.first()`, which matches the same element far more
    robustly. Short, normal names are left untouched."""
    def repl(m: "re.Match") -> str:
        name = m.group(4)
        if len(name) <= _LONG_NAME:
            return m.group(0)
        prefix = ""
        for w in name.split():
            if prefix and len(prefix) + 1 + len(w) > 40:
                break
            prefix = w if not prefix else prefix + " " + w
            if len(prefix.split()) >= 5:
                break
        if not prefix:
            prefix = name[:40]
        esc = _RE_SPECIAL.sub(lambda x: "\\" + x.group(0), prefix)
        q, role = m.group(1), m.group(2)
        return f"getByRole({q}{role}{q}, {{ name: /^{esc}/i }}).first()"
    return _GETBYROLE_NAME.sub(repl, code)


def _parse_link_map(page_context: str) -> list[tuple[str, str]]:
    """The link map lines ('accessible-name -> href') captured by Discover. Returns
    (label_lower, href) pairs, skipping bare '#' anchors."""
    pairs: list[tuple[str, str]] = []
    for line in page_context.splitlines():
        if line.strip().startswith("==="):  # skip the LINKS delimiter header
            continue
        if " -> " in line:
            label, _, href = line.partition(" -> ")
            label, href = label.strip().lower(), href.strip()
            # Trailing `[newtab]`/`[download]` markers are context for the model, not
            # part of the href — strip any of them so the deterministic href match works.
            while href.endswith("[newtab]") or href.endswith("[download]"):
                marker = "[newtab]" if href.endswith("[newtab]") else "[download]"
                href = href[: -len(marker)].strip()
            if label and href and href != "#":
                pairs.append((label, href))
    return pairs


def href_link_locators(code: str, page_context: str) -> str:
    """Card/tile links have long, UNSTABLE accessible names (the whole card's text,
    which even changes with CSS reveal state), so a name match is unreliable and
    often finds nothing. The href is stable. Rewrite `getByRole('link', { name: X })`
    to `locator('a[href="<href>"]').first()` whenever X maps unambiguously to a link
    in the Discover link map — exact, then prefix, then substring match."""
    pairs = _parse_link_map(page_context)
    if not pairs:
        return code

    # How many DISTINCT labels share each href. An href used by >1 link is not a
    # unique handle (e.g. 'Tools' and 'The Toolkit' both -> '/#capabilities'); there
    # the accessible name is the distinguisher, so keep the name locator.
    href_labels: dict[str, set[str]] = {}
    for l, h in pairs:
        href_labels.setdefault(h, set()).add(l)

    # Match on an alphanumeric-only, lower-cased form so punctuation and whitespace
    # differences don't block a match. The link map's label comes from textContent
    # ("Security & Trust26 tools") while the model writes the ARIA accessible name
    # ("Security & Trust 26 tools"); normalized, both are "securitytrust26tools".
    def _norm(s: str) -> str:
        return re.sub(r"[^a-z0-9]+", "", s.lower())

    norm_pairs = [(_norm(l), h) for (l, h) in pairs]

    def find_href(x: str) -> str | None:
        xn = _norm(x)
        if not xn:
            return None
        # Directional prefix tiers, in order of confidence. The combined
        # `startswith` test used to be ONE tier, which made a card link's long
        # run-on name (e.g. the model's truncated "ML Unified PlatformPlatform ·
        # Enter…") tie between the card (map label starts WITH the code name) and a
        # shorter sibling link named just "ML Unified Platform" (code name starts
        # with THAT) — two hrefs, so it bailed and the brittle name locator shipped.
        # Splitting them resolves the card case uniquely: the model almost always
        # TRUNCATES a long name, so "map label starts with code name" wins first.
        for test in (
            lambda ln: ln == xn,
            lambda ln: ln.startswith(xn),
            lambda ln: xn.startswith(ln),
            lambda ln: xn in ln or ln in xn,
        ):
            hrefs = {h for (ln, h) in norm_pairs if ln and test(ln)}
            if len(hrefs) == 1:
                h = next(iter(hrefs))
                # Still require the href to belong to exactly ONE distinct label, so a
                # shared-destination anchor (e.g. two labels -> /#capabilities) keeps
                # its name locator rather than being collapsed to the wrong element.
                return h if len(href_labels.get(h, ())) == 1 else None
        return None

    def repl(m: "re.Match") -> str:
        if m.group(2).lower() != "link":
            return m.group(0)
        href = find_href(m.group(4))
        if not href:
            return m.group(0)
        # .first() because the SAME link often appears twice (nav + footer) with the
        # same href — all matches share one destination, so the first is correct.
        return "locator('a[href=\"" + href.replace('"', '\\"') + "\"]').first()"

    return _GETBYROLE_NAME.sub(repl, code)


def _page_name_counts(page_context: str) -> Counter:
    """How many page elements carry each accessible name (lower-cased). The ARIA
    snapshot lists every element, so true duplicates (nav + footer) are counted;
    link-map names not role-tagged are added once."""
    counts: Counter = Counter()
    for m in _CTX_ROLE_NAME.finditer(page_context):
        counts[m.group(1).lower()] += 1
    for line in page_context.splitlines():
        if " -> " in line:
            nm = line.split(" -> ", 1)[0].strip().lower()
            if nm and nm not in counts:
                counts[nm] += 1
    return counts


def disambiguate_locators(code: str, page_context: str) -> str:
    """Playwright strict mode needs a locator to match exactly one element. A
    name-only `getByRole` can match several: by case-insensitive SUBSTRING (e.g.
    'Tools' is inside 'Browse the tools') or because the SAME name repeats (a nav
    link also in the footer). Grounded in the real page, fix both — `exact: true`
    when a unique name is being over-matched by substring, `.first()` when the
    name genuinely repeats. Already-unique locators are left untouched."""
    counts = _page_name_counts(page_context)
    if not counts:
        return code
    items = list(counts.items())

    def repl(m: "re.Match") -> str:
        x = m.group(4).lower()
        if not x:
            return m.group(0)
        equals = sum(c for n, c in items if n == x)
        contains = sum(c for n, c in items if x in n)
        if equals >= 2:
            # Same name on >1 element — exact can't disambiguate; take the first.
            return m.group(0) + ".first()"
        if contains >= 2 and equals == 1:
            # Unique name over-matched by substring — pin it exact.
            q, nq = m.group(1), m.group(3)
            return f"getByRole({q}{m.group(2)}{q}, {{ name: {nq}{m.group(4)}{nq}, exact: true }})"
        return m.group(0)

    return _GETBYROLE_NAME.sub(repl, code)


# A `locator('a[href="..."]')` NOT already narrowed by a positional/filter method.
# The model writes raw href locators directly (following the "prefer href" rule) and
# forgets that the same href appears on several elements (nav + footer, or two links
# sharing one anchor) -> strict-mode violation. Append `.first()` so it resolves to
# one element, the same way the grounded rewrite already does.
_HREF_LOC_NO_POS = re.compile(
    r"(\.locator\(\s*(['\"])a\[href[^\]]*\]\2\s*\))"
    r"(?!\s*\.(?:first|last|nth|filter|all|count)\b)"
)


def first_on_href_locators(code: str) -> str:
    """Append `.first()` to any `locator('a[href=...]')` that isn't already narrowed —
    the deterministic fix for the strict-mode violation when an href matches >1 link."""
    return _HREF_LOC_NO_POS.sub(lambda m: m.group(1) + ".first()", code)


# A locator whose name/text argument is a wildcard or placeholder, e.g.
# `getByRole('button', { name: '*' })` or `getByText('...')`. The model invents these
# when it can't determine a real name; they match nothing and burn the full timeout.
# No backreference on the quotes: this fragment is concatenated into a two-branch
# alternation, where a `\1` would point at the wrong branch's group. A junk value is
# the same whether opened with ' or ", so loose quote matching is fine.
_JUNK_STR = r"['\"]\s*(?:\*+|\.{2,}|…|-{2,}|_+|)\s*['\"]"
_JUNK_NAME_LOC = re.compile(
    r"getByRole\([^)]*\bname:\s*" + _JUNK_STR + r"\s*\}"
    r"|(?:getByText|getByPlaceholder|getByLabel|getByTitle|getByAltText|getByTestId)\(\s*"
    + _JUNK_STR + r"\s*\)"
)


def strip_junk_locators(code: str) -> str:
    """Drop any standalone statement line that uses a wildcard/placeholder locator
    name (e.g. `name: '*'`). Such a step can only time out; removing it is strictly
    better than hanging, and keeps the rest of the test running."""
    kept = [ln for ln in code.split("\n") if not _JUNK_NAME_LOC.search(ln)]
    return "\n".join(kept)


# A `getByText('<long literal>') … .toBeHidden()` assertion. A real empty-state that a
# result replaces is short ('No results yet', 'Run to see output'); a multi-sentence
# page DESCRIPTION is permanent copy, so asserting it becomes hidden only times out.
_HIDDEN_TEXT_LINE = re.compile(
    r"getByText\(\s*(['\"`])(?P<t>.*?)\1\s*\)[\s\S]*?\.toBeHidden\s*\(")
# A visibility/enabled assertion ON A FILE INPUT. File inputs are usually hidden behind
# a styled dropzone, yet setInputFiles works on them anyway — so asserting the input is
# visible/enabled just times out on those tools. (setInputFiles / toHaveValue stay.)
_FILE_INPUT_VIS_LINE = re.compile(
    r"""locator\(\s*['"][^'"]*input\[type=["']?file["']?\][^'"]*['"]\s*\)"""
    r"[\s\S]*?\.(?:toBeVisible|toBeEnabled)\s*\(")


def strip_upload_assert_noise(code: str) -> str:
    """Drop two always-failing assertions the model emits around uploads, keeping the
    rest of the test: (1) `.toBeHidden()` on a long (>90-char) description string — a
    permanent paragraph the model mistook for an empty-state; (2) `.toBeVisible()` /
    `.toBeEnabled()` on a file input, which is often hidden behind a dropzone. The
    upload itself (setInputFiles) and the reliable `toHaveValue(/sample…/)` check stay."""
    kept = []
    for ln in code.split("\n"):
        m = _HIDDEN_TEXT_LINE.search(ln)
        if m and len(m.group("t")) > 90:
            continue
        if _FILE_INPUT_VIS_LINE.search(ln):
            continue
        kept.append(ln)
    return "\n".join(kept)


# Section/card titles on a dashboard are frequently <p>/<div>, not real <h*> headings,
# yet the model still writes getByRole('heading', {name}) for them — which matches
# nothing and times out on scroll/click/assert. These capture, from the page context,
# which names are REAL headings vs. which are paragraphs/plain text.
_ARIA_HEADING_NAME = re.compile(r'\bheading\s+"([^"\n]{1,120})"')
_CTRL_HEADING_NAME = re.compile(r'^\s*\[heading\]\s+name="([^"\n]{1,120})"\s*$', re.M)
_ARIA_PARA_TEXT = re.compile(r'^\s*-?\s*(?:paragraph|text):\s*(.+?)\s*$', re.M)
# getByRole('heading', { name: <'str' | "str" | /regex/flags> , exact?: ... })
_GBR_HEADING_CALL = re.compile(
    r"getByRole\(\s*['\"]heading['\"]\s*,\s*\{\s*name:\s*"
    r"(?P<name>/(?:\\.|[^/\n])+/[a-z]*|'[^'\n]*'|\"[^\"\n]*\")"
    r"[^{}]*\}\s*\)"
)


def _nrm(s: str) -> str:
    """Normalize to alnum-lowercase for tolerant name comparison."""
    return re.sub(r"[^a-z0-9]+", "", (s or "").lower())


def _name_literal_token(lit: str) -> str:
    """Comparable text inside a getByRole name literal — a quoted string's contents, or a
    regex literal's text with anchors/escapes stripped (so /^Activity Log/ -> 'Activity Log')."""
    s = lit.strip()
    if s.startswith("/"):
        end = s.rfind("/")
        body = s[1:end] if end > 0 else s[1:]
        body = re.sub(r"\\[a-zA-Z]", "", body).replace("^", "").replace("$", "").replace("\\", "")
        return body
    if len(s) >= 2 and s[0] in "'\"`":
        return s[1:-1]
    return s


def fix_invented_heading_role(code: str, ctx: str) -> str:
    """Rewrite getByRole('heading', {name}) -> getByText(name).first() when the captured
    context shows that name as a PARAGRAPH/TEXT, not a heading (a card/section title the
    model wrongly typed as a heading). A name that IS a captured heading, or that appears
    nowhere, is left untouched. Fixes scroll/click/assert timeouts on dashboard titles."""
    if not ctx:
        return code
    headings = {_nrm(m) for m in _ARIA_HEADING_NAME.findall(ctx)}
    headings |= {_nrm(m) for m in _CTRL_HEADING_NAME.findall(ctx)}
    paras = {_nrm(m) for m in _ARIA_PARA_TEXT.findall(ctx) if m.strip()}
    paras.discard("")
    if not paras:
        return code

    def _repl(m: re.Match) -> str:
        tok = _nrm(_name_literal_token(m.group("name")))
        if not tok:
            return m.group(0)
        is_heading = any(tok in h or h in tok for h in headings if h)
        is_para = any(tok in p or p in tok for p in paras if p)
        if is_heading or not is_para:
            return m.group(0)  # a real heading, or unknown — don't touch it
        return f"getByText({m.group('name')}).first()"

    out = _GBR_HEADING_CALL.sub(_repl, code)
    return out.replace(".first().first(", ".first(")  # collapse a redundant chain
