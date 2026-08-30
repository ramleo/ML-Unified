"""
Test: which LLMs reliably extract `invoice_items` from the test invoice PDF.
Hits the live HF Space API with provider= forced per run.
"""
import json
import sys
import time

import httpx

PDF_PATH = "test_invoice.pdf"
API_BASE = "https://wram1708-ml-unified.hf.space"
N_RUNS = 3

PROVIDERS = ["groq", "gemini", "cohere"]
PROVIDER_LABELS = {
    "groq":   "Groq llama-3.3-70b-versatile",
    "gemini": "Gemini 2.0 Flash",
    "cohere": "Cohere command-r-plus",
}


def parse_sse(raw: str) -> list[dict]:
    events = []
    for line in raw.splitlines():
        line = line.strip()
        if line.startswith("data:"):
            try:
                events.append(json.loads(line[5:].strip()))
            except json.JSONDecodeError:
                pass
    return events


_ITEM_FIELD_NAMES = {"invoice_items", "line_items", "items", "invoice_lines",
                     "line_item", "item", "products", "services"}

def got_invoice_items(events: list[dict]) -> bool:
    null_vals = {"null", "none", "n/a", "na", "not found", "not available", "", "-"}
    for ev in events:
        if "field" in ev:
            f = ev["field"]
            name = str(f.get("name", "")).strip().lower()
            val = str(f.get("value", "")).strip().lower()
            if name in _ITEM_FIELD_NAMES or "item" in name:
                if val not in null_vals:
                    return True
    return False


def run_once(provider: str, run_num: int) -> tuple[str, list[dict]]:
    try:
        with open(PDF_PATH, "rb") as f:
            pdf_bytes = f.read()
        with httpx.Client(timeout=120) as client:
            resp = client.post(
                f"{API_BASE}/document/analyze",
                files={"file": ("test_invoice.pdf", pdf_bytes, "application/pdf")},
                data={"doc_type": "invoice", "provider": provider},
            )
            resp.raise_for_status()
            events = parse_sse(resp.text)
        status = "YES" if got_invoice_items(events) else "NO"
        field_names = [ev["field"]["name"] for ev in events if "field" in ev]
        errors = [ev.get("error") for ev in events if "error" in ev]
        item_field = next((ev["field"]["name"] for ev in events
                           if "field" in ev and ("item" in ev["field"]["name"].lower())), None)
        extra = f"  item_field={item_field}" if item_field else (f"  error={errors[0]}" if errors else "  (no fields)" if not field_names else "")
        print(f"  [{PROVIDER_LABELS[provider]}] run {run_num}/{N_RUNS}: {status}  fields={field_names}{extra}")
        return status, events
    except Exception as e:
        print(f"  [{PROVIDER_LABELS[provider]}] run {run_num}/{N_RUNS}: ERROR  {e}")
        return "ERROR", []


if __name__ == "__main__":
    print(f"API: {API_BASE}")
    print(f"PDF: {PDF_PATH}")
    print(f"Runs per provider: {N_RUNS}\n")

    results: list[dict] = []
    for provider in PROVIDERS:
        statuses = []
        for run in range(1, N_RUNS + 1):
            status, _ = run_once(provider, run)
            statuses.append(status)
            if run < N_RUNS:
                time.sleep(2)
        hits = statuses.count("YES")
        results.append({
            "provider": PROVIDER_LABELS[provider],
            "runs": statuses,
            "hits": hits,
            "reliability": f"{hits}/{N_RUNS}",
        })
        print()

    # ── Table ─────────────────────────────────────────────────────────────────
    print("=" * 70)
    print(f"{'Provider':<38} {'Run 1':<8} {'Run 2':<8} {'Run 3':<8} {'Score'}")
    print("-" * 70)
    for r in results:
        runs = r["runs"] + ["—"] * (N_RUNS - len(r["runs"]))
        score_color = r["hits"] == N_RUNS and "  ✓ all" or (r["hits"] > 0 and "  ~ partial" or "  ✗ none")
        print(f"{r['provider']:<38} {runs[0]:<8} {runs[1]:<8} {runs[2]:<8} {r['reliability']}{score_color}")
    print("=" * 70)
    print("\nYES = invoice_items extracted with non-null value")
    print("NO  = field missing or returned null/empty")
    print("ERR = API error / timeout")
