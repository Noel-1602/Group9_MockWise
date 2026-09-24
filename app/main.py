from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.database import Base, engine
from app import models
from app.routers import questions, sessions

load_dotenv()

Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="MockWise API",
    description="Speech-to-Speech AI Mock Interview Platform",
    version="0.1.0",
)

origins = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(sessions.router)
app.include_router(questions.router)


@app.get("/health")
def health_check():
    return {"status": "ok"}

