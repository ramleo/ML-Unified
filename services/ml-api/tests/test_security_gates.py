"""Phase 3: the gates that run before any router does.

Origin blocking, body-size capping and the upload scanner are middleware
and helpers — pure functions of a request's headers. They are also the
layer nobody exercises by hand, because doing so means crafting a request
that is supposed to be refused.

Two of the tests below encode bugs that were already paid for:

- the origin check must be a FULL match. `https://evil.com/?x=.vercel.app`
  contains the allowed pattern; matching loosely would let it through.
- `blocking_matches` exists because /rag/mm-ingest treated a bare entropy
  match as a verdict and refused every real PDF, image, video and audio
  file it was ever given. Every compressed file has high entropy. That is
  not evidence of anything.
"""
from __future__ import annotations

import asyncio

import pytest
from starlette.requests import Request

from security import body_size, origin_policy


def request_with(headers: dict[str, str], path: str = "/x") -> Request:
    raw = [(k.lower().encode(), v.encode()) for k, v in headers.items()]
    return Request({
        "type": "http", "http_version": "1.1", "method": "POST",
        "scheme": "https", "server": ("test", 443), "path": path,
        "raw_path": path.encode(), "query_string": b"", "headers": raw,
        "client": ("203.0.113.9", 1234),
    })


async def _served(request):
    """Stands in for the rest of the app. If a gate lets a request through,
    this is what answers."""
    class _Ok:
        status_code = 200
    return _Ok()


def run_gate(gate, request):
    return asyncio.run(gate(request, _served))


# -- Origin allowlist ----------------------------------------------------------

@pytest.mark.parametrize(
    "origin",
    [
        "https://ml-portfolio-rho.vercel.app",
        "http://localhost:3000",
        "http://localhost:3300",
        "https://ml-portfolio-git-some-branch-ramleo.vercel.app",
    ],
)
def test_the_real_front_ends_are_allowed(origin):
    """3300 matters beyond CORS: the demo recorder and the end-to-end suite
    both serve there because it is the only other allowlisted local port."""
    assert origin_policy.is_allowed_origin(origin)


@pytest.mark.parametrize(
    "origin",
    [
        "https://evil.com",
        "http://localhost:3001",
        "http://ml-portfolio-rho.vercel.app",          # http, not https
        "https://ml-portfolio-rho.vercel.app.evil.com",  # allowed host as a prefix
        "https://evil.com/?next=https://x.vercel.app",   # allowed pattern inside a longer string
        "https://vercel.app",                            # the bare apex, no subdomain
    ],
)
def test_a_lookalike_origin_is_refused(origin):
    assert not origin_policy.is_allowed_origin(origin)


def test_a_blocked_origin_never_reaches_a_router():
    """CORS headers are a negotiation a proxy can override, and the Space's
    front door does exactly that. This is the gate that actually refuses."""
    response = run_gate(origin_policy.enforce_origin, request_with({"origin": "https://evil.com"}))

    assert response.status_code == 403


def test_an_allowed_origin_passes_through():
    response = run_gate(
        origin_policy.enforce_origin,
        request_with({"origin": "https://ml-portfolio-rho.vercel.app"}),
    )
    assert response.status_code == 200


def test_a_request_with_no_origin_header_is_not_blocked():
    """Only a browser sends Origin on a cross-site request. curl, the
    Space's own healthcheck and every server-to-server caller send none,
    and blocking them would break legitimate use to stop nothing."""
    assert run_gate(origin_policy.enforce_origin, request_with({})).status_code == 200


def test_the_cors_kwargs_are_not_a_wildcard():
    """This replaced `allow_origins=["*"]` across roughly fifty public
    routers. A regression to the wildcard would look like nothing in a
    diff and undo the whole module."""
    kwargs = origin_policy.get_cors_kwargs()
    assert "*" not in kwargs["allow_origins"]
    assert kwargs["allow_origins"]


# -- Body size -----------------------------------------------------------------

def test_a_body_over_the_cap_is_refused_before_it_is_read():
    over = str(body_size.MAX_BODY_BYTES + 1)

    response = run_gate(body_size.enforce_body_size, request_with({"content-length": over}))

    assert response.status_code == 413


def test_a_body_exactly_at_the_cap_is_allowed():
    """Off by one here rejects a legitimate 10MB upload."""
    exact = str(body_size.MAX_BODY_BYTES)

    assert run_gate(body_size.enforce_body_size, request_with({"content-length": exact})).status_code == 200


def test_a_normal_body_passes():
    assert run_gate(body_size.enforce_body_size, request_with({"content-length": "2048"})).status_code == 200


