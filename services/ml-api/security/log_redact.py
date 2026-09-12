"""Keep API keys out of the logs.

Google's Gemini API takes its key as a URL query parameter rather than a
header, so every Gemini request URL contains a live secret. Two things then
log that URL: httpx's own INFO line for each request, and our WARNING in
llm.complete(), which formats httpx's exception — and the exception text
carries the URL too. Silencing httpx would only close the first of those.

A filter on the root logger closes both, covers all twelve Gemini call sites
at once, and keeps covering the thirteenth. Providers that authenticate with
a header (Mistral, Groq, OpenAI, Anthropic, Cohere) were never affected.
"""

from __future__ import annotations

import logging
import re

# `key=` in a query string, and the common header-style spellings, in case a
# future caller logs a request body or header dict.
_PATTERNS = [
    re.compile(r"(?i)([?&]key=)[^&\s'\"]+"),
    re.compile(r"(?i)((?:api[_-]?key|x-goog-api-key|authorization)[\"']?\s*[:=]\s*[\"']?)[^\s,&'\"}]+"),
]
_MASK = r"\1REDACTED"


def scrub(text: str) -> str:
    for pattern in _PATTERNS:
        text = pattern.sub(_MASK, text)
    return text


class RedactSecrets(logging.Filter):
    """Rewrites the record in place so every handler sees the masked text.

    Returns True always — this filters content, not records. Formatting is
    applied first because the secret usually arrives through a %s argument
    rather than being baked into the format string.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            message = record.getMessage()
        except Exception:
            return True
        if "key=" in message.lower() or "authorization" in message.lower():
            record.msg = scrub(message)
            record.args = ()
        return True


def install() -> None:
    """Attach to the root logger's handlers, so it applies to every logger."""
    f = RedactSecrets()
    root = logging.getLogger()
    for handler in root.handlers:
        handler.addFilter(f)
    # Handlers added later (uvicorn reconfiguring, say) miss the loop above;
    # the root logger's own filter catches records that propagate to it.
    root.addFilter(f)
