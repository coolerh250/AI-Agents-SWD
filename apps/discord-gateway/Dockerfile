FROM python:3.12-slim

WORKDIR /app

COPY apps/discord-gateway/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY shared/ ./shared/
COPY apps/discord-gateway/src/ ./

EXPOSE 8007

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8007"]
