FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# vision_app / vision_shared, not app / shared. ml-api owns those two names and
# the services are developed in one checkout, so identical top-level names mean
# the second one imported in any shared interpreter silently wins. It is only a
# rename inside this container, where nothing else competes.
COPY vision_app.py .
COPY vision_shared/ vision_shared/

CMD ["sh", "-c", "uvicorn vision_app:app --host 0.0.0.0 --port ${PORT:-8000}"]
