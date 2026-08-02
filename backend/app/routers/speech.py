import uuid
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, status
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.models.session import Question
from app.services.stt_service import STTService
from app.services.tts_service import TTSService
from app.config import settings

router = APIRouter(prefix="/speech", tags=["Speech Pipeline (STT & TTS)"])

@router.get("/questions/{question_id}/audio")
async def get_question_audio(question_id: str, db: AsyncSession = Depends(get_db)):
    """
    Stream TTS audio file for a given question.
    Synthesizes audio on-demand if not already cached on disk.
    """
    stmt = select(Question).where(Question.id == question_id)
    res = await db.execute(stmt)
    question = res.scalar_one_or_none()

    if not question:
        raise HTTPException(status_code=404, detail="Question not found.")

    audio_path = Path(question.tts_audio_path) if question.tts_audio_path else None
    
    if not audio_path or not audio_path.exists():
        # Synthesize audio on demand
        target_path = settings.AUDIO_DIR / f"q_{question_id}.wav"
        audio_path = await TTSService.text_to_speech(question.question_text, target_path)
        question.tts_audio_path = str(audio_path)
        await db.commit()

    media_type = "audio/wav" if audio_path.suffix == ".wav" else "audio/mpeg"
    return FileResponse(path=audio_path, media_type=media_type, filename=audio_path.name)


@router.post("/stt")
async def transcribe_audio_endpoint(audio_file: UploadFile = File(...)):
    """
    Standalone Speech-to-Text endpoint. Accepts an audio file and returns text transcript.
    """
    file_id = str(uuid.uuid4())
    ext = Path(audio_file.filename).suffix or ".wav"
    saved_path = settings.AUDIO_DIR / f"stt_{file_id}{ext}"
    
    contents = await audio_file.read()
    with open(saved_path, "wb") as f:
        f.write(contents)

    transcript = await STTService.transcribe_audio(saved_path)
    return {"transcript": transcript, "audio_file": audio_file.filename}


@router.post("/tts")
async def synthesize_speech_endpoint(text: str = Form(...)):
    """
    Standalone Text-to-Speech endpoint. Accepts text and returns audio file.
    """
    file_id = str(uuid.uuid4())
    output_path = settings.AUDIO_DIR / f"tts_{file_id}.wav"
    
    audio_path = await TTSService.text_to_speech(text, output_path)
    return FileResponse(path=audio_path, media_type="audio/wav", filename=audio_path.name)
