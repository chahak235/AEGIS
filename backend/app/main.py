from fastapi import FastAPI

from app.api import health
from app.api.v1 import events

app = FastAPI(title="AEGIS", version="0.1.0")

app.include_router(health.router)
app.include_router(events.router)


@app.get("/")
def home():
    return {"message": "Welcome to AEGIS", "docs": "/docs"}
