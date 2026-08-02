from app.routers.resume import router as resume_router
from app.routers.sessions import router as sessions_router
from app.routers.speech import router as speech_router
from app.routers.answer import router as answer_router
from app.routers.report import router as report_router

__all__ = [
    "resume_router",
    "sessions_router",
    "speech_router",
    "answer_router",
    "report_router"
]
