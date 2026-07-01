"""LLM-based explanation helpers for AutoML results.

Extracted from automl_helpers.py to keep that file under 400 lines.
RAG context retrieval added here: _llm_explanation fetches top-3 KB chunks
about the winning algorithm and injects them into the prompt.
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def _rag_context_for_winner(winner: str) -> str:
    """Retrieve top-3 KB chunks about the winning algorithm. Returns '' if RAG unavailable."""
    try:
        from routers.rag import get_rag_state
        from routers.rag.retrieve import multi_query_retrieve
        from routers.rag.rerank import rerank
        state = get_rag_state()
        query = f"{winner} algorithm how it works strengths advantages tabular data"
        chunks = rerank(query, multi_query_retrieve([query], state, top_k=20), state, top_k=3)
        if not chunks:
            return ""
        parts = [f"[{c.get('source', 'knowledge_base')}]\n{c['text']}" for c in chunks]
        return "Relevant knowledge base context about " + winner + ":\n---\n" + "\n---\n".join(parts) + "\n---"
    except Exception as exc:
        logger.debug("RAG context retrieval skipped: %s", exc)
        return ""


def _rule_explanation(winner: str, cv_results: list, task: str,
                      selection_metric: str, is_imbalanced: bool,
                      feature_importance: list, n_rows: int) -> str:
    if task == "regression":
        sorted_r = sorted(cv_results, key=lambda x: x["score"])
        best_fmt = f"MAE of {sorted_r[0]['score']:.2f}"
        others   = [f"{r['algorithm']} ({r['score']:.2f})" for r in sorted_r[1:]]
    else:
        sorted_r = sorted(cv_results, key=lambda x: -x["score"])
        best_fmt = f"{selection_metric} of {sorted_r[0]['score'] * 100:.1f}%"
        others   = [f"{r['algorithm']} ({r['score'] * 100:.1f}%)" for r in sorted_r[1:]]

    text = f"{winner} achieved the best {best_fmt}"
    if others:
        text += f", outperforming {' and '.join(others)}"
    text += "."
    if is_imbalanced:
        text += " F1-macro was used as the selection criterion because your dataset has class imbalance."
    if feature_importance:
        top3 = [f["feature"] for f in feature_importance[:3]]
        text += f" The most influential features are: {', '.join(top3)}."
    return text


def _build_prompt(winner, cv_results, task, selection_metric, is_imbalanced,
                  feature_importance, n_rows, rag_context: str = ""):
    def _fmt_score(r):
        score_str = f"{r['score'] * 100:.2f}%" if task == "classification" else f"{r['score']:.4f}"
        folds = r.get("fold_scores", [])
        if folds:
            fold_str = ", ".join(f"{s * 100:.2f}%" if task == "classification" else f"{s:.4f}" for s in folds)
            variance = max(folds) - min(folds)
            var_str = f"{variance * 100:.2f}%" if task == "classification" else f"{variance:.4f}"
            return f"  {r['algorithm']}: {selection_metric} = {score_str}  [folds: {fold_str}, spread: {var_str}]"
        return f"  {r['algorithm']}: {selection_metric} = {score_str}"

    results_text = "\n".join(_fmt_score(r) for r in cv_results)
    algo_list = ", ".join(r["algorithm"] for r in cv_results)
    fi_text = "\n".join(
        f"  {i+1}. {f['feature']} ({f['importance']:.1f}%)"
        for i, f in enumerate(feature_importance[:5])
    ) if feature_importance else "  Not available"
    imbalance_note = (
        " The dataset has class imbalance, so F1-macro was used as the selection metric instead of accuracy."
        if is_imbalanced else ""
    )
    lower_is_better = task == "regression"
    rag_section = f"\n{rag_context}\n" if rag_context else ""
    return (
        f"You are an expert ML engineer explaining AutoML results to a data analyst.\n"
        f"{rag_section}\n"
        f"Dataset: {n_rows:,} rows | Task: {task}{imbalance_note}\n"
        f"Selection metric: {selection_metric} ({'lower is better' if lower_is_better else 'higher is better'})\n"
        f"Algorithms tested (5-fold cross-validation):\n{results_text}\n\n"
        f"Winner: {winner}\n\nTop features by importance:\n{fi_text}\n\n"
        f"Analyze ALL models, not just the winner. Consider fold spread (high spread = unstable model).\n\n"
        f"Return ONLY a valid JSON object with exactly these 6 fields. No markdown, no code fences, no extra text — just the raw JSON:\n\n"
        f"{{\n"
        f'  "why_won": "2-3 sentences on why {winner} outperformed the others — reference the actual score margins and fold stability.",\n'
        f'  "score_analysis": "2-3 sentences comparing ALL {len(cv_results)} models — discuss how competitive the race was, which models were close, and what the fold spread reveals about stability.",\n'
        f'  "key_drivers": "2-3 sentences on what the top features reveal about prediction drivers and any patterns.",\n'
        f'  "recommendations": ["Specific next step referencing actual scores.", "Specific next step.", "Specific next step."],\n'
        f'  "model_comparison": [\n'
        f'    {{"algorithm": "<name>", "fitness_score": <0-100 integer rating for this dataset>, "reason": "1 sentence why this score."}}\n'
        f'    // one entry per algorithm: {algo_list}\n'
        f'  ],\n'
        f'  "actionable_insights": [\n'
        f'    {{"title": "3-5 word title", "detail": "1-2 specific sentences tied to the actual numbers."}},\n'
        f'    {{"title": "3-5 word title", "detail": "1-2 specific sentences tied to the actual numbers."}},\n'
        f'    {{"title": "3-5 word title", "detail": "1-2 specific sentences tied to the actual numbers."}}\n'
        f'  ]\n'
        f"}}\n\n"
        f"Be specific to the numbers provided. No generic filler. Avoid jargon."
    )


def _llm_explanation(api_key: str, winner: str, cv_results: list, task: str,
                     selection_metric: str, is_imbalanced: bool,
                     feature_importance: list, n_rows: int, provider: str = "gemini-2.5",
                     custom_base_url: str = "", custom_model: str = ""):
    import json as _json
    import concurrent.futures as _cf

    rag_context = _rag_context_for_winner(winner)
    if rag_context:
        logger.info("RAG-enhanced /explain: retrieved KB context for winner=%s", winner)

    prompt = _build_prompt(winner, cv_results, task, selection_metric, is_imbalanced,
                           feature_importance, n_rows, rag_context=rag_context)
    raw_text = None
    try:
        if provider == "openai":
            import openai
            client = openai.OpenAI(api_key=api_key, timeout=45)
            resp = client.chat.completions.create(
                model=custom_model or "gpt-4o-mini", max_tokens=1200,
                messages=[{"role": "user", "content": prompt}],
            )
            raw_text = resp.choices[0].message.content.strip()
        elif provider in ("groq", "groq-mixtral"):
            import openai
            client = openai.OpenAI(api_key=api_key, base_url="https://api.groq.com/openai/v1", timeout=45)
            default_model = "llama-3.1-8b-instant" if provider == "groq-mixtral" else "llama-3.3-70b-versatile"
            resp = client.chat.completions.create(
                model=custom_model or default_model, max_tokens=1200,
                messages=[{"role": "user", "content": prompt}],
            )
            raw_text = resp.choices[0].message.content.strip()
        elif provider == "custom":
            import openai
            if not custom_base_url or not custom_model:
                return None
            client = openai.OpenAI(api_key=api_key or "none", base_url=custom_base_url, timeout=45)
            resp = client.chat.completions.create(
                model=custom_model, max_tokens=1200,
                messages=[{"role": "user", "content": prompt}],
            )
            raw_text = resp.choices[0].message.content.strip()
        elif provider in ("gemini-3.5", "gemini-2.5"):
            import urllib.request as _urllib
            import json as _json2
            default_model = "gemini-2.0-flash" if provider == "gemini-3.5" else "gemini-2.5-flash"
            _model = custom_model or default_model
            _url = f"https://generativelanguage.googleapis.com/v1beta/models/{_model}:generateContent?key={api_key}"
            _body = _json2.dumps({"contents": [{"parts": [{"text": prompt}]}]}).encode()
            _req = _urllib.Request(_url, data=_body, headers={"Content-Type": "application/json"})
            with _urllib.urlopen(_req, timeout=30) as _r:
                _data = _json2.loads(_r.read())
            raw_text = _data["candidates"][0]["content"]["parts"][0]["text"].strip()
        else:
            def _call_anthropic():
                import anthropic as _ant
                client = _ant.Anthropic(api_key=api_key)
                msg = client.messages.create(
                    model=custom_model or "claude-haiku-4-5-20251001",
                    max_tokens=1200,
                    messages=[{"role": "user", "content": prompt}],
                )
                return msg.content[0].text.strip()
            with _cf.ThreadPoolExecutor(max_workers=1) as _ex:
                try:
                    raw_text = _ex.submit(_call_anthropic).result(timeout=45)
                except _cf.TimeoutError:
                    print("[LLM error] Anthropic call timed out after 45s", flush=True)
                    return None
    except Exception as e:
        print(f"[LLM error] provider={provider} error={e}")
        return None
    if raw_text is None:
        return None
    import re as _re
    cleaned = raw_text.strip()
    cleaned = _re.sub(r'^```[a-z]*\n?', '', cleaned)
    cleaned = _re.sub(r'\n?```$', '', cleaned).strip()
    try:
        parsed = _json.loads(cleaned)
        return {
            "why_won":             str(parsed.get("why_won", "")),
            "score_analysis":      str(parsed.get("score_analysis", "")),
            "key_drivers":         str(parsed.get("key_drivers", "")),
            "recommendations":     parsed.get("recommendations", []),
            "model_comparison":    parsed.get("model_comparison", []),
            "actionable_insights": parsed.get("actionable_insights", []),
        }
    except (_json.JSONDecodeError, Exception):
        return {"why_won": raw_text, "score_analysis": "", "key_drivers": "", "recommendations": []}
