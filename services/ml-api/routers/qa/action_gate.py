"""
Testwright — deterministic grounded-action gate.

The model sometimes grounds a real STRING but invents its ROLE (e.g. clicks a
heading's text as if it were a button). The industry fix (Octomind / Playwright-MCP
/ Checkly): feed the model only interactive elements and refuse actions on anything
else. We enforce it deterministically here — any click/fill/select whose target is
not in the page's captured interactive allow-list gets its whole test() block
dropped, rather than shipping a guaranteed-red test.

The allow-list comes from the page context Discover captured: the `[role] name=...`
/ `[role] placeholder=...` CONTROLS lines plus the ARIA snapshot's `role "name"`
lines. Assertions (expect(...)) are NEVER touched — only interaction verbs.
"""

import re


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", (s or "").lower())


# Roles a user can actually interact with (click/fill/select/check/...).
_INTERACTIVE_ROLES = {
    "button", "link", "checkbox", "radio", "tab", "menuitem", "menuitemcheckbox",
    "menuitemradio", "option", "switch", "combobox", "textbox", "searchbox",
    "slider", "spinbutton", "listbox", "gridcell",
}
# Interaction verbs (NOT assertions — `expect(...).toBeVisible()` is always allowed).
_ACTION_VERBS = (
    "click", "dblclick", "fill", "type", "press", "check", "uncheck",
    "setChecked", "selectOption", "tap", "setInputFiles",
)
_VERB_RE = re.compile(r"\.(?:" + "|".join(_ACTION_VERBS) + r")\s*\(")
_LOC_CALL_RE = re.compile(
    r"(getByRole|getByPlaceholder|getByText|getByLabel|getByTitle|getByAltText|"
    r"getByTestId|locator)\s*\("
)
# `[role] name="..."` / `[role] placeholder="..."` lines from a CONTROLS block.
_CONTROL_LINE = re.compile(r'^\s*\[([a-z][\w-]*)\]\s+(name|placeholder)="(.*)"\s*$')
# A role "name" entry in an ARIA snapshot (e.g. `- button "Open the platform"`).
_ARIA_ROLE_NAME = re.compile(r'\b([a-z]+)\s+"([^"\n]{1,120})"')
_GBR_ROLE_NAME = re.compile(
    r"getByRole\(\s*['\"](\w+)['\"]\s*(?:,\s*\{[^{}]*?\bname:\s*(['\"])(.*?)\2[^{}]*\})?"
)
_GBP_ARG = re.compile(r"getByPlaceholder\(\s*(['\"])(.*?)\1")


def _parse_interactive(ctx: str) -> tuple[dict, set, set]:
    """Build the interactive allow-list from the page context: a role -> {names}
    map plus the set of real placeholders. Sources: the `[role] name=`/`placeholder=`
    CONTROLS blocks AND the ARIA snapshot's `role "name"` lines."""
    by_role: dict[str, set] = {}
    placeholders: set = set()
    for line in ctx.splitlines():
        m = _CONTROL_LINE.match(line)
        if m:
            role, kind, val = m.group(1).lower(), m.group(2), m.group(3)
            if kind == "placeholder":
                placeholders.add(_norm(val))
            by_role.setdefault(role, set()).add(_norm(val))
    for m in _ARIA_ROLE_NAME.finditer(ctx):
        role = m.group(1).lower()
        if role in _INTERACTIVE_ROLES:
            by_role.setdefault(role, set()).add(_norm(m.group(2)))
    return by_role, placeholders, {n for s in by_role.values() for n in s}


def _match_delim(code: str, open_idx: int, op: str, cl: str) -> int:
    """Index of the delimiter closing the one at open_idx, skipping string/template
    literals. Returns -1 if unbalanced."""
    depth, i, n, quote = 0, open_idx, len(code), None
    while i < n:
        c = code[i]
        if quote:
            if c == "\\":
                i += 2
                continue
            if c == quote:
                quote = None
        elif c in "'\"`":
            quote = c
        elif c == op:
            depth += 1
        elif c == cl:
            depth -= 1
            if depth == 0:
                return i
        i += 1
    return -1


