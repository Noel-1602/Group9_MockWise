from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.database import init_db
from app.routers import (
    resume_router,
    sessions_router,
    speech_router,
    answer_router,
    report_router
)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: initialize SQLite database tables
    await init_db()
    yield

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="Backend API for MockWise - AI-powered speech-to-speech mock interview platform",
    lifespan=lifespan
)

# Configure CORS for Next.js frontend integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins during local dev & testing
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register API Routers under settings.API_PREFIX (/api)
app.include_router(resume_router, prefix=settings.API_PREFIX)
app.include_router(sessions_router, prefix=settings.API_PREFIX)
app.include_router(speech_router, prefix=settings.API_PREFIX)
app.include_router(answer_router, prefix=settings.API_PREFIX)
app.include_router(report_router, prefix=settings.API_PREFIX)

# Health Check & System Status Endpoint
@app.get("/api/health", tags=["Health & Status"])
async def health_check():
    return {
        "status": "healthy",
        "service": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "providers": {
            "llm": settings.LLM_PROVIDER,
            "stt": settings.STT_PROVIDER,
            "tts": settings.TTS_PROVIDER
        },
        "directories": {
            "storage": str(settings.STORAGE_DIR),
            "uploads": str(settings.UPLOADS_DIR),
            "audio": str(settings.AUDIO_DIR),
            "reports": str(settings.REPORTS_DIR)
        }
    }

@app.get("/")
async def root():
    return {
        "message": "Welcome to MockWise API Service",
        "docs_url": "/docs",
        "health_check": "/api/health"
    }
