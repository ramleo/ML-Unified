#!/usr/bin/env python3
"""Produce a RAG-friendly copy of the handbook for the knowledge base.

The handbook (ml-portfolio/public/handbook.md) is the site's own comprehensive
description — what AIRaML is, who built it, every tool, the Public API and MCP.
The public RAG chat answers from data/knowledge_base, which held only ML-theory
docs, so site/feature questions had nothing to retrieve and the chat either
declined or confabulated (surfaced by the Q4 M2 eval, pass rate ~33%).

This strips the handbook's HTML/Paged.js scaffolding (title page, colophon, the
contents nav, the per-section <div> wrappers and anchor links) down to headings +
prose, and writes it to data/knowledge_base/airaml_handbook.md so the startup
ingest indexes it.

Re-run after regenerating the handbook (it is NOT auto-synced across repos):
    python3 scripts/sync_handbook_kb.py [path/to/handbook.md]
Default source is the sibling ml-portfolio checkout.
"""
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_SRC = os.path.normpath(os.path.join(
    HERE, "..", "..", "..", "..", "ml-portfolio", "public", "handbook.md"))
# Split into per-section files in this dir (load_kb_documents walks recursively),
# so no single KB file is enormous and each section is its own citation source.
DEST_DIR = os.path.normpath(os.path.join(HERE, "..", "data", "knowledge_base", "handbook"))


def clean(md: str) -> str:
    # Drop the Contents / TOC nav block entirely — it's just a list of links.
    md = re.sub(r"<nav\b.*?</nav>", "", md, flags=re.DOTALL | re.IGNORECASE)
    # Unwrap anchor links to their text: <a ...>EDA Explorer</a> -> EDA Explorer
    md = re.sub(r"<a\b[^>]*>(.*?)</a>", r"\1", md, flags=re.DOTALL | re.IGNORECASE)
    # Remove every remaining HTML tag (the bk-* <div> wrappers, page breaks, etc.).
    md = re.sub(r"<[^>]+>", "", md)
    # Collapse runs of blank lines.
    md = re.sub(r"\n{3,}", "\n\n", md)
    return md.strip() + "\n"


def _slug(title: str, i: int) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")[:60]
    return f"{i:02d}-{s or 'section'}"


# A section starts at a top-level (#) heading OR a tool "Chapter N<Title>" line
# (the number and title run together after HTML cleaning). One file per part-intro
# and per tool chapter → small, well-scoped KB sources instead of one huge file.
_BOUNDARY = re.compile(r"(?m)^(#\s+.+|Chapter\s+\d+.*)$")


def _title_of(heading: str) -> str:
    if heading.startswith("#"):
        return heading.lstrip("# ").strip()
    return re.sub(r"^Chapter\s+\d+\s*", "", heading).strip() or "chapter"


def split_sections(cleaned: str) -> list[tuple[str, str]]:
    parts = _BOUNDARY.split(cleaned)   # [pre, heading, body, heading, body, ...]
    sections: list[tuple[str, str]] = []
    pre = parts[0].strip()
    for i in range(1, len(parts), 2):
        heading = parts[i].strip()
        body = parts[i + 1] if i + 1 < len(parts) else ""
        text = f"{heading}\n{body}".strip()
        if i == 1 and pre:
            text = f"{pre}\n\n{text}"
        sections.append((_title_of(heading), text))
    return sections


def main() -> None:
    src = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_SRC
    if not os.path.isfile(src):
        raise SystemExit(f"handbook not found: {src}")
    cleaned = clean(open(src, encoding="utf-8").read())

    # Fresh dir each run so renamed/removed sections don't linger.
    if os.path.isdir(DEST_DIR):
        for f in os.listdir(DEST_DIR):
            if f.endswith(".md"):
                os.remove(os.path.join(DEST_DIR, f))
    os.makedirs(DEST_DIR, exist_ok=True)

    sections = split_sections(cleaned)
    for i, (title, text) in enumerate(sections, 1):
        path = os.path.join(DEST_DIR, _slug(title, i) + ".md")
        with open(path, "w", encoding="utf-8") as f:
            f.write(text.strip() + "\n")
    total = sum(len(t) for _, t in sections)
    print(f"wrote {len(sections)} files to {DEST_DIR} — {total:,} chars total")
    for i, (title, text) in enumerate(sections, 1):
        print(f"  {_slug(title, i)}.md — {text.count(chr(10)):,} lines")


if __name__ == "__main__":
    main()
