FROM python:3.11-slim

WORKDIR /app

# libgomp1 is required by LightGBM and XGBoost for OpenMP parallelism.
# ffmpeg is required by opencv-python-headless to decode most video codecs
# (MP4/MOV/WEBM/etc.) for the Multimodal RAG video-upload key-frame path.
RUN apt-get update \
    && apt-get install -y --no-install-recommends libgomp1 ffmpeg \
    && rm -rf /var/lib/apt/lists/*

RUN adduser --disabled-password --gecos "" appuser

# Layer 1: heavy packages (torch, transformers, ML libs) — cached unless requirements-base.txt changes
COPY requirements-base.txt .
RUN pip install --no-cache-dir -r requirements-base.txt \
    && python -m spacy download en_core_web_sm

# groundingdino-py + supervision (mm_rotoscope.py) are installed with --no-deps:
# both declare an unpinned, non-headless opencv-python dependency that would
# collide with opencv-python-headless (installed below in requirements.txt) and
# typically fails to import in this slim image at all (missing libGL.so.1).
# Their actual other deps are already satisfied by requirements-base.txt above.
RUN pip install --no-cache-dir --no-deps "groundingdino-py==0.4.0" "supervision==0.6.0"

# facenet-pytorch (mm_face_cloak.py) is also installed with --no-deps: it pins
# torch<2.3.0, which conflicts with sam2's torch>=2.5.1 floor above. Its other
# actual runtime deps (numpy, Pillow, requests, tqdm) are already satisfied by
# requirements-base.txt/requirements.txt; only torch/torchvision are left to
# resolve freely so they satisfy sam2 instead.
RUN pip install --no-cache-dir --no-deps "facenet-pytorch==2.6.0"

# Layer 2: lightweight / frequently-changing packages — only this layer rebuilds when adding new tools
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py .
COPY routers/ routers/
COPY shared/ shared/
COPY frontend/ frontend/
COPY --chown=appuser:appuser models/ models/
COPY --chown=appuser:appuser schemas/ schemas/
COPY --chown=appuser:appuser data/ data/

# /home/appuser is always writable; /data persistent volume may not exist on all Spaces
ENV HF_HOME=/home/appuser/.cache/huggingface

USER appuser
EXPOSE ${PORT:-8000}
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
  CMD python3 -c "import urllib.request; urllib.request.urlopen('http://localhost:${PORT:-8000}/health')" || exit 1

CMD ["sh", "-c", "uvicorn app:app --host 0.0.0.0 --port ${PORT:-8000}"]
