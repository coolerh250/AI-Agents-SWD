FROM python:3.12-slim

WORKDIR /app

COPY agents/requirement-agent/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY shared/ ./shared/
COPY agents/requirement-agent/src/ ./

EXPOSE 8011

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8011"]
