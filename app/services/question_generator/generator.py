"""Question generation service orchestrator.

Provides question generation backends for structured resumes:
- mock: Rule-based generator grounded across resume fields. Deterministic when
  count (and any random seed) is fixed, but randomizes the total within 6-8 by default.
- ollama: Local LLM generation via Ollama (to be implemented).
- groq: Cloud LLM generation via Groq API (openai/gpt-oss-120b).
"""

import json
import logging
import os
import random
from typing import List, Literal, Optional

from app.services.question_generator.schema import GeneratedQuestion
from app.services.resume_parser.schema import ParsedResume

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

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

_GROQ_SYSTEM_PROMPT = """\
You are an expert technical interviewer. Your task is to generate a set of interview questions for a candidate based on their structured resume data.

Follow these strict rules:
1. Target Question Count: Generate {target_count_instruction}.
2. Question Types and Distribution:
   - "resume_specific": Grounded directly in the candidate's actual listed skills, projects, work experience, or education.
   - "general": Technical, architectural, problem-solving, behavioral, or engineering leadership questions.
   - Aim for approximately 70% "resume_specific" questions and 30% "general" questions when sufficient resume content is available.
3. Grounding and Integrity (CRITICAL):
   - Only ground "resume_specific" questions in information explicitly stated in the provided resume.
   - DO NOT fabricate, hallucinate, or assume technologies, tools, responsibilities, or accomplishments not present in the resume.
   - THIN / SPARSE RESUME RULE: If the resume contains little content or empty sections, DO NOT invent fake specifics. Instead, generate fewer "resume_specific" questions and lean more heavily on high-quality "general" interview questions to meet the requested count.
4. Uniqueness: All questions must be distinct; do not repeat questions or duplicate concepts.
5. Response Format: Respond ONLY with a valid JSON object matching the schema below. Do not include markdown code fences, comments, or any surrounding text.

Schema:
{{
  "questions": [
    {{
      "question_text": "<question text>",
      "type": "resume_specific" | "general"
    }}
  ]
}}
"""


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

    # Shuffle copies of items using unseeded randomness so each generation call produces fresh combinations
    shuffled_skills = list(available_skills)
    random.shuffle(shuffled_skills)
    shuffled_projects = list(available_projects)
    random.shuffle(shuffled_projects)
    shuffled_experience = list(available_experience)
    random.shuffle(shuffled_experience)
    shuffled_general = list(_GENERAL_QUESTION_POOL)
    random.shuffle(shuffled_general)

    questions: List[GeneratedQuestion] = []
    seen_texts: set = set()

    skill_idx = 0
    project_idx = 0
    experience_idx = 0

    # Cycle across skills, projects, and experience to generate resume_specific questions
    while len(questions) < target_resume_specific:
        added_in_round = False

        # 1. Skill item
        if skill_idx < len(shuffled_skills) and len(questions) < target_resume_specific:
            skill = shuffled_skills[skill_idx]
            skill_idx += 1
            q_text = f"Can you describe your experience and key achievements using {skill}?"
            if q_text not in seen_texts:
                seen_texts.add(q_text)
                questions.append(
                    GeneratedQuestion(question_text=q_text, type="resume_specific")
                )
                added_in_round = True

        # 2. Project item
        if project_idx < len(shuffled_projects) and len(questions) < target_resume_specific:
            proj = shuffled_projects[project_idx]
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
        if experience_idx < len(shuffled_experience) and len(questions) < target_resume_specific:
            exp = shuffled_experience[experience_idx]
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
        if gen_idx < len(shuffled_general):
            q_text = shuffled_general[gen_idx]
            gen_idx += 1
        else:
            q_text = f"Can you describe a challenging engineering scenario you encountered and how you handled it? (Part {len(questions) + 1})"

        if q_text not in seen_texts:
            seen_texts.add(q_text)
            questions.append(GeneratedQuestion(question_text=q_text, type="general"))

    return questions


def _format_resume_context(resume: ParsedResume) -> str:
    """Format structured resume into a human-readable text block for prompt grounding."""
    parts = []

    skills = [s.strip() for s in resume.skills if s and s.strip()]
    if skills:
        parts.append(f"Skills: {', '.join(skills)}")
    else:
        parts.append("Skills: None provided")

    if resume.projects:
        proj_lines = []
        for p in resume.projects:
            title = p.title.strip() if p.title else "Untitled Project"
            desc = f" - {p.description.strip()}" if p.description and p.description.strip() else ""
            proj_lines.append(f"* {title}{desc}")
        parts.append("Projects:\n" + "\n".join(proj_lines))
    else:
        parts.append("Projects: None provided")

    exp = [e.strip() for e in resume.experience if e and e.strip()]
    if exp:
        parts.append("Experience:\n" + "\n".join(f"* {e}" for e in exp))
    else:
        parts.append("Experience: None provided")

    edu = [ed.strip() for ed in resume.education if ed and ed.strip()]
    if edu:
        parts.append("Education:\n" + "\n".join(f"* {ed}" for ed in edu))
    else:
        parts.append("Education: None provided")

    return "\n\n".join(parts)


