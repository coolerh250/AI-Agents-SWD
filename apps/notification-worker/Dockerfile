FROM python:3.12-slim

WORKDIR /app

COPY apps/notification-worker/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY shared/ ./shared/
COPY apps/notification-worker/src/ ./

EXPOSE 8008

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8008"]
