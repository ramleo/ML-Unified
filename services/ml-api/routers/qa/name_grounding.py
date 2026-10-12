"""
Testwright — name-grounding transforms (split out of locators.py to stay under the
400-line limit). Deterministic rewrites that keep a generated locator matching when
the page's control/heading NAMES are not what a naive capture assumed:
  * strip_upload_assert_noise — drop always-failing asserts around uploads;
  * fix_invented_heading_role — a <p> title typed as getByRole('heading') -> getByText;
  * stabilize_dynamic_control_names — match a name with a live count / state suffix by
    its stable prefix ('Warnings 1' -> /^Warnings/, 'Activity Log — today' -> /^Activity Log/).
These run in author.py's post-generation pipeline.
"""

import re


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


# A control/heading NAME often bakes in a value that CHANGES as the page is used — a
# live count ("Warnings 1" -> "Warnings 3", "Security & Trust 26 tools") or a state/range
# suffix ("Activity Log — today" -> "— 30d"). A test that switches that state can no
# longer match the captured string, so it times out. The fix is to match by the STABLE
# leading text via a prefix regex. One transform handles every such case at once.
_VOLATILE_SUFFIX = re.compile(r"\s*[—–-]\s+\S.*$")              # " — today", " – 30d", " - x"
_TRAILING_COUNT = re.compile(r"\s+\d[\d,]*(?:\s+[A-Za-z]+){0,2}\s*$")  # " 1", " 26 tools", " 1,204 rows"
# A disclosure caret flips with open/closed state ("✦ AI Explain ▼" -> "▲"), so a test
# that toggles the control can no longer match the captured glyph. Strip a trailing caret.
_TRAILING_CARET = re.compile(r"\s*[▼▲▾▴▸◂►◄▶◀⌄⌃˅˄]\s*$")
_JS_RE_SPECIAL = re.compile(r"[.*+?^${}()|\[\]\\/]")
# getByRole('role', { name: 'STRING' [, exact: ...] }) and getByText('STRING') — STRING
# literals only (a regex name is already stable; skip it).
_GBR_STR_NAME = re.compile(
    r"getByRole\(\s*(['\"])(?P<role>\w+)\1\s*,\s*\{\s*name:\s*"
    r"(['\"])(?P<name>[^'\"\n]*)\3(?P<rest>[^{}]*)\}\s*\)")
_GBT_STR = re.compile(r"getByText\(\s*(['\"])(?P<name>[^'\"\n]*)\1\s*\)")


def _stable_prefix(name: str) -> str | None:
    """The leading, non-volatile part of a control name, or None if the name has no
    volatile tail to strip (so stable names are left exactly as-is)."""
    s = _TRAILING_CARET.sub("", name).strip()
    s = _VOLATILE_SUFFIX.sub("", s).strip()
    s = _TRAILING_COUNT.sub("", s).strip()
    return s if (s != name.strip() and len(s) >= 3) else None


def _js_regex(prefix: str) -> str:
    return "/^" + _JS_RE_SPECIAL.sub(lambda m: "\\" + m.group(0), prefix) + "/"


def stabilize_dynamic_control_names(code: str) -> str:
    """Rewrite getByRole/getByText locators whose NAME carries a volatile value (a live
    count or a ' — state/range' suffix) to match by a stable PREFIX regex + .first(), so
    a test that changes the page's state still matches. Names without a volatile tail are
    untouched, and a name that is already a regex is skipped."""
    def _role(m: re.Match) -> str:
        pre = _stable_prefix(m.group("name"))
        if not pre:
            return m.group(0)
        return f"getByRole('{m.group('role')}', {{ name: {_js_regex(pre)} }}).first()"

    def _text(m: re.Match) -> str:
        pre = _stable_prefix(m.group("name"))
        if not pre:
            return m.group(0)
        return f"getByText({_js_regex(pre)}).first()"

    out = _GBR_STR_NAME.sub(_role, code)
    out = _GBT_STR.sub(_text, out)
    return out.replace(".first().first(", ".first(")  # collapse a redundant chain
