"""Documented cases that belong to a lane this suite cannot cover — they need a
live API call or a rendered page. Kept as explicit skips so the registry shows
them as known-and-waiting rather than silently missing.

Cases whose subject is the predecessor AutoML-generator project are NOT here:
that code was never in this monorepo, so a skip stub for it is code that can
never run. They are recorded as lane DEAD in the TestOps registry instead,
which is where "this is dead" belongs.
"""
from __future__ import annotations

import pytest


@pytest.mark.skip(reason="asserts a live API response — belongs to the backend lane, "
                         "not the repo-assertion lane")
def test_tc_early_009_predict_upload_batch_count():
    """TC-EARLY-009: POST /predict/upload returns a count matching the CSV row count"""


@pytest.mark.skip(reason="needs the rendered page, and the documented figures are a "
                         "point-in-time list — belongs to the browser lane")
def test_tc_p13_024_no_unverifiable_performance_claims():
    """TC-P13-024: unverifiable performance claims removed sitewide"""


@pytest.mark.skip(reason="needs the served HTML and the generated handbook chapters — "
                         "browser lane")
def test_tc_p13_036_corner_radii_use_tokens():
    """TC-P13-036: corner radii all resolve to the token scale (14/10px)"""


@pytest.mark.skip(reason="src/lib/capabilities.ts moved to src/data/capabilities/; the "
                         "documented path no longer identifies the subject")
def test_tc_p13_042_chapter_filenames_key_off_capability_id():
    """TC-P13-042: deep-chapter file names key off capability id, not route"""