def _find_test_blocks(code: str) -> list[tuple[int, int]]:
    """(start, end) spans of each individual `test(...)` case, braces/strings
    balanced. `test.describe(` is excluded so dropping one case never removes its
    siblings; `test.only/skip/fixme` are included."""
    spans = []
    for m in re.finditer(r"\btest(?:\.(?:only|skip|fixme))?\s*\(", code):
        arrow = code.find("=>", m.end())
        brace = code.find("{", arrow) if arrow != -1 else -1
        if brace == -1:
            continue
        end = _match_delim(code, brace, "{", "}")
        if end == -1:
            continue
        tail = re.match(r"\s*\)\s*;?", code[end + 1:])
        spans.append((m.start(), end + 1 + (tail.end() if tail else 0)))
    return spans


def _name_ok(by_role: dict, role: str, name: str) -> bool:
    nn = _norm(name)
    if not nn:
        return True  # can't judge an empty/odd name — don't drop on it
    return any(nn in cn or cn in nn for cn in by_role.get(role, set()))


def _target_grounded(subject: str, var_map: dict, by_role: dict, placeholders: set) -> bool:
    """Is the locator that this action runs on a REAL interactive element? Only the
    precise, low-false-positive cases are judged (getByRole w/ string name,
    getByPlaceholder); everything else (locator/testid/text/label/regex/role-only)
    is treated as grounded so valid tests are never dropped."""
    expr = subject
    if not _LOC_CALL_RE.search(expr):
        var = re.search(r"([A-Za-z_$][\w$]*)\s*$", subject.strip())
        if var and var.group(1) in var_map:
            expr = var_map[var.group(1)]
    calls = list(_LOC_CALL_RE.finditer(expr))
    if not calls:
        return True
    frag = expr[calls[-1].start():]
    gbr = _GBR_ROLE_NAME.match(frag)
    if gbr:
        role, name = gbr.group(1).lower(), gbr.group(3)
        if name is None:
            return role in by_role  # role-only: fine if that role exists
        if role not in _INTERACTIVE_ROLES:
            return False  # interacting with a non-interactive role (e.g. heading)
        return _name_ok(by_role, role, name)
    gbp = _GBP_ARG.match(frag)
    if gbp:
        pn = _norm(gbp.group(2))
        return any(pn in p or p in pn for p in placeholders) if placeholders else True
    return True  # locator()/getByTestId/getByText/getByLabel/... — not judged


def drop_ungrounded_actions(code: str, ctx: str) -> str:
    """Remove any test() block that INTERACTS with an element absent from the page's
    interactive allow-list (e.g. clicks a heading's text as a button). Assertions are
    never touched. If nothing is captured, the code is returned unchanged."""
    by_role, placeholders, _ = _parse_interactive(ctx)
    if not by_role and not placeholders:
        return code
    var_map = {}
    for m in re.finditer(r"(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=\s*([^\n;]+)", code):
        if _LOC_CALL_RE.search(m.group(2)):
            var_map[m.group(1)] = m.group(2)

    drop: list[tuple[int, int]] = []
    for (s, e) in _find_test_blocks(code):
        block = code[s:e]
        for vm in _VERB_RE.finditer(block):
            # Statement start = last `;` or newline before the verb. (NOT braces — a
            # locator's own `{ name: ... }` options object would false-split it.)
            stmt_start = max(block.rfind(";", 0, vm.start()),
                             block.rfind("\n", 0, vm.start())) + 1
            if not _target_grounded(block[stmt_start:vm.start()], var_map, by_role, placeholders):
                drop.append((s, e))
                break
    if not drop:
        return code
    out, prev = [], 0
    for (s, e) in drop:
        out.append(code[prev:s])
        prev = e
    out.append(code[prev:])
    return re.sub(r"\n{3,}", "\n\n", "".join(out))
