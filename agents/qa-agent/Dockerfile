FROM python:3.12-slim

WORKDIR /app

COPY agents/qa-agent/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY shared/ ./shared/
COPY agents/qa-agent/src/ ./

EXPOSE 8013

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8013"]
