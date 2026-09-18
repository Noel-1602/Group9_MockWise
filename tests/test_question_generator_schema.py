import pytest
from pydantic import ValidationError

from app.services.question_generator.schema import GeneratedQuestion


def test_generated_question_valid():
    """Verify GeneratedQuestion instantiates with valid data."""
    q1 = GeneratedQuestion(
        question_text="Can you explain your experience with microservices?",
        type="resume_specific",
    )
    assert q1.question_text == "Can you explain your experience with microservices?"
    assert q1.type == "resume_specific"

    q2 = GeneratedQuestion(
        question_text="What is your biggest strength?",
        type="general",
    )
    assert q2.question_text == "What is your biggest strength?"
    assert q2.type == "general"


def test_generated_question_type_required():
    """Verify GeneratedQuestion raises ValidationError when type is omitted."""
    with pytest.raises(ValidationError):
        GeneratedQuestion(question_text="Tell me about yourself.")


def test_generated_question_invalid_type():
    """Verify GeneratedQuestion raises ValidationError on invalid question type."""
    with pytest.raises(ValidationError):
        GeneratedQuestion(
            question_text="Invalid question type test",
            type="invalid_type",
        )


def test_generated_question_extra_forbidden():
    """Verify extra fields raise ValidationError when extra='forbid' is configured."""
    with pytest.raises(ValidationError):
        GeneratedQuestion.model_validate({
            "question_text": "Explain async IO in Python.",
            "type": "general",
            "extra_field": "should be rejected",
        })
