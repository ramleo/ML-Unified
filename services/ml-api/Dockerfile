FROM python:3.11-slim

WORKDIR /app

# libgomp1 is required by LightGBM and XGBoost for OpenMP parallelism
RUN apt-get update \
    && apt-get install -y --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py .
COPY routers/ routers/
COPY shared/ shared/
COPY frontend/ frontend/
RUN mkdir -p models
COPY schemas/ schemas/

CMD ["sh", "-c", "uvicorn app:app --host 0.0.0.0 --port ${PORT:-8000}"]
