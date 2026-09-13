from fastapi import FastAPI
from app.routers import questions, sessions

app = FastAPI(
    title="MockWise API",
    description="Speech-to-Speech AI Mock Interview Platform",
    version="0.1.0",
)

app.include_router(sessions.router)
app.include_router(questions.router)


@app.get("/health")
def health_check():
    return {"status": "ok"}

