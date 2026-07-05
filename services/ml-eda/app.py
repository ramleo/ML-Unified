from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from routers import eda as _eda_router
from routers._suggest import router as _suggest_router
import collections
import time
from typing import Dict

app = FastAPI(title="ML EDA")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Request monitoring ────────────────────────────────────────────────────────
_SKIP_PATHS = {"/", "/health", "/metrics"}
_req_log: collections.deque = collections.deque(maxlen=1000)
_svc_start = time.time()


@app.middleware("http")
async def _monitor(request: Request, call_next):
    t0 = time.perf_counter()
    response = await call_next(request)
    ms = round((time.perf_counter() - t0) * 1000, 1)
    if request.url.path not in _SKIP_PATHS:
        _req_log.append({
            "ts":     time.time(),
            "path":   request.url.path,
            "method": request.method,
            "status": response.status_code,
            "ms":     ms,
        })
    return response


@app.get("/health")
def health():
    return {"status": "ok", "service": "ml-eda"}


@app.get("/metrics")
def get_metrics():
    logs = list(_req_log)
    uptime_s = int(time.time() - _svc_start)
    if not logs:
        return {"service": "ml-eda", "uptime_s": uptime_s,
                "total_requests": 0, "avg_ms": 0, "p95_ms": 0,
                "error_rate": 0.0, "endpoints": []}
    by_path: Dict[str, list] = collections.defaultdict(list)
    for r in logs:
        by_path[r["path"]].append(r)
    endpoints = []
    for path, reqs in sorted(by_path.items(), key=lambda x: -len(x[1])):
        times = sorted(r["ms"] for r in reqs)
        errs  = sum(1 for r in reqs if r["status"] >= 400)
        endpoints.append({
            "path":   path,
            "count":  len(reqs),
            "avg_ms": round(sum(times) / len(times), 1),
            "p95_ms": times[min(int(len(times) * 0.95), len(times) - 1)],
            "errors": errs,
        })
    all_ms  = sorted(r["ms"] for r in logs)
    all_err = sum(1 for r in logs if r["status"] >= 400)
    return {
        "service":        "ml-eda",
        "uptime_s":       uptime_s,
        "total_requests": len(logs),
        "avg_ms":         round(sum(all_ms) / len(all_ms), 1),
        "p95_ms":         all_ms[min(int(len(all_ms) * 0.95), len(all_ms) - 1)],
        "error_rate":     round(all_err / len(logs) * 100, 1),
        "endpoints":      endpoints,
    }


app.include_router(_eda_router.router)
app.include_router(_suggest_router)
