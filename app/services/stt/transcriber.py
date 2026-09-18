"""STT (Speech-to-Text) transcription service orchestrator.

Provides speech transcription backends:
- mock: Deterministic mock transcriber returning a placeholder string.
- faster_whisper: Local Whisper model transcription via faster-whisper (to be implemented).
"""

import logging
from typing import Literal

logger = logging.getLogger(__name__)

MOCK_TRANSCRIPTION: str = "This is a mock transcription of the candidate's answer."


def _mock_transcribe(audio_bytes: bytes) -> str:
    """Return a deterministic mock transcription string regardless of audio content.

    Parameters
    ----------
    audio_bytes:
        Raw audio content in bytes.

    Returns
    -------
    str
        Fixed mock transcription string.
    """
    return MOCK_TRANSCRIPTION


def transcribe_audio(
    audio_bytes: bytes,
    backend: Literal["mock", "faster_whisper"] = "mock",
) -> str:
    """Transcribe speech audio into text using the selected backend.

    Parameters
    ----------
    audio_bytes:
        Raw binary audio content to transcribe.
    backend:
        Transcription backend strategy:
        * "mock"           - Deterministic mock transcriber returning fixed text (default).
        * "faster_whisper" - Local speech recognition using faster-whisper (raises NotImplementedError).

    Returns
    -------
    str
        Transcribed text from the audio input.

    Raises
    ------
    ValueError
        If audio_bytes is empty, or if an unknown backend is provided.
    NotImplementedError
        If backend="faster_whisper" is selected.
    """
    if not isinstance(audio_bytes, (bytes, bytearray)) or len(audio_bytes) == 0:
        raise ValueError("Audio bytes cannot be empty.")

    backend_normalized = backend.lower().strip() if isinstance(backend, str) else backend

    if backend_normalized == "mock":
        return _mock_transcribe(audio_bytes)

    if backend_normalized == "faster_whisper":
        raise NotImplementedError("Backend 'faster_whisper' is not yet implemented.")

    raise ValueError(
        f"Unknown backend {backend!r}. Choose one of: 'mock', 'faster_whisper'."
    )
