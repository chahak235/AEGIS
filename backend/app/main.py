from fastapi import FastAPI

app = FastAPI(title="AEGIS", version="0.1.0")


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/")
def home():
    return {"message": "Welcome to AEGIS", "docs": "/docs"}