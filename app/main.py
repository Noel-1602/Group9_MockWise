from fastapi import FastAPI
from app.routers import sessions

app = FastAPI(
    title="MockWise API",
    description="Speech-to-Speech AI Mock Interview Platform",
    version="0.1.0",
)

app.include_router(sessions.router)


@app.get("/health")
def health_check():
    return {"status": "ok"}

