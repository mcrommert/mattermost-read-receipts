FROM python:3.12-slim

# DejaVu fonts give the letter emoji a clean bold glyph.
RUN apt-get update \
    && apt-get install -y --no-install-recommends fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app

# config.yml is provided at runtime (bind mount or baked into your own image).
CMD ["python", "-u", "-m", "app.main"]
