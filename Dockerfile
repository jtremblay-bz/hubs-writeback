FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY deal_update/ deal_update/
# Cloud Run sets PORT. State lives in Postgres (DATABASE_URL), never on this disk.
ENV HUBSPOT_PROD_PORTAL_ID=44505231
CMD exec uvicorn deal_update.service.app:app --host 0.0.0.0 --port ${PORT:-8080} --workers 1
