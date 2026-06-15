FROM python:3.12-slim

WORKDIR /app

COPY agents/workspace-operator-agent/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY shared/ ./shared/
COPY agents/workspace-operator-agent/src/ ./

EXPOSE 8018

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8018"]