def _parse_groq_json_response(raw_text: str) -> List[GeneratedQuestion]:
    """Parse and validate JSON response from Groq LLM into List[GeneratedQuestion]."""
    text = raw_text.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        # drop opening fence line
        lines = lines[1:] if lines[0].startswith("```") else lines
        # drop closing fence line
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()

    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"Failed to parse JSON from Groq question generator response: {exc}\nRaw content: {raw_text}"
        ) from exc

    if isinstance(data, dict):
        raw_questions = data.get("questions")
        if not isinstance(raw_questions, list):
            raise ValueError(
                f"Invalid JSON response schema: expected 'questions' key containing a list, got {type(raw_questions).__name__}"
            )
    elif isinstance(data, list):
        raw_questions = data
    else:
        raise ValueError(
            f"Invalid JSON response structure: expected dict or list, got {type(data).__name__}"
        )

    questions: List[GeneratedQuestion] = []
    seen_texts: set = set()
    for item in raw_questions:
        if not isinstance(item, dict):
            continue
        q_text = item.get("question_text", "").strip() if isinstance(item.get("question_text"), str) else ""
        q_type = item.get("type", "general").strip() if isinstance(item.get("type"), str) else "general"
        if q_type not in ("resume_specific", "general"):
            q_type = "general"
        if q_text and q_text not in seen_texts:
            seen_texts.add(q_text)
            questions.append(GeneratedQuestion(question_text=q_text, type=q_type))

    if not questions:
        raise ValueError(f"Groq question generator returned no valid questions. Raw content: {raw_text}")

    return questions


def _groq_generate(
    resume: ParsedResume,
    count: Optional[int] = None,
) -> List[GeneratedQuestion]:
    """Generate interview questions using Groq cloud LLM.

    Requires the ``groq`` package and GROQ_API_KEY environment variable.
    """
    try:
        from groq import Groq  # type: ignore[import]
    except ImportError as exc:
        raise ImportError(
            "The 'groq' package is required for the groq backend. "
            "Install it with: pip install groq"
        ) from exc

    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise EnvironmentError(
            "GROQ_API_KEY environment variable is not set. "
            "Set it before using the groq backend."
        )

    if count is not None:
        target_instruction = f"exactly {max(1, count)} questions"
    else:
        target_instruction = "between 6 and 8 interview questions (defaulting to 7)"

    system_prompt = _GROQ_SYSTEM_PROMPT.format(target_count_instruction=target_instruction)
    resume_context = _format_resume_context(resume)
    user_prompt = f"Candidate Resume Data:\n\n{resume_context}\n\nPlease generate the interview questions now."

    client = Groq(api_key=api_key)
    completion = client.chat.completions.create(
        model="openai/gpt-oss-120b",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.7,
    )
    raw_content = completion.choices[0].message.content or ""
    return _parse_groq_json_response(raw_content)


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
        * "mock"   - Rule-based generator grounded in resume fields (default).
        * "ollama" - Local LLM generation via Ollama (raises NotImplementedError).
        * "groq"   - Cloud LLM generation via Groq API (openai/gpt-oss-120b).
    count:
        Optional exact number of questions to generate. If None, the generator
        produces 6 to 8 questions.

    Returns
    -------
    List[GeneratedQuestion]
        List of generated interview questions.

    Raises
    ------
    NotImplementedError
        If "ollama" backend is selected.
    ValueError
        If an unknown backend is provided or if the LLM output is malformed.
    ImportError
        If the required 'groq' package is missing when using the groq backend.
    EnvironmentError
        If GROQ_API_KEY is not set when using the groq backend.
    """
    backend_normalized = backend.lower().strip() if isinstance(backend, str) else backend

    if backend_normalized == "mock":
        return _mock_generate(resume, count=count)

    if backend_normalized == "groq":
        return _groq_generate(resume, count=count)

    if backend_normalized == "ollama":
        raise NotImplementedError(
            f"Backend {backend!r} is not yet implemented."
        )

    raise ValueError(
        f"Unknown backend {backend!r}. Choose one of: 'mock', 'ollama', 'groq'."
    )
