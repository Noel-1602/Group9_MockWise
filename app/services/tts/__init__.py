"""TTS (Text-to-Speech) service package."""

from app.services.tts.synthesizer import synthesize_speech

__all__ = [
    "synthesize_speech",
]
