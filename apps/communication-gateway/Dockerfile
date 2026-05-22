FROM python:3.12-slim

WORKDIR /app

COPY apps/communication-gateway/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY shared/ ./shared/
COPY apps/communication-gateway/src/ ./

EXPOSE 8004

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8004"]
