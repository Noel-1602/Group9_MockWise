"""Question generation service orchestrator.

Provides question generation backends for structured resumes:
- mock: Rule-based generator grounded across resume fields. Deterministic when
  count (and any random seed) is fixed, but randomizes the total within 6-8 by default.
- ollama: Local LLM generation via Ollama (to be implemented).
- groq: Cloud LLM generation via Groq API (to be implemented).
"""

import logging
import random
from typing import List, Literal, Optional

from app.services.question_generator.schema import GeneratedQuestion
from app.services.resume_parser.schema import ParsedResume

logger = logging.getLogger(__name__)

# Pool of diverse general questions to supplement interview sets
_GENERAL_QUESTION_POOL: List[str] = [
    "Tell me about yourself and what motivates you in your career.",
    "What is one of the most challenging technical problems you have solved recently?",
    "How do you approach learning and mastering a new technology or framework quickly?",
    "Can you describe a situation where you had to make a technical trade-off under tight deadlines?",
    "How do you handle disagreements or differing opinions on technical decisions within a team?",
    "What strategies do you use for debugging complex issues in production environments?",
    "Where do you see your technical growth and career heading in the next few years?",
    "Describe a time when you received constructive feedback and how you acted on it.",
    "How do you ensure code quality, testability, and maintainability in your daily work?",
    "What is your approach to collaborating effectively with cross-functional team members?",
    "How do you prioritize competing tasks when working on multiple high-priority deliverables?",
    "Can you describe a time when a project didn't go as planned and how you adapted?",
]


def _mock_generate(
    resume: ParsedResume,
    count: Optional[int] = None,
) -> List[GeneratedQuestion]:
    """Generate mock interview questions grounded across resume fields.

    Parameters
    ----------
    resume:
        Structured parsed resume data.
    count:
        Optional exact number of questions to generate. If None, picks a random
        integer between 6 and 8 inclusive.

    Returns
    -------
    List[GeneratedQuestion]
        List of generated questions with ~70% resume-specific and remainder general.
    """
    if count is None:
        target_count = random.randint(6, 8)
    else:
        target_count = max(0, count)

    if target_count == 0:
        return []

    target_resume_specific = round(target_count * 0.7)

    # Gather available non-empty distinct items from resume sections
    available_skills = [s.strip() for s in resume.skills if s and s.strip()]
    available_projects = [
        p for p in resume.projects
        if (p.title and p.title.strip()) or (p.description and p.description.strip())
    ]
    available_experience = [e.strip() for e in resume.experience if e and e.strip()]

    questions: List[GeneratedQuestion] = []
    seen_texts: set = set()

    skill_idx = 0
    project_idx = 0
    experience_idx = 0

    # Cycle across skills, projects, and experience to generate resume_specific questions
    while len(questions) < target_resume_specific:
        added_in_round = False

        # 1. Skill item
        if skill_idx < len(available_skills) and len(questions) < target_resume_specific:
            skill = available_skills[skill_idx]
            skill_idx += 1
            q_text = f"Can you describe your experience and key achievements using {skill}?"
            if q_text not in seen_texts:
                seen_texts.add(q_text)
                questions.append(
                    GeneratedQuestion(question_text=q_text, type="resume_specific")
                )
                added_in_round = True

        # 2. Project item
        if project_idx < len(available_projects) and len(questions) < target_resume_specific:
            proj = available_projects[project_idx]
            project_idx += 1
            proj_title = proj.title.strip() if proj.title and proj.title.strip() else proj.description.strip()
            q_text = f"Could you walk me through the architecture and technical challenges of '{proj_title}'?"
            if q_text not in seen_texts:
                seen_texts.add(q_text)
                questions.append(
                    GeneratedQuestion(question_text=q_text, type="resume_specific")
                )
                added_in_round = True

        # 3. Experience item
        if experience_idx < len(available_experience) and len(questions) < target_resume_specific:
            exp = available_experience[experience_idx]
            experience_idx += 1
            q_text = f"In your experience regarding '{exp}', what were your primary responsibilities and major accomplishments?"
            if q_text not in seen_texts:
                seen_texts.add(q_text)
                questions.append(
                    GeneratedQuestion(question_text=q_text, type="resume_specific")
                )
                added_in_round = True

        if not added_in_round:
            break

    # Fill remaining slots up to target_count with general questions from the pool
    gen_idx = 0
    while len(questions) < target_count:
        if gen_idx < len(_GENERAL_QUESTION_POOL):
            q_text = _GENERAL_QUESTION_POOL[gen_idx]
            gen_idx += 1
        else:
            q_text = f"Can you describe a challenging engineering scenario you encountered and how you handled it? (Part {len(questions) + 1})"

        if q_text not in seen_texts:
            seen_texts.add(q_text)
            questions.append(GeneratedQuestion(question_text=q_text, type="general"))

    return questions


def generate_questions(
    resume: ParsedResume,
    backend: Literal["mock", "ollama", "groq"] = "mock",
    count: Optional[int] = None,
) -> List[GeneratedQuestion]:
    """Generate interview questions grounded in a parsed resume using the selected backend.

    Parameters
    ----------
    resume:
        Structured parsed resume data.
    backend:
        Generation backend strategy:
        * "mock"   - Rule-based generator grounded in resume fields.
        * "ollama" - Local LLM generation via Ollama (raises NotImplementedError).
        * "groq"   - Cloud LLM generation via Groq API (raises NotImplementedError).
    count:
        Optional exact number of questions to generate. If None, the mock backend
        picks a random total between 6 and 8 inclusive.

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
        return _mock_generate(resume, count=count)

    if backend in ("ollama", "groq"):
        raise NotImplementedError(
            f"Backend {backend!r} is not yet implemented."
        )

    raise ValueError(
        f"Unknown backend {backend!r}. Choose one of: 'mock', 'ollama', 'groq'."
    )
