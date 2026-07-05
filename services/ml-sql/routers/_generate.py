"""Non-streaming SQL generation via Groq / Gemini / Cohere."""
from __future__ import annotations

import re
import httpx

_PROVIDERS: dict[str, dict] = {
    "groq":   {"env": "GROQ_API_KEY",   "model": "llama-3.3-70b-versatile"},
    "gemini": {"env": "GEMINI_API_KEY", "model": "gemini-2.0-flash"},
    "cohere": {"env": "COHERE_API_KEY", "model": "command-r-plus-08-2024"},
}


def get_provider_cfg(provider: str) -> dict:
    return _PROVIDERS.get(provider, _PROVIDERS["groq"])


def _build_sql_prompt(
    question: str,
    schema_text: str,
    prev_sql: str | None = None,
    error: str | None = None,
) -> str:
    lines = [
        "You are an expert SQL query writer. Generate a single valid SQL SELECT query.",
        "Return ONLY the raw SQL — no explanation, no markdown, no code fences.",
        "",
        f"Schema:\n{schema_text}",
        f"Question: {question}",
    ]
    if prev_sql and error:
        lines += [
            "",
            f"Previous attempt failed:\nSQL: {prev_sql}\nError: {error}",
            "Fix the SQL query based on the error above.",
        ]
    lines += [
        "",
        "Rules:",
        "- Use only SELECT statements",
        "- Use proper JOIN syntax when combining tables",
        "- Limit results to 100 rows unless the question asks for all",
        "- Use double-quotes for identifiers with spaces",
        "- Return ONLY the SQL query, nothing else",
    ]
    return "\n".join(lines)


def _extract_sql(text: str) -> str:
    """Strip markdown code fences and extract the first SELECT/WITH block."""
    text = re.sub(r"```(?:sql)?\s*", "", text, flags=re.IGNORECASE)
    text = text.replace("```", "").strip()
    match = re.search(r"((?:WITH|SELECT)\s+.+)", text, re.IGNORECASE | re.DOTALL)
    if match:
        text = match.group(1).strip()
    return text.rstrip(";").strip()


async def _call_groq(prompt: str, model: str, key: str) -> str:
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            json={
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "stream": False,
                "max_tokens": 512,
                "temperature": 0.1,
            },
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]


async def _call_gemini(prompt: str, model: str, key: str) -> str:
    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{model}:generateContent?key={key}"
    )
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            url,
            json={
                "contents": [{"role": "user", "parts": [{"text": prompt}]}],
                "generationConfig": {"maxOutputTokens": 512, "temperature": 0.1},
            },
        )
        resp.raise_for_status()
        return resp.json()["candidates"][0]["content"]["parts"][0]["text"]


async def _call_cohere(prompt: str, model: str, key: str) -> str:
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            "https://api.cohere.ai/v2/chat",
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            json={
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "stream": False,
                "max_tokens": 512,
                "temperature": 0.1,
            },
        )
        resp.raise_for_status()
        return resp.json()["message"]["content"][0]["text"]


async def generate_sql(
    question: str,
    schema_text: str,
    provider: str,
    key: str,
    prev_sql: str | None = None,
    error: str | None = None,
) -> str:
    """Call LLM (non-streaming) and return extracted SQL string."""
    cfg = get_provider_cfg(provider)
    prompt = _build_sql_prompt(question, schema_text, prev_sql, error)
    model = cfg["model"]

    if provider == "gemini":
        raw = await _call_gemini(prompt, model, key)
    elif provider == "cohere":
        raw = await _call_cohere(prompt, model, key)
    else:
        raw = await _call_groq(prompt, model, key)

    return _extract_sql(raw)