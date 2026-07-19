FROM python:3.11-slim

WORKDIR /srv

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ ./app/

ENV PORT=8000
EXPOSE 8000

# single worker: conversions are CPU/memory heavy; free tier has ~512MB.
# uvicorn's threadpool queues concurrent requests instead of forking workers.
CMD uvicorn app.main:app --host 0.0.0.0 --port ${PORT} --timeout-keep-alive 130
