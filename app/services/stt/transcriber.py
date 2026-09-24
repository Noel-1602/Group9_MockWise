"""STT (Speech-to-Text) transcription service orchestrator.

Provides speech transcription backends:
- mock: Deterministic mock transcriber returning a placeholder string.
- faster_whisper: Local Whisper model transcription via faster-whisper.
"""

import io
import logging
from typing import Any, Literal, Optional

logger = logging.getLogger(__name__)

MOCK_TRANSCRIPTION: str = "This is a mock transcription of the candidate's answer."

_whisper_model: Optional[Any] = None


def _get_whisper_model():
    """Retrieve or initialize the singleton faster-whisper WhisperModel instance."""
    global _whisper_model
    if _whisper_model is None:
        try:
            from faster_whisper import WhisperModel  # type: ignore[import]
        except ImportError as exc:
            raise ImportError(
                "The 'faster-whisper' package is required for the faster_whisper backend. "
                "Install it with: pip install faster-whisper"
            ) from exc

        logger.info("Initializing faster-whisper model (base, cpu, int8)...")
        _whisper_model = WhisperModel("base", device="cpu", compute_type="int8")
    return _whisper_model


def _faster_whisper_transcribe(audio_bytes: bytes) -> str:
    """Transcribe raw audio bytes using the faster-whisper model.

    Parameters
    ----------
    audio_bytes:
        Raw audio content in bytes.

    Returns
    -------
    str
        Transcribed text from speech segments, or empty string if no speech detected.
    """
    model = _get_whisper_model()
    audio_file = io.BytesIO(audio_bytes)
    segments, _ = model.transcribe(audio_file)

    segment_texts = [s.text.strip() for s in segments if hasattr(s, "text") and s.text and s.text.strip()]
    transcription = " ".join(segment_texts).strip()
    return transcription


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
        * "faster_whisper" - Local speech recognition using faster-whisper.

    Returns
    -------
    str
        Transcribed text from the audio input.

    Raises
    ------
    ValueError
        If audio_bytes is empty, or if an unknown backend is provided.
    ImportError
        If faster-whisper is not installed and backend="faster_whisper" is selected.
    """
    if not isinstance(audio_bytes, (bytes, bytearray)) or len(audio_bytes) == 0:
        raise ValueError("Audio bytes cannot be empty.")

    backend_normalized = backend.lower().strip() if isinstance(backend, str) else backend

    if backend_normalized == "mock":
        return _mock_transcribe(audio_bytes)

    if backend_normalized == "faster_whisper":
        return _faster_whisper_transcribe(audio_bytes)

    raise ValueError(
        f"Unknown backend {backend!r}. Choose one of: 'mock', 'faster_whisper'."
    )
