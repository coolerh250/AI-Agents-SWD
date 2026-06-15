FROM python:3.12-slim

WORKDIR /app

COPY agents/delivery-package-agent/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY shared/ ./shared/
COPY agents/delivery-package-agent/src/ ./

EXPOSE 8020

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8020"]
