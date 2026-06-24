"""Optuna-specific AI explanation endpoint."""
import json
import urllib.request as _ur
from fastapi import APIRouter, Form

router = APIRouter()


def _build_optuna_prompt(winner, task, n_trials, best_score, optuna_params,
                         param_importance, feature_importance, winner_metrics):
    """Build a prompt for explaining Optuna hyperparameter tuning results."""
    params_text = "\n".join(f"  {k}: {v}" for k, v in optuna_params.items()) if optuna_params else "  None available"
    imp_sorted = sorted(param_importance.items(), key=lambda x: -x[1]) if param_importance else []
    imp_text = "\n".join(f"  {k}: {v*100:.1f}%" for k, v in imp_sorted) if imp_sorted else "  None available"
    metrics_text = "\n".join(f"  {k}: {v}" for k, v in winner_metrics.items()) if winner_metrics else "  None available"
    top_features = [f["feature"] for f in feature_importance[:5]] if feature_importance else []
    feat_str = ", ".join(top_features) if top_features else "Not available"
    return (
        f"You are an ML expert explaining Optuna hyperparameter tuning results to a data scientist.\n\n"
        f"Task: {task} | Winner model: {winner} | Optuna trials: {n_trials} | Best CV score: {best_score:.4f}\n\n"
        f"Best hyperparameters found:\n{params_text}\n\n"
        f"Hyperparameter importance (fANOVA analysis — higher = more impact on score):\n{imp_text}\n\n"
        f"Final model metrics:\n{metrics_text}\n\n"
        f"Top features by importance: {feat_str}\n\n"
        f"Explain in plain English (3-5 paragraphs):\n"
        f"1. What the most important hyperparameters mean and why they matter for this dataset\n"
        f"2. What the best parameter values tell us about the data structure\n"
        f"3. What the CV score means in practice and how confident we should be\n"
        f"4. 2-3 concrete next steps to further improve performance\n\n"
        f"Be specific to the actual numbers provided. No generic filler. Use simple language."
    )


def _llm_explanation_raw(api_key: str, prompt: str, provider: str = "gemini-2.5"):
    """Call LLM with a raw prompt string. Returns plain text or None on failure."""
    try:
        if provider in ("gemini-2.5", "gemini-3.5-flash"):
            _model = "gemini-2.5-flash" if provider == "gemini-2.5" else "gemini-3.5-flash"
            _url = (
                f"https://generativelanguage.googleapis.com/v1beta/models/"
                f"{_model}:generateContent?key={api_key}"
            )
            _body = json.dumps({"contents": [{"parts": [{"text": prompt}]}]}).encode()
            _req = _ur.Request(_url, data=_body, headers={"Content-Type": "application/json"})
            with _ur.urlopen(_req, timeout=30) as _r:
                _data = json.loads(_r.read())
            return _data["candidates"][0]["content"]["parts"][0]["text"].strip()
        if provider == "openai":
            import openai  # noqa: PLC0415
            client = openai.OpenAI(api_key=api_key)
            resp = client.chat.completions.create(
                model="gpt-4o-mini", max_tokens=900,
                messages=[{"role": "user", "content": prompt}],
            )
            return resp.choices[0].message.content.strip()
        if provider == "cohere":
            _url = "https://api.cohere.com/v2/chat"
            _body = json.dumps({
                "model": "command-a-03-2025",
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 900,
            }).encode()
            _req = _ur.Request(_url, data=_body, headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}",
            })
            with _ur.urlopen(_req, timeout=30) as _r:
                _data = json.loads(_r.read())
            return _data["message"]["content"][0]["text"].strip()
        if provider == "groq":
            import openai  # noqa: PLC0415
            client = openai.OpenAI(api_key=api_key, base_url="https://api.groq.com/openai/v1")
            resp = client.chat.completions.create(
                model="llama-3.3-70b-versatile", max_tokens=900,
                messages=[{"role": "user", "content": prompt}],
            )
            return resp.choices[0].message.content.strip()
    except Exception as _e:
        print(f"[optuna-explain LLM error] provider={provider} error={_e}", flush=True)
    return None


@router.post("/optuna-explain")
async def optuna_explain(
    winner: str = Form(...),
    task: str = Form("classification"),
    n_trials: int = Form(0),
    best_score: float = Form(0.0),
    optuna_params_json: str = Form("{}"),
    param_importance_json: str = Form("{}"),
    feature_importance_json: str = Form("[]"),
    winner_metrics_json: str = Form("{}"),
    api_key: str = Form(...),
    provider: str = Form("gemini-2.5"),
):
    try:
        optuna_params = json.loads(optuna_params_json or "{}")
    except Exception:
        optuna_params = {}
    try:
        param_importance = json.loads(param_importance_json or "{}")
    except Exception:
        param_importance = {}
    try:
        feature_importance = json.loads(feature_importance_json or "[]")
    except Exception:
        feature_importance = []
    try:
        winner_metrics = json.loads(winner_metrics_json or "{}")
    except Exception:
        winner_metrics = {}

    prompt = _build_optuna_prompt(
        winner=winner, task=task, n_trials=n_trials, best_score=best_score,
        optuna_params=optuna_params, param_importance=param_importance,
        feature_importance=feature_importance, winner_metrics=winner_metrics,
    )
    explanation = _llm_explanation_raw(api_key=api_key, prompt=prompt, provider=provider)
    return {"explanation": explanation or "Could not generate explanation — check your API key and try again."}
