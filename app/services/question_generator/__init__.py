"""Question generation service package."""

from app.services.question_generator.generator import generate_questions
from app.services.question_generator.schema import GeneratedQuestion, QuestionType

__all__ = [
    "generate_questions",
    "GeneratedQuestion",
    "QuestionType",
]
