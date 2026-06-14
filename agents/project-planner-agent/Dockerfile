FROM python:3.12-slim

WORKDIR /app

COPY agents/project-planner-agent/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY shared/ ./shared/
COPY agents/project-planner-agent/src/ ./

EXPOSE 8016

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8016"]
