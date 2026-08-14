import base64

import pytest
from fastapi.testclient import TestClient

from app import app
from routers.rag import _image_gen_budget, mm_text_to_image

client = TestClient(app)


@pytest.fixture(autouse=True)
def _reset_budget_and_key(monkeypatch):
    _image_gen_budget._counts.clear()
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    yield
    _image_gen_budget._counts.clear()


def _fake_gemini_response(has_image: bool = True):
    class _Resp:
        def raise_for_status(self):
            pass

        def json(self):
            if has_image:
                data = base64.b64encode(b"fake-jpeg-bytes").decode()
                return {"candidates": [{"content": {"parts": [{"inlineData": {"data": data, "mimeType": "image/jpeg"}}]}}]}
            return {"candidates": [{"content": {"parts": [{"text": "no image, sorry"}]}}]}

    return _Resp()


class _FakeClient:
    def __init__(self, has_image=True, raise_exc=None, captured=None):
        self._has_image = has_image
        self._raise_exc = raise_exc
        self._captured = captured

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def post(self, *args, **kwargs):
        if self._captured is not None:
            self._captured.append(kwargs)
        if self._raise_exc:
            raise self._raise_exc
        return _fake_gemini_response(self._has_image)


def test_empty_prompt_rejected():
    res = client.post("/rag/mm-text-to-image", json={"prompt": "   "})
    assert res.status_code == 400


def test_overlength_prompt_rejected():
    res = client.post("/rag/mm-text-to-image", json={"prompt": "x" * 2001})
    assert res.status_code == 400


def test_missing_api_key(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    res = client.post("/rag/mm-text-to-image", json={"prompt": "a red apple"})
    assert res.status_code == 502
    assert "not configured" in res.json()["detail"]


def test_successful_generation(monkeypatch):
    monkeypatch.setattr("httpx.Client", lambda timeout: _FakeClient(has_image=True))
    res = client.post("/rag/mm-text-to-image", json={"prompt": "a red apple"})
    assert res.status_code == 200
    data = res.json()
    assert "image" in data
    assert data["mime_type"] == "image/jpeg"


def test_no_image_part_returns_502(monkeypatch):
    monkeypatch.setattr("httpx.Client", lambda timeout: _FakeClient(has_image=False))
    res = client.post("/rag/mm-text-to-image", json={"prompt": "a red apple"})
    assert res.status_code == 502
    assert "temporarily unavailable" in res.json()["detail"]


def test_upstream_exception_returns_502(monkeypatch):
    monkeypatch.setattr("httpx.Client", lambda timeout: _FakeClient(raise_exc=RuntimeError("boom")))
    res = client.post("/rag/mm-text-to-image", json={"prompt": "a red apple"})
    assert res.status_code == 502


def test_budget_exhausted_returns_429(monkeypatch):
    monkeypatch.setattr("httpx.Client", lambda timeout: _FakeClient(has_image=True))
    monkeypatch.setattr(_image_gen_budget, "_CAPS", {**_image_gen_budget._CAPS, "text2img": 2})
    for _ in range(2):
        res = client.post("/rag/mm-text-to-image", json={"prompt": "a red apple"})
        assert res.status_code == 200
    res = client.post("/rag/mm-text-to-image", json={"prompt": "a red apple"})
    assert res.status_code == 429
    assert "text-to-image" in res.json()["detail"].lower()


def test_budget_pools_independent():
    for _ in range(2):
        _image_gen_budget.check_and_record_call("deblur")
    for _ in range(2):
        _image_gen_budget.check_and_record_call("text-to-image", pool="text2img")
    today = __import__("datetime").datetime.now(__import__("datetime").timezone.utc).date().isoformat()
    assert _image_gen_budget._counts[("shared", today)] == 2
    assert _image_gen_budget._counts[("text2img", today)] == 2


def test_shared_pool_cap_still_40_by_default():
    for _ in range(40):
        _image_gen_budget.check_and_record_call("deblur")
    with pytest.raises(Exception):
        _image_gen_budget.check_and_record_call("ai-fill")


def test_text2img_pool_cap_default_15():
    for _ in range(15):
        _image_gen_budget.check_and_record_call("text-to-image", pool="text2img")
    with pytest.raises(Exception):
        _image_gen_budget.check_and_record_call("text-to-image", pool="text2img")


def test_unknown_style_rejected(monkeypatch):
    monkeypatch.setattr("httpx.Client", lambda timeout: _FakeClient(has_image=True))
    res = client.post("/rag/mm-text-to-image", json={"prompt": "a cat", "style": "not-a-real-style"})
    assert res.status_code == 400


def test_unknown_aspect_ratio_rejected(monkeypatch):
    monkeypatch.setattr("httpx.Client", lambda timeout: _FakeClient(has_image=True))
    res = client.post("/rag/mm-text-to-image", json={"prompt": "a cat", "aspect_ratio": "ultrawide"})
    assert res.status_code == 400


def test_overlength_negative_prompt_rejected(monkeypatch):
    monkeypatch.setattr("httpx.Client", lambda timeout: _FakeClient(has_image=True))
    res = client.post("/rag/mm-text-to-image", json={"prompt": "a cat", "negative_prompt": "x" * 501})
    assert res.status_code == 400


def test_style_aspect_ratio_negative_prompt_appended_to_sent_prompt(monkeypatch):
    captured = []
    monkeypatch.setattr("httpx.Client", lambda timeout: _FakeClient(has_image=True, captured=captured))
    res = client.post("/rag/mm-text-to-image", json={
        "prompt": "a cat on a tree",
        "style": "anime",
        "aspect_ratio": "landscape",
        "negative_prompt": "blurry, text, watermark",
    })
    assert res.status_code == 200
    sent_prompt = captured[0]["json"]["contents"][0]["parts"][0]["text"]
    assert "a cat on a tree" in sent_prompt
    assert "anime" in sent_prompt
    assert "16:9" in sent_prompt
    assert "blurry, text, watermark" in sent_prompt


def test_no_style_or_aspect_ratio_leaves_prompt_unmodified(monkeypatch):
    captured = []
    monkeypatch.setattr("httpx.Client", lambda timeout: _FakeClient(has_image=True, captured=captured))
    res = client.post("/rag/mm-text-to-image", json={"prompt": "a cat on a tree"})
    assert res.status_code == 200
    sent_prompt = captured[0]["json"]["contents"][0]["parts"][0]["text"]
    assert sent_prompt == "a cat on a tree"
