import pytest
from pydantic import ValidationError

from app.services.evaluation.schema import EvaluationResult


def test_evaluation_result_valid():
    """Verify EvaluationResult instantiates correctly with valid scores and feedback."""
    result = EvaluationResult(
        overall_score=8.5,
        relevance_score=9.0,
        clarity_score=8.0,
        structure_score=8.5,
        feedback_text="Strong answer with clear explanation and structured approach.",
    )
    assert result.overall_score == 8.5
    assert result.relevance_score == 9.0
    assert result.clarity_score == 8.0
    assert result.structure_score == 8.5
    assert result.feedback_text == "Strong answer with clear explanation and structured approach."


@pytest.mark.parametrize("score_field,invalid_val", [
    ("overall_score", 10.1),
    ("overall_score", -0.1),
    ("overall_score", 15.0),
    ("overall_score", -5.0),
    ("relevance_score", 10.5),
    ("relevance_score", -1.0),
    ("clarity_score", 11.0),
    ("clarity_score", -0.5),
    ("structure_score", 12.0),
    ("structure_score", -2.0),
])
def test_evaluation_result_score_out_of_bounds_raises_validation_error(score_field, invalid_val):
    """Verify any score above 10 or below 0 raises ValidationError."""
    valid_data = {
        "overall_score": 8.0,
        "relevance_score": 8.0,
        "clarity_score": 8.0,
        "structure_score": 8.0,
        "feedback_text": "Good response.",
    }
    valid_data[score_field] = invalid_val
    with pytest.raises(ValidationError):
        EvaluationResult(**valid_data)


@pytest.mark.parametrize("missing_field", [
    "overall_score",
    "relevance_score",
    "clarity_score",
    "structure_score",
    "feedback_text",
])
def test_evaluation_result_missing_required_field_raises_validation_error(missing_field):
    """Verify omitting any required field raises ValidationError."""
    valid_data = {
        "overall_score": 7.5,
        "relevance_score": 7.0,
        "clarity_score": 8.0,
        "structure_score": 7.5,
        "feedback_text": "Constructive feedback.",
    }
    del valid_data[missing_field]
    with pytest.raises(ValidationError):
        EvaluationResult(**valid_data)


def test_evaluation_result_extra_field_forbidden():
    """Verify passing unexpected extra field raises ValidationError per extra='forbid'."""
    with pytest.raises(ValidationError):
        EvaluationResult.model_validate({
            "overall_score": 8.0,
            "relevance_score": 8.0,
            "clarity_score": 8.0,
            "structure_score": 8.0,
            "feedback_text": "Solid answer.",
            "unexpected_extra_field": "disallowed",
        })
