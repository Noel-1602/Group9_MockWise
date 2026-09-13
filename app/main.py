from fastapi import FastAPI
from app.database import Base, engine
from app import models
from app.routers import questions, sessions

Base.metadata.create_all(bind=engine)

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

