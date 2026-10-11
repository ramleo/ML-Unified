"""
Testwright — the shared test-fixture catalog (Phase 2).

Many of the portfolio's tools need a FILE (a CSV/image/PDF/audio/video to upload)
or a CAMERA before they do anything. Before Phase 2 a generated test could not get
past them — there was no file to upload, and CI has no camera — so ~34 tools were
effectively untestable. The fix:

  * small sample files are committed to the runner repo (`ml-qa-runner/fixtures/`)
    and shipped with the companion; a generated test uploads one with
    `setInputFiles('fixtures/<name>')`;
  * the runner/companion launch Chromium with fake-media flags, so camera tools run
    against a synthetic stream (see each repo's playwright.config).

This module is the SINGLE SOURCE OF TRUTH for which fixture matches which input, and
builds the `===MEDIA===` grounding block Discover hands to Author. Keep FIXTURES in
sync with the files committed under `ml-qa-runner/fixtures/`.
"""

import re

# Delimiter the explore spec uses to append raw file-input facts to aria.txt, and
# the same string escaped for a JS single-quoted literal (used in discover.py's spec).
FILEINPUTS_DELIM = "\n\n===FILEINPUTS===\n"
FILEINPUTS_DELIM_JS = FILEINPUTS_DELIM.replace("\n", "\\n")

# Header for the grounding block Author consumes.
MEDIA_DELIM = "\n\n===MEDIA (uploads & camera — use these EXACT fixtures)===\n"

# Each fixture: committed filename, the accept-substrings it satisfies, description.
# Order matters — the first match wins, so put specific types before generic ones.
FIXTURES = [
    ("sample.csv", ("csv", "excel", "spreadsheet", ".tsv"), "a small CSV data table"),
    ("sample.pdf", ("pdf",), "a one-page PDF document"),
    ("sample.wav", ("audio", "wav", "mp3", ".m4a", ".ogg"), "a short WAV audio clip"),
    ("sample.mp4", ("video", "mp4", ".mov", ".webm", ".avi"), "a short MP4 video"),
    ("sample.jpg", (".jpg", ".jpeg", "jpeg"), "a small JPEG photo"),
    ("sample.png", ("image", "png", ".gif", ".webp", ".bmp"), "a small PNG image"),
    ("sample.txt", ("text", "txt", ".log", ".json", ".md"), "a small text/log file"),
]
# Most file-input tools here take an image, so that is the safe default.
DEFAULT_FIXTURE = "sample.png"


def fixture_for_accept(accept: str) -> str:
    """Pick the best committed fixture filename for an `<input accept="...">` value."""
    a = (accept or "").lower()
    if not a:
        return DEFAULT_FIXTURE
    for name, keys, _desc in FIXTURES:
        if any(k in a for k in keys):
            return name
    return DEFAULT_FIXTURE


# Camera/mic controls: a button named like one of these means the page asks for a
# live stream. The fake-media launch flags satisfy getUserMedia, so a test just
# clicks the control. Conservative phrases only (avoid bare "start"/"record").
_CAMERA_RE = re.compile(
    r"\b(start camera|open camera|use camera|enable camera|take photo|take a photo|"
    r"capture (photo|image|frame)|webcam|start video|record video|scan (qr|code)|"
    r"live camera|turn on camera)\b", re.I)


def split_fileinputs(aria: str) -> tuple[str, str]:
    """Separate the raw ===FILEINPUTS=== block (if any) from the rest of the snapshot,
    so it survives the MAX_PAGE_CONTEXT truncation applied to the snapshot body.
    Returns (snapshot_without_block, raw_fileinputs_lines)."""
    head, sep, tail = aria.partition(FILEINPUTS_DELIM)
    if not sep:
        return aria, ""
    # The block runs until the next `===…===` section header, or to the end.
    nxt = re.search(r"\n\n===", tail)
    raw = tail[: nxt.start()] if nxt else tail
    rest = head + (tail[nxt.start():] if nxt else "")
    return rest, raw.strip()


def media_hint(fileinputs_raw: str, context: str) -> str:
    """Build the ===MEDIA=== grounding block: a concrete `setInputFiles('fixtures/…')`
    line per detected file input, plus a camera line if the page has a camera control.
    Returns '' when the page needs neither (so most pages are unaffected)."""
    lines: list[str] = []
    for row in (fileinputs_raw or "").splitlines():
        if not row.strip():
            continue
        accept, _, label = row.partition("\t")
        fx = fixture_for_accept(accept)
        near = f' near "{label.strip()}"' if label.strip() else ""
        acc = f' accept="{accept.strip()}"' if accept.strip() else ""
        lines.append(
            f"file input{acc}{near} -> upload with "
            f"page.locator('input[type=\"file\"]').setInputFiles('fixtures/{fx}')")
    if _CAMERA_RE.search(context or ""):
        lines.append(
            "camera: a fake camera/mic stream is already provided — just click the "
            "capture/start control (no permission handling needed), then assert the "
            "resulting state change.")
    return MEDIA_DELIM + "\n".join(lines) + "\n" if lines else ""
