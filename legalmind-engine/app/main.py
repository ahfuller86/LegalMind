from fastapi import FastAPI
from app.api.routes import router as api_router

app = FastAPI(title="LegalMind Engine", version="3.0")

app.include_router(api_router, prefix="/api")

@app.get("/")
def read_root():
    return {"message": "LegalMind Engine v3.0 is running"}
