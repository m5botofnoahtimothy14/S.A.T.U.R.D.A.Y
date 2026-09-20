FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
VOLUME ["/app/vault", "/app/blackbox", "/app/staging", "/app/config"]
ENV PYTHONUNBUFFERED=1
CMD ["python", "main.py"]
