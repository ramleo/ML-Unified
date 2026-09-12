"""Posting a golden to the running service and reading the SSE stream back.

The evals talk to the deployed Space over HTTP rather than importing the
extraction code, for two reasons. The provider keys live on the Space, so
nothing has to be copied into a second place to run this. And the money
bug this phase exists to catch lived in the wiring between the router, the
cascade and the keys — none of which an in-process call exercises the same
way.

Set EVAL_BASE_URL to point this somewhere else, e.g. a local uvicorn.
"""
from __future__ import annotations

import json
import os

import httpx

BASE_URL = os.environ.get("EVAL_BASE_URL", "https://wram1708-ml-unified.hf.space").rstrip("/")

# Generous: a document goes through classification, extraction and a
# validation pass, each a provider round trip, and a free tier is not fast.
TIMEOUT = httpx.Timeout(connect=30.0, read=240.0, write=60.0, pool=30.0)


class Result:
    """What one /document/analyze call produced."""

    def __init__(self) -> None:
        self.fields: list[dict] = []
        self.done: dict = {}
        self.warning: str = ""
        self.error: str = ""

    @property
    def provider(self) -> str:
        return str(self.done.get("provider", "")).strip()

    @property
    def doc_type(self) -> str:
        return str(self.done.get("doc_type", ""))

    @property
    def cached(self) -> bool:
        return bool(self.done.get("cached")) or "(cached)" in self.provider

    def field(self, name: str) -> dict | None:
        for f in self.fields:
            if f.get("name") == name:
                return f
        return None


def analyze(pdf_bytes: bytes, filename: str) -> Result:
    """One document in, one Result out. Network problems surface as
    `result.error` rather than an exception, so one unreachable run
    reports as a failed golden instead of killing the whole report."""
    result = Result()
    files = {"file": (filename, pdf_bytes, "application/pdf")}
    data = {"doc_type": "auto", "provider": "auto"}

    try:
        with httpx.Client(timeout=TIMEOUT) as client:
            with client.stream("POST", f"{BASE_URL}/document/analyze",
                               files=files, data=data) as response:
                if response.status_code != 200:
                    response.read()
                    result.error = f"HTTP {response.status_code}"
                    return result
                for line in response.iter_lines():
                    if not line.startswith("data: "):
                        continue
                    try:
                        event = json.loads(line[6:])
                    except json.JSONDecodeError:
                        continue
                    if "field" in event:
                        result.fields.append(event["field"])
                    elif event.get("done"):
                        result.done = event
                    elif "warning" in event:
                        result.warning = str(event["warning"])
                    elif "error" in event:
                        result.error = str(event["error"])
    except Exception as exc:  # noqa: BLE001 — a report beats a traceback here
        result.error = f"{type(exc).__name__}: {exc}"

    return result
