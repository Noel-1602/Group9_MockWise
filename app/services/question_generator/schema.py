"""Pydantic schemas representing generated interview questions."""

from typing import Literal
from pydantic import BaseModel, ConfigDict, Field

QuestionType = Literal["resume_specific", "general"]


class GeneratedQuestion(BaseModel):
    """Schema representing a single generated interview question.

    Deliberately flat: consists of question text and type categorization
    ('resume_specific' or 'general') with no nested models.
    """
    model_config = ConfigDict(extra="forbid")

    question_text: str = Field(description="The interview question text")
    type: QuestionType = Field(
        description="Type category of the question: 'resume_specific' or 'general'",
    )
