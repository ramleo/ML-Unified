# ML-Unified

The backend behind [ml-portfolio-rho.vercel.app](https://ml-portfolio-rho.vercel.app) —
three FastAPI services deployed to Hugging Face Spaces, serving around fifty
machine-learning tools from one codebase.

| Service | What it does |
|---|---|
| `services/ml-api` | The main API: tabular AutoML, EDA, SHAP and explainability, multimodal RAG, and the computer-vision and document-forensics tools |
| `services/ml-sql` | Text-to-SQL |
| `services/ml-vision` | Image and video models kept apart from the main API for memory reasons |

`services/ml-api/frontend/` is the plain-HTML interface the Space serves
directly. The richer Next.js interface most people use is a separate project:
[ramleo/ML-Portfolio](https://github.com/ramleo/ML-Portfolio).

## Running it

```bash
cd services/ml-api
pip install -r requirements.txt
python -m spacy download en_core_web_sm
uvicorn app:app --reload
```

Provider API keys are read from the environment and every LLM feature degrades
to a non-LLM path when a key is absent, so the service starts and most of it
works with no keys at all.

## Licence

Copyright (C) 2026 Ramakrishnasai Wuppalapati

This program is free software: you can redistribute it and/or modify it under
the terms of the GNU Affero General Public License as published by the Free
Software Foundation, either version 3 of the License, or (at your option) any
later version.

This program is distributed in the hope that it will be useful, but WITHOUT ANY
WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A
PARTICULAR PURPOSE. See the GNU Affero General Public License for more details.

You should have received a copy of the GNU Affero General Public License along
with this program. If not, see <https://www.gnu.org/licenses/>.

The full text is in [LICENSE](LICENSE).

**Why AGPL and not something permissive.** Three of the object detectors
bundled here are Ultralytics-architecture YOLO models, and Ultralytics treats
exported weights as AGPL-3.0 derivatives regardless of the runtime serving
them. Rather than argue that reading, this project adopts the licence and
complies with it. [THIRD_PARTY.md](THIRD_PARTY.md) has every model's
provenance, the licence each upstream claims, and the search for permissive
replacements that found none.

**Source for the running service.** AGPL-3.0 §13 requires that people using
this over a network can get its source. This repository is that source, and the
live application links here from its own interface.

The frontend repository is MIT-licensed and separate; this licence does not
reach it.
