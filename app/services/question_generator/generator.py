"""Question generation service orchestrator.

Provides question generation backends for structured resumes:
- mock: Deterministic generator grounded in resume fields (for testing/development).
- ollama: Local LLM generation via Ollama (to be implemented).
- groq: Cloud LLM generation via Groq API (to be implemented).
"""

import logging
from typing import List, Literal

from app.services.question_generator.schema import GeneratedQuestion
from app.services.resume_parser.schema import ParsedResume

logger = logging.getLogger(__name__)


def _mock_generate(resume: ParsedResume) -> List[GeneratedQuestion]:
    """Generate a deterministic set of questions for testing and development."""
    questions: List[GeneratedQuestion] = []

    # 1. Resume-specific question grounded in skills
    if resume.skills:
        skill = resume.skills[0]
        questions.append(
            GeneratedQuestion(
                question_text=f"Can you describe your experience and key achievements using {skill}?",
                type="resume_specific",
            )
        )
    else:
        questions.append(
            GeneratedQuestion(
                question_text="Can you describe your core technical skills and how you apply them?",
                type="general",
            )
        )

    # 2. Resume-specific question grounded in projects
    if resume.projects:
        project = resume.projects[0]
        questions.append(
            GeneratedQuestion(
                question_text=f"Could you walk me through the architecture and technical challenges of '{project.title}'?",
                type="resume_specific",
            )
        )
    else:
        questions.append(
            GeneratedQuestion(
                question_text="Can you describe a significant project you built and the challenges you faced?",
                type="general",
            )
        )

    # 3. General behavioral / background question
    questions.append(
        GeneratedQuestion(
            question_text="Tell me about yourself and what drives your interest in this role.",
            type="general",
        )
    )

    return questions


def generate_questions(
    resume: ParsedResume,
    backend: Literal["mock", "ollama", "groq"] = "mock",
) -> List[GeneratedQuestion]:
    """Generate interview questions grounded in a parsed resume using the selected backend.

    Parameters
    ----------
    resume:
        Structured parsed resume data.
    backend:
        Generation backend strategy:
        * "mock"   - Deterministic rule-based question generator.
        * "ollama" - Local LLM generation via Ollama (raises NotImplementedError).
        * "groq"   - Cloud LLM generation via Groq API (raises NotImplementedError).

    Returns
    -------
    List[GeneratedQuestion]
        List of generated interview questions.

    Raises
    ------
    NotImplementedError
        If "ollama" or "groq" backends are selected.
    ValueError
        If an unknown backend is provided.
    """
    if backend == "mock":
        return _mock_generate(resume)

    if backend in ("ollama", "groq"):
        raise NotImplementedError(
            f"Backend {backend!r} is not yet implemented."
        )

    raise ValueError(
        f"Unknown backend {backend!r}. Choose one of: 'mock', 'ollama', 'groq'."
    )
