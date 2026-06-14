FROM python:3.12-slim

WORKDIR /app

COPY agents/design-review-agent/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY shared/ ./shared/
COPY agents/design-review-agent/src/ ./

EXPOSE 8017

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8017"]
