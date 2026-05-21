from fastapi import FastAPI

app = FastAPI(title="orchestrator")


@app.get("/health")
def health():
    return {"service": "orchestrator", "status": "ok"}
