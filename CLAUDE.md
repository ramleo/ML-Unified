## Rules — follow always, no exceptions

1. **"first tell" = stop** — if the user says "first tell", "pehle bata", or any variant: only answer in text, no code, no agents, no edits. Wait for explicit "proceed" or "haan kar" before doing anything.

2. **Subagents — be deliberate, not default** — each subagent re-derives context from scratch and burns its own usage. Only spawn one when the work is genuinely independent/parallelizable (e.g. 4+ unrelated files that don't depend on each other's output) or so large it would blow the main context window. For 1-2 files, or anything under ~300 lines, do it directly — no agent. Never spawn multiple agents to write near-identical content (e.g. several similar doc/KB files) — write them yourself in sequence, or use one agent in a loop. Default subagent model to a cheaper tier (e.g. Haiku) unless the task needs strong reasoning.

3. **No file over 400 lines** — before touching any file, check its line count (`wc -l`). If it is over 350 lines, modularize it first via a subagent, then add the feature.

4. **HF Space upload is mandatory after every backend commit** — after any `git push origin main` that includes backend changes (`services/ml-api/**`), immediately upload all changed `.py` files to HF Space using `api.upload_file()` with token from `git remote get-url hf`. Repo: `wram1708/ml-unified`, `repo_type="space"`, strip `services/ml-api/` prefix from path. Never close out backend work without this step.
