FROM python:3.12-slim

WORKDIR /app

COPY apps/retry-scheduler/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY shared/ ./shared/
COPY apps/retry-scheduler/src/ ./

EXPOSE 8015

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8015"]
