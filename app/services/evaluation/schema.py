"""Pydantic schema representing candidate answer evaluation results."""

from pydantic import BaseModel, ConfigDict, Field


class EvaluationResult(BaseModel):
    """Schema representing structured candidate answer evaluation.

    Deliberately flat: consists of numeric scores (0–10) and feedback text
    with no nested models.
    """
    model_config = ConfigDict(extra="forbid")

    overall_score: float = Field(
        ...,
        ge=0.0,
        le=10.0,
        description="Overall evaluation score between 0 and 10 inclusive.",
    )
    relevance_score: float = Field(
        ...,
        ge=0.0,
        le=10.0,
        description="Relevance score between 0 and 10 inclusive.",
    )
    clarity_score: float = Field(
        ...,
        ge=0.0,
        le=10.0,
        description="Clarity and articulation score between 0 and 10 inclusive.",
    )
    structure_score: float = Field(
        ...,
        ge=0.0,
        le=10.0,
        description="Structure and coherence score between 0 and 10 inclusive.",
    )
    feedback_text: str = Field(
        ...,
        description="Constructive feedback and breakdown for the candidate.",
    )
