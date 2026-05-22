FROM python:3.12-slim

WORKDIR /app

COPY agents/devops-agent/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY shared/ ./shared/
COPY agents/devops-agent/src/ ./

EXPOSE 8014

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8014"]
