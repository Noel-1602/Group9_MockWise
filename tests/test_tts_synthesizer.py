import io
import wave
import pytest

from app.services.tts.synthesizer import synthesize_speech


def test_mock_backend_returns_valid_wav_riff_header():
    """Verify mock backend returns bytes starting with RIFF magic bytes and is a valid WAV."""
    audio_bytes = synthesize_speech("Hello world, this is a test.", backend="mock")

    assert isinstance(audio_bytes, bytes)
    assert len(audio_bytes) > 0
    # RIFF header checks
    assert audio_bytes.startswith(b"RIFF")
    assert audio_bytes[8:12] == b"WAVE"

    # Verify standard wave reader can parse it
    with wave.open(io.BytesIO(audio_bytes), "rb") as wav_file:
        assert wav_file.getnchannels() == 1
        assert wav_file.getsampwidth() == 2
        assert wav_file.getframerate() == 16000
        assert wav_file.getnframes() > 0


def test_mock_backend_default_parameter():
    """Verify default backend parameter is 'mock' and produces valid WAV bytes."""
    audio_bytes = synthesize_speech("Testing default backend parameter.")

    assert isinstance(audio_bytes, bytes)
    assert audio_bytes.startswith(b"RIFF")
    assert audio_bytes[8:12] == b"WAVE"


@pytest.mark.parametrize("empty_input", [
    "",
    "   ",
    "\t\n\r ",
    " \n ",
])
def test_empty_or_whitespace_text_raises_value_error(empty_input):
    """Verify empty or whitespace-only text raises ValueError."""
    with pytest.raises(ValueError, match="empty or whitespace-only"):
        synthesize_speech(empty_input, backend="mock")


def test_piper_backend_raises_not_implemented_error():
    """Verify backend='piper' raises NotImplementedError."""
    with pytest.raises(NotImplementedError, match="piper"):
        synthesize_speech("Hello world", backend="piper")


def test_unknown_backend_raises_value_error():
    """Verify unknown backend string raises ValueError."""
    with pytest.raises(ValueError, match="Unknown backend"):
        synthesize_speech("Hello world", backend="nonexistent")  # type: ignore[arg-type]
