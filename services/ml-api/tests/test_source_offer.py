"""The AGPL-3.0 §13 source offer must actually reach the pages we serve.

This project is licensed AGPL-3.0 because three of its bundled detectors are
Ultralytics-architecture YOLO models (THIRD_PARTY.md explains why that decides
the licence of the whole thing). Section 13 attaches one obligation to running
it as a network service: users interacting with it remotely must be offered its
source. `frontend/source-notice.js` is how that offer is made — it injects a
link into the navbar of every page the Space serves.

That makes it the rare piece of frontend code with a legal consequence when it
silently stops loading, and the way it is wired makes silence likely: the
script tag sits at the end of an existing line in each HTML file (those files
are pinned in .file-length-baseline, so a new line fails CI), which is exactly
the kind of thing a careless reformat drops without anyone noticing.

So these assert the wiring rather than the rendering. A Playwright run proves
the pill appears; this proves the file exists, is reachable through the static
mount, and is referenced by all three pages — which is what a reformat breaks.
"""
from __future__ import annotations

import os

import pytest

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FRONTEND = os.path.join(HERE, "frontend")
PAGES = ("index.html", "eda.html", "vision.html")


def test_the_source_notice_script_exists():
    path = os.path.join(FRONTEND, "source-notice.js")
    assert os.path.isfile(path), "frontend/source-notice.js is the AGPL §13 offer and is missing"
    body = open(path, encoding="utf-8").read()
    assert "github.com/ramleo/ML-Unified" in body, "the offer must point at the source repository"


@pytest.mark.parametrize("page", PAGES)
def test_every_served_page_loads_the_source_notice(page):
    body = open(os.path.join(FRONTEND, page), encoding="utf-8").read()
    assert 'src="/static/source-notice.js"' in body, f"{page} no longer loads the source offer"


def test_the_repository_carries_the_licence_it_claims():
    # Two levels up from services/ml-api is the repository root.
    root = os.path.dirname(os.path.dirname(HERE))
    licence = os.path.join(root, "LICENSE")
    assert os.path.isfile(licence), "LICENSE is missing; the §13 offer would point at nothing"
    head = open(licence, encoding="utf-8").read(400)
    assert "GNU AFFERO GENERAL PUBLIC LICENSE" in head
    assert "Version 3" in head
