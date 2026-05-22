FROM python:3.12-slim

WORKDIR /app

COPY agents/intake-agent/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY shared/ ./shared/
COPY agents/intake-agent/src/ ./

EXPOSE 8010

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8010"]
