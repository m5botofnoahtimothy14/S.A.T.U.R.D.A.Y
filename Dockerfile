FROM python:3.11-slim

WORKDIR /app

# System deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc g++ portaudio19-dev espeak-ng ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Python deps
COPY requirements-cloud.txt .
RUN pip install --no-cache-dir -r requirements-cloud.txt

# App
COPY . .

# Create dirs
RUN mkdir -p logs data models

EXPOSE 8000

CMD ["python", "run_production.py"]
