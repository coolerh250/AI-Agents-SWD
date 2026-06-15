FROM python:3.12-slim

WORKDIR /app

COPY agents/mini-delivery-pilot-agent/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY shared/ ./shared/
COPY agents/mini-delivery-pilot-agent/src/ ./

EXPOSE 8019

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8019"]
