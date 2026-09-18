"""Answer evaluation service orchestrator.

Provides evaluation backends for candidate interview responses:
- mock: Heuristic-based evaluator using transcript word counts to assign deterministic scores and feedback.
- llm: LLM-based evaluation (to be implemented).
"""

import logging
from typing import Literal

from app.services.evaluation.schema import EvaluationResult

logger = logging.getLogger(__name__)


def _mock_evaluate(question_text: str, transcript_text: str) -> EvaluationResult:
    """Evaluate candidate answer using word-count heuristics.

    Parameters
    ----------
    question_text:
        The interview question presented to the candidate.
    transcript_text:
        The transcribed candidate answer.

    Returns
    -------
    EvaluationResult
        Deterministic evaluation result with scores bounded in [0.0, 10.0].
    """
    words = transcript_text.split()
    word_count = len(words)

    if word_count < 10:
        score = 3.0
        feedback = "Answer was concise; consider adding more detail."
    elif word_count <= 40:
        score = 6.0
        feedback = "Answer was moderately detailed; covered key points with room for expansion."
    else:
        score = 8.0
        feedback = "Answer was comprehensive and thorough; demonstrated strong depth."

    return EvaluationResult(
        overall_score=score,
        relevance_score=score,
        clarity_score=score,
        structure_score=score,
        feedback_text=feedback,
    )


def evaluate_answer(
    question_text: str,
    transcript_text: str,
    backend: Literal["mock", "llm"] = "mock",
) -> EvaluationResult:
    """Evaluate a candidate's answer to an interview question.

    Parameters
    ----------
    question_text:
        The interview question that was asked.
    transcript_text:
        The transcribed verbal or written answer from the candidate.
    backend:
        Evaluation backend strategy:
        * "mock" - Heuristic word-count evaluator (default).
        * "llm"  - LLM-based evaluator (raises NotImplementedError).

    Returns
    -------
    EvaluationResult
        Structured evaluation containing scores (0-10) and feedback.

    Raises
    ------
    ValueError
        If transcript_text or question_text is empty or whitespace-only,
        or if an unknown backend is provided.
    NotImplementedError
        If backend="llm" is selected.
    """
    if not isinstance(transcript_text, str) or not transcript_text.strip():
        raise ValueError("Transcript text cannot be empty or whitespace-only.")

    if not isinstance(question_text, str) or not question_text.strip():
        raise ValueError("Question text cannot be empty or whitespace-only.")

    backend_normalized = (
        backend.lower().strip() if isinstance(backend, str) else backend
    )

    if backend_normalized == "mock":
        return _mock_evaluate(question_text, transcript_text)

    if backend_normalized == "llm":
        raise NotImplementedError("Backend 'llm' is not yet implemented.")

    raise ValueError(
        f"Unknown backend {backend!r}. Choose one of: 'mock', 'llm'."
    )
