"""SSE progress streaming with tqdm integration.

Usage in a FastAPI endpoint:
    from shared.progress import StreamingTask
    from fastapi.responses import StreamingResponse

    @app.post("/some-endpoint")
    async def my_endpoint(...):
        task = StreamingTask()

        def work(p):
            p.update(10, "Loading data...")
            # ... heavy work ...
            p.update(80, "Computing...")
            # ...
            p.finish(result={"key": "value"})

        return StreamingResponse(task.stream(work), media_type="text/event-stream",
                                 headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
"""
from __future__ import annotations

import asyncio
import json
import threading
from tqdm import tqdm


class _Progress:
    """Passed to the worker function; wraps tqdm and SSE put."""

    def __init__(self, put_fn, total: int = 100):
        self._put  = put_fn
        self._pct  = 0
        self._bar  = tqdm(total=total, unit="%", ncols=70, colour="green",
                          bar_format="{l_bar}{bar}| {n}/{total}%")

    def update(self, target_pct: int, msg: str = "") -> None:
        """Advance to target_pct (0-100) and send an SSE event."""
        delta = max(0, target_pct - self._pct)
        if delta:
            self._bar.update(delta)
            self._bar.set_description(msg[:40] if msg else "")
        self._pct = max(self._pct, target_pct)
        self._put({"pct": self._pct, "msg": msg})

    def finish(self, result: dict | None = None, error: str | None = None) -> None:
        """Send the final event (with result payload or error)."""
        self._bar.close()
        payload: dict = {"done": True}
        if error:
            payload["error"] = error
            payload["pct"]   = -1
        else:
            payload["pct"]   = 100
            payload["msg"]   = "Done"
            if result is not None:
                payload["result"] = result
        self._put(payload)


class StreamingTask:
    """Runs a synchronous worker in a thread and yields SSE events."""

    def __init__(self) -> None:
        self._loop: asyncio.AbstractEventLoop | None = None
        self._queue: asyncio.Queue | None = None

    def _put(self, data: dict) -> None:
        if self._loop and self._queue:
            self._loop.call_soon_threadsafe(self._queue.put_nowait, data)

    def stream(self, worker_fn):
        """
        Returns an async generator of SSE-formatted strings.

        worker_fn(p: _Progress) — synchronous; call p.update() and p.finish().
        """
        self._loop  = asyncio.get_event_loop()
        self._queue = asyncio.Queue()
        put         = self._put

        def _run():
            p = _Progress(put)
            try:
                worker_fn(p)
            except Exception as exc:
                p.finish(error=str(exc))

        async def _generate():
            t = threading.Thread(target=_run, daemon=True)
            t.start()
            while True:
                item = await self._queue.get()
                yield f"data: {json.dumps(item)}\n\n"
                if item.get("done"):
                    break
            t.join()

        return _generate()
