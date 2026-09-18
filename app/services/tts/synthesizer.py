"""TTS (Text-to-Speech) synthesis service orchestrator.

Provides speech synthesis backends:
- mock: Rule-based generator returning raw bytes of a valid minimal WAV file (silent clip).
- piper: Local neural TTS via Piper (to be implemented).
"""

import io
import logging
import wave
from typing import Literal

logger = logging.getLogger(__name__)


def _generate_minimal_wav(
    duration_seconds: float = 0.5,
    sample_rate: int = 16000,
    num_channels: int = 1,
    sample_width: int = 2,
) -> bytes:
    """Generate the raw bytes of a valid minimal silent WAV file.

    Parameters
    ----------
    duration_seconds:
        Duration of the silent clip in seconds.
    sample_rate:
        Audio sample rate in Hz (default 16000 Hz).
    num_channels:
        Number of audio channels (default 1 for mono).
    sample_width:
        Sample width in bytes (default 2 for 16-bit PCM).

    Returns
    -------
    bytes
        Valid WAV file bytes starting with RIFF header.
    """
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wav_file:
        wav_file.setnchannels(num_channels)
        wav_file.setsampwidth(sample_width)
        wav_file.setframerate(sample_rate)
        num_frames = int(duration_seconds * sample_rate)
        wav_file.writeframes(b"\x00" * (num_frames * num_channels * sample_width))
    return buf.getvalue()


def _mock_synthesize(text: str) -> bytes:
    """Generate deterministic mock audio for the given text.

    Parameters
    ----------
    text:
        Input text to synthesize.

    Returns
    -------
    bytes
        Raw bytes of a valid minimal WAV file.
    """
    return _generate_minimal_wav()


def synthesize_speech(
    text: str,
    backend: Literal["mock", "piper"] = "mock",
) -> bytes:
    """Synthesize speech audio from text using the selected backend.

    Parameters
    ----------
    text:
        Text content to convert to speech.
    backend:
        Synthesis backend strategy:
        * "mock"  - Deterministic generator returning a valid minimal WAV file (default).
        * "piper" - Fast local neural TTS (raises NotImplementedError).

    Returns
    -------
    bytes
        Raw binary audio content (WAV format).

    Raises
    ------
    ValueError
        If text is empty or whitespace-only, or if an unknown backend is provided.
    NotImplementedError
        If backend="piper" is selected.
    """
    if not isinstance(text, str) or not text.strip():
        raise ValueError("Text cannot be empty or whitespace-only.")

    backend_normalized = backend.lower().strip() if isinstance(backend, str) else backend

    if backend_normalized == "mock":
        return _mock_synthesize(text)

    if backend_normalized == "piper":
        raise NotImplementedError("Backend 'piper' is not yet implemented.")

    raise ValueError(
        f"Unknown backend {backend!r}. Choose one of: 'mock', 'piper'."
    )
