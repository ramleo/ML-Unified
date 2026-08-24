# Session — 2026-05-31 ML-Pipeline-Auto Build

## Context
Building a new unified ML pipeline template repo called ML-Pipeline-Auto, based on builds_bootstrap with all known bugs fixed and new improvements.

## Status at session start
- builds_bootstrap is at v2.0.1 (Docker, all three boosters, 19 domain themes, sliders, comparison table, dark/light toggle)
- All today's bootstrap.py bug fixes are already present in builds_bootstrap
- ML-Pipeline-Auto directory created at /Users/wrks/Downloads/Claude-documentation/Projects/ML-Pipeline-Auto/
- Fresh git init done (no history from builds_bootstrap)

## Todo list
1. [completed] Copy builds_bootstrap to ML-Pipeline-Auto locally
2. [in_progress] Fix all bugs in bootstrap.py (shell wizard + Python CLI sections) — ALREADY DONE in builds_bootstrap, so bootstrap.py in ML-Pipeline-Auto already has all fixes
3. [pending] Fix bugs in start.sh and init.py
4. [pending] Improve standalone auto_pipeline.py (Pydantic aliases, feature ranges via web search, input validation, categorical dropdowns)
5. [pending] Re-embed improved auto_pipeline.py into bootstrap.py FILES dict
6. [pending] Update README.md with new repo URL and roadmap
7. [pending] Create GitHub repo ML-Pipeline-Auto (public) and push everything in one commit

## Key decisions made
- Target column: ALWAYS required, no auto-detect fallback
- Feature ranges: web search (DuckDuckGo API) first, fallback to dataset p5-p95 percentiles
- Categorical dropdowns: unique values from dataset
- ID columns: NOT included (no injection either)
- Pydantic fields with spaces: safe_name + Field(alias="Original Name") + model_dump(by_alias=True)
- Docker: included (Dockerfile.bootstrap + run.sh already in builds_bootstrap)
- CLAUDE.md files: unchanged from builds_bootstrap
- builds_bootstrap: left untouched
- GitHub repo: ML-Pipeline-Auto, public, ramleo account

## Changes made to auto_pipeline.py so far
1. Feature ranges section (around line 619): replaced data min/max with web search via DuckDuckGo API + p5-p95 fallback
2. Added _cat_uniques dict collection after feature ranges

## Next: Fix _generate_app function
Location: around line 2085 in auto_pipeline.py
Changes needed:
- Change `from pydantic import BaseModel` → `from pydantic import BaseModel, Field`
- Add `model_config = {"populate_by_name": True}` to InputData
- Use safe_name + Field(alias) for fields with spaces
- Remove ID column detection and _ID_COLS injection entirely
- Change data.dict() → data.model_dump(by_alias=True)
- Change [d.dict() for d in data] → [d.model_dump(by_alias=True) for d in data]

## Next: Fix _generate_frontend function
Location: around line 1232 in auto_pipeline.py
Changes needed:
- Pass cat_uniques to function signature
- Replace <input type="text"> for categorical → <select> with <option> from cat_uniques
- Add inline validation JS: red border + error message on blur for out-of-range numeric values
- Disable predict button until all required fields valid

## Next: Update call sites
Location: around line 2338-2339
- Pass cat_uniques to _generate_app and _generate_frontend

## Key file locations
- ML-Pipeline-Auto: /Users/wrks/Downloads/Claude-documentation/Projects/ML-Pipeline-Auto/
- auto_pipeline.py: /Users/wrks/Downloads/Claude-documentation/Projects/ML-Pipeline-Auto/auto_pipeline.py
- bootstrap.py: /Users/wrks/Downloads/Claude-documentation/Projects/ML-Pipeline-Auto/bootstrap.py
- builds_bootstrap (reference): /Users/wrks/Downloads/Claude-documentation/Projects/builds_bootstrap/
- spec doc: /Users/wrks/Downloads/Bootstrap_Template/bootstrap_template_spec.md
- portfolio guide: /Users/wrks/Downloads/Claude-documentation/Projects/docs/ML_Portfolio_Guide.md

## GitHub repos
- New: https://github.com/ramleo/ML-Pipeline-Auto (to be created)
- Reference: https://github.com/ramleo/builds_bootstrap
- Live projects: ML-Insurance_with-Frontend, ML-Iris_with-Frontend, ML-Titanic_with-Frontend, ML-Diabetes_with-Frontend

## 20-Point Plan status
- Items 1-6: Done (inherited from builds_bootstrap)
- Items 7-17: Portfolio website (out of scope, separate decision needed)
- Item 18: Categorical dropdowns — being implemented now
- Item 19: Playwright UI tests — stub file tests/test_ui.py with TODO
- Item 20: CI/CD — .github/workflows/ci.yml template included

## Pending items (outside 20-point plan)
- Domain-informed feature_ranges.json — being implemented (web search)
- Inline field validation — being implemented
- Mobile responsive layout — TODO in index.html
