import pytest
from pydantic import ValidationError

from app.services.evaluation.evaluator import evaluate_answer
from app.services.evaluation.schema import EvaluationResult


def test_short_transcript_produces_low_scores():
    """Verify that a short transcript (< 10 words) produces low scores within the 0-10 bound."""
    question = "Can you describe your experience with Python?"
    transcript = "I used Python once for a small script."
    assert len(transcript.split()) < 10

    result = evaluate_answer(question, transcript, backend="mock")

    assert isinstance(result, EvaluationResult)
    assert 0.0 <= result.overall_score <= 10.0
    assert 2.0 <= result.overall_score <= 3.5
    assert result.overall_score == result.relevance_score == result.clarity_score == result.structure_score
    assert "concise" in result.feedback_text.lower() or "detail" in result.feedback_text.lower()


def test_mid_length_transcript_produces_mid_scores():
    """Verify that a mid-range transcript (10-40 words) produces mid-range scores (5-6)."""
    question = "Can you describe your experience with Python?"
    transcript = (
        "I have worked with Python for about two years building backend APIs using "
        "FastAPI and PostgreSQL, creating endpoints, writing tests, and managing migrations."
    )
    words = transcript.split()
    assert 10 <= len(words) <= 40

    result = evaluate_answer(question, transcript, backend="mock")

    assert isinstance(result, EvaluationResult)
    assert 5.0 <= result.overall_score <= 6.5
    assert result.overall_score == result.relevance_score == result.clarity_score == result.structure_score
    assert len(result.feedback_text) > 0


def test_long_transcript_produces_high_scores():
    """Verify that a long transcript (> 40 words) produces higher scores (7-8)."""
    question = "Can you describe your experience with Python?"
    transcript = (
        "In my previous role as a software engineer, I spent three years architecting and developing "
        "high-throughput microservices in Python. We utilized FastAPI and AsyncIO to process incoming data streams, "
        "integrated Celery and Redis for distributed background task execution, and implemented comprehensive "
        "unit and integration test suites using pytest. Additionally, I set up CI/CD pipelines to ensure seamless deployments."
    )
    assert len(transcript.split()) > 40

    result = evaluate_answer(question, transcript, backend="mock")

    assert isinstance(result, EvaluationResult)
    assert 7.0 <= result.overall_score <= 8.5
    assert result.overall_score == result.relevance_score == result.clarity_score == result.structure_score
    assert "thorough" in result.feedback_text.lower() or "depth" in result.feedback_text.lower()


def test_stress_test_very_long_input_within_bounds():
    """Verify scores never exceed 0-10 bounds regardless of transcript length, including very long inputs."""
    question = "Describe your background."
    very_long_transcript = " ".join(["experience"] * 2000)

    result = evaluate_answer(question, very_long_transcript, backend="mock")

    assert isinstance(result, EvaluationResult)
    for score in [result.overall_score, result.relevance_score, result.clarity_score, result.structure_score]:
        assert 0.0 <= score <= 10.0
    assert result.overall_score == 8.0


def test_default_backend_is_mock():
    """Verify default backend parameter is 'mock'."""
    question = "What is your experience?"
    transcript = "I have several years of experience writing clean Python code."
    result = evaluate_answer(question, transcript)

    assert isinstance(result, EvaluationResult)
    assert 0.0 <= result.overall_score <= 10.0


@pytest.mark.parametrize("empty_transcript", [
    "",
    "   ",
    "\t\n\r ",
    " \n ",
])
def test_empty_or_whitespace_transcript_raises_value_error(empty_transcript):
    """Verify empty or whitespace-only transcript raises ValueError."""
    with pytest.raises(ValueError, match="Transcript text cannot be empty or whitespace-only"):
        evaluate_answer("Sample question?", empty_transcript, backend="mock")


@pytest.mark.parametrize("empty_question", [
    "",
    "   ",
    "\t\n\r ",
    " \n ",
])
def test_empty_or_whitespace_question_raises_value_error(empty_question):
    """Verify empty or whitespace-only question raises ValueError."""
    with pytest.raises(ValueError, match="Question text cannot be empty or whitespace-only"):
        evaluate_answer(empty_question, "Valid answer transcript here.", backend="mock")


def test_llm_backend_raises_not_implemented_error():
    """Verify backend='llm' raises NotImplementedError."""
    with pytest.raises(NotImplementedError, match="Backend 'llm' is not yet implemented"):
        evaluate_answer("What is Python?", "Python is a programming language.", backend="llm")


def test_unknown_backend_raises_value_error():
    """Verify unknown backend string raises ValueError."""
    with pytest.raises(ValueError, match="Unknown backend"):
        evaluate_answer("What is Python?", "Python is a programming language.", backend="invalid_backend")  # type: ignore[arg-type]