def test_a_request_with_no_content_length_is_not_blocked_here():
    """Chunked transfer declares no length. Starlette and uvicorn have
    their own transport-level limit for that case; guessing one here would
    reject streaming uploads that are fine."""
    assert run_gate(body_size.enforce_body_size, request_with({})).status_code == 200


def test_a_garbage_content_length_does_not_crash_the_gate():
    """A malformed header must not turn a middleware into a 500 on every
    route in the app."""
    assert run_gate(body_size.enforce_body_size,
                    request_with({"content-length": "not-a-number"})).status_code == 200


# -- Upload scanning -----------------------------------------------------------

def test_an_advisory_match_alone_is_not_grounds_to_refuse_a_file():
    """The bug this encodes: high entropy is a property of every
    compressed file. Treated as a verdict, it rejected the entire input of
    the Multimodal RAG tool."""
    pytest.importorskip("yara", reason="yara-python is installed in CI, not always locally")
    from routers.yara_scan import ADVISORY_RULES
    from security.file_gate import blocking_matches

    advisory = [{"rule": rule} for rule in ADVISORY_RULES]

    assert blocking_matches(advisory) == []


def test_real_evidence_still_blocks():
    pytest.importorskip("yara", reason="yara-python is installed in CI, not always locally")
    from routers.yara_scan import ADVISORY_RULES
    from security.file_gate import blocking_matches

    matches = [{"rule": "EICAR_Test_File"}] + [{"rule": r} for r in ADVISORY_RULES]

    assert [m["rule"] for m in blocking_matches(matches)] == ["EICAR_Test_File"]


def test_a_clean_file_produces_nothing_to_block():
    pytest.importorskip("yara", reason="yara-python is installed in CI, not always locally")
    from security.file_gate import blocking_matches

    assert blocking_matches([]) == []


def test_a_broken_rule_set_fails_open_rather_than_breaking_uploads(monkeypatch):
    """A scanner problem must not take down an unrelated upload feature."""
    pytest.importorskip("yara", reason="yara-python is installed in CI, not always locally")
    from security import file_gate

    monkeypatch.setattr(file_gate, "_get_builtin_rules",
                        lambda: (_ for _ in ()).throw(RuntimeError("rules failed to compile")))

    assert file_gate.scan_upload_bytes(b"anything") == []


# -- The app's own origin ------------------------------------------------------

def test_the_apps_own_space_origin_is_allowed(monkeypatch):
    """ml-api serves three legacy static pages at /?mode=... and they POST
    back to this same host. A same-origin POST still carries an Origin
    header, so without this the app answered 403 to its own UI — which it
    did, on every upload on every one of those pages."""
    monkeypatch.setenv("SPACE_HOST", "wram1708-ml-unified.hf.space")
    monkeypatch.delenv("SPACE_ID", raising=False)

    assert origin_policy._self_origins() == ["https://wram1708-ml-unified.hf.space"]


def test_the_host_is_derived_from_the_space_id_when_the_host_is_absent(monkeypatch):
    monkeypatch.delenv("SPACE_HOST", raising=False)
    monkeypatch.setenv("SPACE_ID", "Wram1708/ML-Unified")

    assert origin_policy._self_origins() == ["https://wram1708-ml-unified.hf.space"]


def test_a_host_that_already_has_a_scheme_is_not_doubled(monkeypatch):
    monkeypatch.setenv("SPACE_HOST", "https://wram1708-ml-unified.hf.space")

    assert origin_policy._self_origins() == ["https://wram1708-ml-unified.hf.space"]


def test_off_platform_there_is_no_self_origin(monkeypatch):
    """Locally neither variable is set, and the fixed list is already right.
    Guessing a host here would add an origin nobody controls."""
    monkeypatch.delenv("SPACE_HOST", raising=False)
    monkeypatch.delenv("SPACE_ID", raising=False)

    assert origin_policy._self_origins() == []


def test_a_malformed_space_id_is_ignored_rather_than_guessed(monkeypatch):
    monkeypatch.delenv("SPACE_HOST", raising=False)
    monkeypatch.setenv("SPACE_ID", "no-slash-here")

    assert origin_policy._self_origins() == []


def test_the_self_origin_does_not_open_the_door_to_other_spaces():
    """The fix adds one exact origin. It must not become "any hf.space",
    which would let every Space on the platform call this API."""
    assert not origin_policy.is_allowed_origin("https://someone-else.hf.space")
    assert not origin_policy.is_allowed_origin("https://wram1708-ml-unified.hf.space.evil.com")
