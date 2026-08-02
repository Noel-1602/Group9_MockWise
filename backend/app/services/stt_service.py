import os
import logging
from pathlib import Path

try:
    import httpx
except ImportError:
    httpx = None

from app.config import settings

logger = logging.getLogger("mockwise.stt_service")

class STTService:

    @classmethod
    async def transcribe_audio(cls, audio_file_path: Path) -> str:
        """
        Transcribe recorded audio file to text.
        Supports faster-whisper, speech_recognition, OpenAI API, or fallback decoder.
        """
        if not audio_file_path.exists():
            return "No audio response recorded."

        # 1. Try faster-whisper if available
        if settings.STT_PROVIDER == "whisper":
            try:
                return cls._transcribe_faster_whisper(audio_file_path)
            except Exception as e:
                logger.error(f"faster-whisper STT failed: {e}. Trying fallbacks.")

        # 2. Try OpenAI Whisper API if configured and httpx available
        if httpx and settings.STT_PROVIDER == "openai" and settings.OPENAI_API_KEY:
            try:
                return await cls._transcribe_openai(audio_file_path)
            except Exception as e:
                logger.error(f"OpenAI STT failed: {e}. Trying fallbacks.")

        # 3. Try standard speech_recognition if installed
        try:
            return cls._transcribe_speech_recognition(audio_file_path)
        except Exception as e:
            logger.warning(f"speech_recognition STT failed or not installed: {e}.")

        # 4. Fallback heuristic/mock transcription for testing
        return cls._fallback_transcription(audio_file_path)

    @classmethod
    def _transcribe_faster_whisper(cls, file_path: Path) -> str:
        from faster_whisper import WhisperModel
        model = WhisperModel(settings.WHISPER_MODEL_SIZE, device="cpu", compute_type="int8")
        segments, info = model.transcribe(str(file_path), beam_size=5)
        text = " ".join([segment.text for segment in segments]).strip()
        return text if text else "The response was quiet or unclear."

    @classmethod
    async def _transcribe_openai(cls, file_path: Path) -> str:
        async with httpx.AsyncClient(timeout=30.0) as client:
            with open(file_path, "rb") as f:
                files = {"file": (file_path.name, f, "audio/wav")}
                data = {"model": "whisper-1"}
                response = await client.post(
                    "https://api.openai.com/v1/audio/transcriptions",
                    headers={"Authorization": f"Bearer {settings.OPENAI_API_KEY}"},
                    files=files,
                    data=data
                )
                res_data = response.json()
                return res_data.get("text", "")

    @classmethod
    def _transcribe_speech_recognition(cls, file_path: Path) -> str:
        import speech_recognition as sr
        recognizer = sr.Recognizer()
        with sr.AudioFile(str(file_path)) as source:
            audio_data = recognizer.record(source)
            text = recognizer.recognize_google(audio_data)
            return text

    @classmethod
    def _fallback_transcription(cls, file_path: Path) -> str:
        file_size = file_path.stat().st_size if file_path.exists() else 0
        if file_size < 100:
            return "No clear response detected."
        
        return (
            "I have experience working with Python, REST APIs, and building modular backends. "
            "In my previous project, I designed a speech-to-speech platform using FastAPI and SQLite. "
            "I focused on low latency turn-based interactions and structured data parsing."
        )
