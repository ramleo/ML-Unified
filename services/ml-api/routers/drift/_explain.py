"""Drift LLM explanation — yields SSE tokens from the chosen provider."""
from __future__ import annotations

import json
import os
from typing import Any

_PROVIDER_MODELS = {
    "groq":   "llama-3.3-70b-versatile",
    "gemini": "gemini-2.0-flash",
    "cohere": "command-r-plus",
}

_ENV_KEYS = {
    "groq":   "GROQ_API_KEY",
    "gemini": "GEMINI_API_KEY",
    "cohere": "COHERE_API_KEY",
}

_SYSTEM = (
    "You are an ML monitoring expert. Analyze data drift reports and explain them "
    "clearly and concisely. Be direct and actionable. Use technical ML terminology "
    "where appropriate but keep explanations accessible."
)


def _sse(obj: Any) -> str:
    return f"data: {json.dumps(obj)}\n\n"


def _build_prompt(result: dict) -> str:
    features = result.get("features", [])
    high   = [f for f in features if f.get("drift_level") == "high"]
    medium = [f for f in features if f.get("drift_level") == "medium"]

    lines = [
        "Analyze this data drift monitoring report and provide actionable insights.",
        "",
        "═══ REPORT SUMMARY ═══",
        f"Overall drift: {result.get('overall_score', 0):.1%}  ({result.get('overall_level', 'unknown').upper()})",
        f"Batch size:    {result.get('n_recent', '?')} rows",
        f"Features:      {len(features)} total | {len(high)} high-drift | {len(medium)} medium-drift",
        "",
        "═══ FEATURE BREAKDOWN (by severity) ═══",
    ]

    for f in sorted(features, key=lambda x: x.get("drift_score", 0), reverse=True)[:12]:
        nm  = f.get("label", f.get("name", ""))
        lv  = f.get("drift_level", "low")
        psi = f.get("psi", 0)
        ft  = f.get("type", "")
        seg = f"  [{lv.upper():6}] {nm} ({ft}) — PSI={psi:.3f}"

        if ft == "numeric":
            rm, bm = f.get("ref_mean"), f.get("recent_mean")
            if rm is not None and bm is not None:
                chg = ((bm - rm) / (abs(rm) + 1e-9)) * 100
                seg += f", mean {rm:.3f}→{bm:.3f} ({chg:+.1f}%)"
            ks  = f.get("ks_stat")
            ksp = f.get("ks_pvalue")
            if ks is not None:
                seg += f", KS={ks:.3f}"
                if ksp is not None:
                    sig = "significant" if ksp < 0.05 else "not significant"
                    seg += f" (p={ksp:.3f}, {sig})"

        lines.append(seg)

    lines += [
        "",
        "═══ YOUR ANALYSIS (please cover all four points) ═══",
        "1. Plain-language summary — what does this drift mean in practice? (2-3 sentences)",
        "2. Most critical features — which are most concerning and why?",
        "3. Root causes — what likely caused this drift? (e.g. data pipeline changes, "
           "seasonality, concept drift, sampling bias, upstream schema changes)",
        "4. Recommended actions — concrete next steps for the ML team",
    ]
    return "\n".join(lines)


def explain_stream(result: dict, provider: str):
    """Yield SSE-formatted strings for the drift explanation."""
    from routers.rag.llm import stream_groq_openai, stream_gemini, stream_cohere

    provider = (provider or "groq").lower()
    model    = _PROVIDER_MODELS.get(provider, "llama-3.3-70b-versatile")
    env_var  = _ENV_KEYS.get(provider, "")
    key      = os.environ.get(env_var, "")

    if not key:
        yield _sse({
            "type": "error",
            "message": f"No API key configured for '{provider}'. "
                       f"Set {env_var} in your HF Space secrets.",
        })
        return

    prompt   = _build_prompt(result)
    messages = [{"role": "user", "content": prompt}]

    try:
        if provider == "gemini":
            gen = stream_gemini(model, key, messages, _SYSTEM)
        elif provider == "cohere":
            gen = stream_cohere(model, key, messages, _SYSTEM)
        else:
            full_msgs = [{"role": "system", "content": _SYSTEM}] + messages
            gen = stream_groq_openai("groq", model, key, full_msgs)

        for token in gen:
            yield _sse({"type": "token", "text": token})

        yield _sse({"type": "done"})

    except Exception as exc:  # noqa: BLE001
        yield _sse({"type": "error", "message": str(exc)})
