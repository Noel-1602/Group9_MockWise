"""STT (Speech-to-Text) service package."""

from app.services.stt.transcriber import transcribe_audio

__all__ = [
    "transcribe_audio",
]
