FROM python:3.11-slim

WORKDIR /app

# libgomp1 is required by LightGBM and XGBoost for OpenMP parallelism.
# ffmpeg is required by opencv-python-headless to decode most video codecs
# (MP4/MOV/WEBM/etc.) for the Multimodal RAG video-upload key-frame path.
# clamav + clamav-daemon + clamav-freshclam: the full antivirus engine for the
# upload deep-scan gate (security/clamav_scan.py). Its signature DB is baked in
# at build time below.
RUN DEBIAN_FRONTEND=noninteractive apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends libgomp1 ffmpeg clamav clamav-daemon clamav-freshclam \
    && rm -rf /var/lib/apt/lists/*

RUN adduser --disabled-password --gecos "" appuser

# --- ClamAV: bake the signature DB into the image, configure the daemon --------
# Fresh Debian clamav configs ship with an "Example" line that makes freshclam
# and clamd refuse to start; strip it. Then download the virus DB at build time
# (fail-soft: if the CDN rate-limits the build, clamd just has no/partial DB and
# the gate falls back to YARA — clamav_scan.py fails open, so build + app still
# succeed). clamd is configured for local TCP (so the unprivileged appuser can
# reach it without socket-permission juggling) with 60MB limits so it can scan
# the 50MB document upload (security/body_size.py). The DB + config are handed to
# appuser since the app process runs unprivileged.
RUN sed -i '/^Example/d' /etc/clamav/freshclam.conf 2>/dev/null || true; \
    freshclam --quiet || true
RUN printf '%s\n' \
      'TCPSocket 3310' \
      'TCPAddr 127.0.0.1' \
      'StreamMaxLength 60M' \
      'MaxFileSize 60M' \
      'MaxScanSize 200M' \
      'Foreground false' \
      'DatabaseDirectory /var/lib/clamav' \
      'PidFile /tmp/clamd.pid' \
      'TemporaryDirectory /tmp' \
      'LogFile /tmp/clamd.log' \
      > /etc/clamav/clamd.conf \
    && chown -R appuser:appuser /var/lib/clamav /etc/clamav

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
#
# It also declares numpy<2.0.0, which this image knowingly violates since the
# move to numpy 2.4.6, so pip prints it among its resolver warnings. That bound
# is metadata rather than a binary one: facenet-pytorch is pure Python over
# torch and links nothing against numpy's C API. Checked rather than assumed —
# InceptionResnetV1 imports, instantiates and runs a forward pass to a 512-dim
# embedding under numpy 2.4.6. mm_face_cloak.py also catches a load failure and
# disables the feature, so the worst case is a missing tool, not a broken app.
RUN pip install --no-cache-dir --no-deps "facenet-pytorch==2.6.0"

# Layer 2: lightweight / frequently-changing packages — only this layer rebuilds when adding new tools
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py .
COPY mcp_server.py .
COPY mcp_ext/ mcp_ext/
COPY routers/ routers/
COPY security/ security/
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

# Start clamd in the background (it loads its ~1GB DB over 20-30s; until it is
# ready the upload gate falls open to YARA — clamav_scan.py handles the wait),
# then run the API in the foreground.
CMD ["sh", "-c", "clamd & uvicorn app:app --host 0.0.0.0 --port ${PORT:-8000}"]
