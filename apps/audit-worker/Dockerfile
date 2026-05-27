FROM python:3.12-slim

WORKDIR /app

COPY apps/audit-worker/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY shared/ ./shared/
COPY apps/audit-worker/src/ ./

EXPOSE 8006

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8006"]
