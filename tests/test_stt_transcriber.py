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


def test_faster_whisper_backend_successful_transcription(monkeypatch):
    """Verify faster_whisper backend transcribes audio bytes and concatenates segments cleanly."""
    class MockSegment:
        def __init__(self, text: str):
            self.text = text

    class MockWhisperModel:
        def __init__(self, model_size, device="cpu", compute_type="int8"):
            self.model_size = model_size
            self.device = device
            self.compute_type = compute_type

        def transcribe(self, audio_file):
            segments = [
                MockSegment("  I have built multiple microservices "),
                MockSegment(" using FastAPI and Docker.  "),
            ]
            return segments, None

    # Reset singleton model for test isolation
    import app.services.stt.transcriber as stt_module
    monkeypatch.setattr(stt_module, "_whisper_model", MockWhisperModel("base"))

    sample_audio = b"dummy audio bytes"
    result = transcribe_audio(sample_audio, backend="faster_whisper")

    assert result == "I have built multiple microservices using FastAPI and Docker."


def test_faster_whisper_backend_empty_speech_returns_empty_string(monkeypatch):
    """Verify faster_whisper backend handles silent / no speech audio gracefully."""
    class MockWhisperModel:
        def __init__(self, *args, **kwargs):
            pass

        def transcribe(self, audio_file):
            return [], None

    import app.services.stt.transcriber as stt_module
    monkeypatch.setattr(stt_module, "_whisper_model", MockWhisperModel())

    result = transcribe_audio(b"silent audio bytes", backend="faster_whisper")
    assert result == ""


def test_faster_whisper_backend_missing_package_raises_import_error(monkeypatch):
    """Verify faster_whisper raises ImportError when faster-whisper is not installed."""
    import app.services.stt.transcriber as stt_module
    monkeypatch.setattr(stt_module, "_whisper_model", None)

    import builtins
    real_import = builtins.__import__

    def mock_import(name, *args, **kwargs):
        if name == "faster_whisper":
            raise ImportError("No module named 'faster_whisper'")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", mock_import)

    with pytest.raises(ImportError, match="The 'faster-whisper' package is required"):
        transcribe_audio(b"audio bytes", backend="faster_whisper")


def test_unknown_backend_raises_value_error():
    """Verify unknown backend string raises ValueError."""
    with pytest.raises(ValueError, match="Unknown backend"):
        transcribe_audio(b"dummy audio bytes", backend="unknown")  # type: ignore[arg-type]
