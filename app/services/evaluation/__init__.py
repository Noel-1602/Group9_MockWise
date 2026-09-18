"""Answer evaluation service package."""

from app.services.evaluation.evaluator import evaluate_answer
from app.services.evaluation.schema import EvaluationResult

__all__ = [
    "EvaluationResult",
    "evaluate_answer",
]
