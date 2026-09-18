import pytest

from app.services.stt.transcriber import MOCK_TRANSCRIPTION, transcribe_audio


def test_mock_backend_returns_expected_string():
    """Verify mock backend returns the expected non-empty placeholder string for valid bytes."""
    sample_audio = b"RIFF\x24\x00\x00\x00WAVEfmt \x10\x00\x00\x00"
    result = transcribe_audio(sample_audio, backend="mock")

    assert isinstance(result, str)
    assert len(result) > 0
    assert result == MOCK_TRANSCRIPTION


def test_mock_backend_default_parameter():
    """Verify default backend parameter is 'mock' and produces expected string."""
    result = transcribe_audio(b"some audio stream bytes")

    assert result == MOCK_TRANSCRIPTION


def test_empty_bytes_raises_value_error():
    """Verify empty bytes raises ValueError."""
    with pytest.raises(ValueError, match="empty"):
        transcribe_audio(b"", backend="mock")


def test_faster_whisper_backend_raises_not_implemented_error():
    """Verify backend='faster_whisper' raises NotImplementedError."""
    with pytest.raises(NotImplementedError, match="faster_whisper"):
        transcribe_audio(b"dummy audio bytes", backend="faster_whisper")


def test_unknown_backend_raises_value_error():
    """Verify unknown backend string raises ValueError."""
    with pytest.raises(ValueError, match="Unknown backend"):
        transcribe_audio(b"dummy audio bytes", backend="unknown")  # type: ignore[arg-type]
