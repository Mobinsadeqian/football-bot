FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY bot.py .
COPY .env.example .

# For PaaS health checks: optional HTTP server on PORT
# subscribers.json will be created at runtime (use volume if you want persistence)
RUN mkdir -p /data

ENV SUBSCRIBERS_FILE=/app/subscribers.json
ENV PYTHONUNBUFFERED=1

CMD ["python", "bot.py"]
