"""E21 regression: DELETE /models/{id} requires a real browser Origin.

The route permanently deletes a model (disk + HF store). `enforce_origin`
already 403s a disallowed Origin but lets a no-Origin request through by
design, so a plain `curl -X DELETE https://…/models/<id>` deleted models
(that is how 8 leftover test models were cleaned up on 2026-09-16). A browser
always sends Origin on a DELETE, so the route now requires an allowlisted one.

These tests pin the guard: a no-Origin or foreign-Origin delete is refused
before any deletion, an allowlisted Origin gets past the guard (404 for an
unknown id proves it reached the lookup), and a built-in model is still
protected. The guard is deliberately partial — a curl can forge the Origin
header — so there is no test claiming it stops a determined script; only
Turnstile/auth would, judged disproportionate for a regenerable demo model.
"""
from fastapi.testclient import TestClient

from app import app

client = TestClient(app)

ALLOWED = "https://ml-portfolio-rho.vercel.app"


def test_delete_with_no_origin_is_refused():
    r = client.delete("/models/does-not-exist")
    assert r.status_code == 403


def test_delete_with_a_foreign_origin_is_refused():
    r = client.delete("/models/does-not-exist", headers={"origin": "https://evil.example"})
    assert r.status_code == 403


def test_delete_with_an_allowed_origin_reaches_the_lookup():
    # 404 (not 403) proves the origin guard passed and the route ran — the id
    # simply does not exist. This is the "does not false-positive" check.
    r = client.delete("/models/does-not-exist", headers={"origin": ALLOWED})
    assert r.status_code == 404


def test_a_builtin_is_still_protected_even_from_an_allowed_origin():
    r = client.delete("/models/iris", headers={"origin": ALLOWED})
    assert r.status_code == 400
    assert "built-in" in r.json()["detail"].lower()


def test_a_builtin_delete_with_no_origin_is_refused_by_the_origin_guard_first():
    # Origin is checked before the built-in check, so this is 403, not 400 —
    # the destructive route refuses an unauthenticated caller outright.
    r = client.delete("/models/iris")
    assert r.status_code == 403
