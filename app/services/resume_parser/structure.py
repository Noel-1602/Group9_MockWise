"""LLM structuring layer to convert cleaned resume text into StructuredResume schema.

Public API
----------
structure_resume(cleaned_text, backend="mock") -> dict
    Converts cleaned resume text into a dict matching the ParsedResume schema.

    Backends
    --------
    "mock"   – Deterministic, rule-based keyword/section extractor. No network
               calls; always returns a valid dict even for unstructured text.
    "ollama" – Sends a JSON-extraction prompt to a locally running Ollama model
               (default http://localhost:11434). Requires ``ollama`` package.
    "groq"   – Sends the same prompt to the Groq API using the GROQ_API_KEY
               environment variable. Requires ``groq`` package.
"""

import json
import logging
import os
import re
from typing import Any, Callable, Dict, List, Optional

from app.services.resume_parser.schema import (
    EducationItem,
    ExperienceItem,
    ParsedResume,
    ProjectItem,
    ResumeProject,
    StructuredResume,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Prompt used by both the ollama and groq backends
# ---------------------------------------------------------------------------

_PARSED_RESUME_PROMPT = """\
You are an expert resume parser. Extract the key information from the resume \
text below and respond ONLY with valid JSON matching the schema shown. \
Do not include any explanation, markdown fences, or extra text—just the JSON object.

Schema:
{
  "skills": [<string>, ...],
  "projects": [{"title": <string>, "description": <string>}, ...],
  "experience": [<string>, ...],
  "education": [<string>, ...]
}

Rules:
- "skills" is a flat list of skill strings.
- "experience" is a flat list of strings, each summarising one role \
  (e.g. "Software Engineer at Acme Corp, 2021-2023").
- "education" is a flat list of strings, each summarising one credential \
  (e.g. "B.Sc. Computer Science, MIT, 2020").
- "projects" is a list of objects, each with a "title" (string) and \
  "description" (string).
- Return empty lists [] when a section is absent. Never return null.

Resume Text:
---
{cleaned_text}
---
"""

# ---------------------------------------------------------------------------
# Section-header vocabulary for the mock backend
# ---------------------------------------------------------------------------

_SECTION_HEADERS: Dict[str, str] = {
    # skills
    "skills": "skills",
    "technical skills": "skills",
    "core competencies": "skills",
    "technologies": "skills",
    "tools": "skills",
    "languages": "skills",
    # experience
    "experience": "experience",
    "work experience": "experience",
    "employment history": "experience",
    "professional experience": "experience",
    "career history": "experience",
    # education
    "education": "education",
    "academic background": "education",
    "qualifications": "education",
    # projects
    "projects": "projects",
    "personal projects": "projects",
    "key projects": "projects",
    "side projects": "projects",
    "open source": "projects",
}

_SECTION_KEYS = list(_SECTION_HEADERS.keys())


def _is_section_header(line: str) -> Optional[str]:
    """Return the canonical section name if *line* is a section header, else None."""
    normalised = line.lower().strip().rstrip(":").strip()
    return _SECTION_HEADERS.get(normalised)


def _split_items(line: str) -> List[str]:
    """Split a line on commas, bullets, pipes, or semicolons into clean tokens."""
    parts = re.split(r"[,•|;]+", line.lstrip("- \t"))
    return [p.strip() for p in parts if p.strip()]


def _mock_structure(cleaned_text: str) -> dict:
    """Deterministic, rule-based parser returning a ParsedResume-shaped dict.

    Algorithm
    ---------
    1. Walk each non-blank line.
    2. If the line matches a known section header, switch the active section.
    3. Otherwise accumulate the line under the active section bucket.
    4. Post-process each bucket into the appropriate output shape.
    """
    if not cleaned_text or not cleaned_text.strip():
        return ParsedResume().model_dump()

    lines = [ln.strip() for ln in cleaned_text.splitlines()]

    buckets: Dict[str, List[str]] = {
        "skills": [],
        "experience": [],
        "education": [],
        "projects": [],
    }
    current: Optional[str] = None

    for line in lines:
        if not line:
            continue
        section = _is_section_header(line)
        if section is not None:
            current = section if section in buckets else None
            continue
        if current is not None:
            buckets[current].append(line)

    # -- skills: split comma/bullet separated values --------------------------
    skills: List[str] = []
    for ln in buckets["skills"]:
        skills.extend(_split_items(ln))

    # -- experience: one string per non-bullet line, bullets appended ---------
    experience: List[str] = []
    i = 0
    exp_lines = buckets["experience"]
    while i < len(exp_lines):
        ln = exp_lines[i]
        if ln.startswith("-"):
            # orphan bullet — append to previous entry or skip
            if experience:
                experience[-1] += "; " + ln.lstrip("- ").strip()
            i += 1
            continue
        entry = ln
        i += 1
        bullets: List[str] = []
        while i < len(exp_lines) and exp_lines[i].startswith("-"):
            bullets.append(exp_lines[i].lstrip("- ").strip())
            i += 1
        if bullets:
            entry += " — " + "; ".join(bullets)
        experience.append(entry)

    # -- education: one string per non-bullet line ----------------------------
    education: List[str] = []
    for ln in buckets["education"]:
        clean = ln.lstrip("- ").strip()
        if clean:
            education.append(clean)

    # -- projects: title line + optional bullet lines → ResumeProject dicts --
    projects: List[Dict[str, str]] = []
    j = 0
    proj_lines = buckets["projects"]
    while j < len(proj_lines):
        ln = proj_lines[j]
        if ln.startswith("-"):
            # orphan bullet — attach to previous project description
            if projects:
                prev = projects[-1]
                prev["description"] = (
                    (prev["description"] + "; " if prev["description"] else "")
                    + ln.lstrip("- ").strip()
                )
            j += 1
            continue
        title = ln.strip()
        j += 1
        desc_parts: List[str] = []
        while j < len(proj_lines) and proj_lines[j].startswith("-"):
            desc_parts.append(proj_lines[j].lstrip("- ").strip())
            j += 1
        projects.append(
            {"title": title, "description": "; ".join(desc_parts)}
        )

    parsed = ParsedResume(
        skills=skills,
        experience=experience,
        education=education,
        projects=[ResumeProject(**p) for p in projects],
    )
    return parsed.model_dump()


def _parse_llm_json(raw: str) -> dict:
    """Strip optional markdown fences and parse JSON from an LLM response."""
    text = raw.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        # drop opening fence line (```json or ```)
        lines = lines[1:] if lines[0].startswith("```") else lines
        # drop closing fence line
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    data = json.loads(text)
    # Normalise: convert project dicts that may only have a "title" key
    projects_raw = data.get("projects", [])
    projects_clean = []
    for p in projects_raw:
        if isinstance(p, dict):
            projects_clean.append(
                {"title": str(p.get("title", "")), "description": str(p.get("description", ""))}
            )
        elif isinstance(p, str):
            projects_clean.append({"title": p, "description": ""})
    data["projects"] = projects_clean
    return data


def _ollama_structure(cleaned_text: str) -> dict:
    """Call a local Ollama model and return a ParsedResume-shaped dict.

    Requires the ``ollama`` package and a running Ollama daemon on localhost.
    """
    try:
        import ollama  # type: ignore[import]
    except ImportError as exc:
        raise ImportError(
            "The 'ollama' package is required for the ollama backend. "
            "Install it with: pip install ollama"
        ) from exc

    prompt = _PARSED_RESUME_PROMPT.replace("{cleaned_text}", cleaned_text)
    response = ollama.chat(
        model="llama3",
        messages=[{"role": "user", "content": prompt}],
    )
    raw = response["message"]["content"]
    try:
        data = _parse_llm_json(raw)
        return ParsedResume(**data).model_dump()
    except Exception as exc:
        logger.warning("ollama backend: failed to parse JSON response (%s); falling back to mock.", exc)
        return _mock_structure(cleaned_text)


def _groq_structure(cleaned_text: str) -> dict:
    """Call the Groq API and return a ParsedResume-shaped dict.

    Requires the ``groq`` package and the GROQ_API_KEY environment variable.
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

    client = Groq(api_key=api_key)
    prompt = _PARSED_RESUME_PROMPT.replace("{cleaned_text}", cleaned_text)
    completion = client.chat.completions.create(
        model="llama3-8b-8192",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.0,
    )
    raw = completion.choices[0].message.content
    try:
        data = _parse_llm_json(raw)
        return ParsedResume(**data).model_dump()
    except Exception as exc:
        logger.warning("groq backend: failed to parse JSON response (%s); falling back to mock.", exc)
        return _mock_structure(cleaned_text)


def structure_resume(
    cleaned_text: str,
    backend: str = "mock",
    llm_callable: Optional[Callable[[str], str]] = None,
) -> Any:
    """Convert cleaned resume text into a ParsedResume-shaped dict.

    Parameters
    ----------
    cleaned_text:
        Pre-processed plain text of the resume.
    backend:
        Which parsing strategy to use:

        * ``"mock"``   – Deterministic rule-based extractor (default). No
                         external dependencies; always returns a valid dict.
        * ``"ollama"`` – Sends a JSON-extraction prompt to a local Ollama
                         daemon. Requires the ``ollama`` package.
        * ``"groq"``   – Sends the same prompt to the Groq cloud API.
                         Requires the ``groq`` package and ``GROQ_API_KEY``.
    llm_callable:
        Optional callable receiving prompt string and returning LLM text.
        If supplied, returns a StructuredResume model for legacy callers.

    Returns
    -------
    dict or StructuredResume
        A dict whose keys match the ``ParsedResume`` schema:
        ``{"skills": [...], "projects": [...], "experience": [...], "education": [...]}``.

    Raises
    ------
    ValueError
        If an unknown backend name is provided.
    ImportError
        If the required third-party package for a non-mock backend is missing.
    EnvironmentError
        If the ``GROQ_API_KEY`` variable is absent when using the groq backend.
    """
    if llm_callable is not None:
        if not cleaned_text or not cleaned_text.strip():
            return StructuredResume(raw_text="")
        try:
            prompt = build_structuring_prompt(cleaned_text)
            response = llm_callable(prompt)
            return parse_llm_response(response, cleaned_text)
        except Exception as exc:
            logger.error(f"Error during LLM structuring call: {exc}", exc_info=True)
            return heuristic_structure_resume(cleaned_text)

    if not cleaned_text or not cleaned_text.strip():
        return ParsedResume().model_dump()

    backend = backend.lower().strip()

    if backend == "mock":
        return _mock_structure(cleaned_text)
    if backend == "ollama":
        return _ollama_structure(cleaned_text)
    if backend == "groq":
        return _groq_structure(cleaned_text)

    raise ValueError(
        f"Unknown backend {backend!r}. Choose one of: 'mock', 'ollama', 'groq'."
    )


# ---------------------------------------------------------------------------
# Legacy helpers – kept for backwards compatibility with existing callers
# ---------------------------------------------------------------------------


EMAIL_REGEX = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,7}\b")
PHONE_REGEX = re.compile(r"(?:\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}")

RESUME_EXTRACTION_PROMPT = """You are an expert HR and technical resume parser.
Extract the structured information from the following resume text and respond ONLY with valid JSON matching the schema below.

JSON Schema:
{
  "candidate_name": string or null,
  "email": string or null,
  "phone": string or null,
  "summary": string or null,
  "skills": [string],
  "experience": [
    {
      "role": string,
      "company": string,
      "location": string or null,
      "start_date": string or null,
      "end_date": string or null,
      "description": string or null,
      "highlights": [string]
    }
  ],
  "education": [
    {
      "degree": string,
      "institution": string,
      "graduation_year": string or null,
      "field_of_study": string or null,
      "details": string or null
    }
  ],
  "projects": [
    {
      "title": string,
      "description": string or null,
      "technologies": [string],
      "link": string or null
    }
  ]
}

Resume Text:
---
{cleaned_text}
---
"""


def build_structuring_prompt(cleaned_text: str) -> str:
    """Format the LLM prompt with the given resume text."""
    return RESUME_EXTRACTION_PROMPT.replace("{cleaned_text}", cleaned_text)


def parse_llm_response(raw_response: str, cleaned_text: str) -> StructuredResume:
    """Parse raw LLM response text (handling code fences or json wrappers) into StructuredResume."""
    text = raw_response.strip()

    # Strip markdown code fences if present
    if text.startswith("```"):
        lines = text.split("\n")
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        text = "\n".join(lines).strip()

    try:
        data = json.loads(text)
        data["raw_text"] = cleaned_text
        return StructuredResume.model_validate(data)
    except (json.JSONDecodeError, Exception) as exc:
        logger.warning(f"Failed to parse LLM JSON response: {exc}. Falling back to heuristic parsing.")
        return heuristic_structure_resume(cleaned_text)


def heuristic_structure_resume(cleaned_text: str) -> StructuredResume:
    """Rule-based heuristic structuring for offline execution, testing, or fallback."""
    if not cleaned_text:
        return StructuredResume(raw_text="")

    lines = [line.strip() for line in cleaned_text.split("\n") if line.strip()]

    # Extract email and phone
    email_match = EMAIL_REGEX.search(cleaned_text)
    phone_match = PHONE_REGEX.search(cleaned_text)

    email = email_match.group(0) if email_match else None
    phone = phone_match.group(0) if phone_match else None

    # Guess candidate name: first line that doesn't contain email or phone and isn't a header
    candidate_name = None
    for line in lines[:5]:
        if email and email in line:
            continue
        if phone and phone in line:
            continue
        if any(h in line.lower() for h in ["resume", "curriculum vitae", "cv", "contact", "summary"]):
            continue
        if len(line.split()) <= 4 and len(line) < 40:
            candidate_name = line
            break

    # Categorize sections by headers
    sections: Dict[str, List[str]] = {
        "summary": [],
        "skills": [],
        "experience": [],
        "education": [],
        "projects": [],
    }
    current_section: Optional[str] = None

    header_map = {
        "skills": "skills",
        "technical skills": "skills",
        "core competencies": "skills",
        "technologies": "skills",
        "experience": "experience",
        "work experience": "experience",
        "employment history": "experience",
        "professional experience": "experience",
        "education": "education",
        "academic background": "education",
        "projects": "projects",
        "personal projects": "projects",
        "key projects": "projects",
        "summary": "summary",
        "professional summary": "summary",
        "objective": "summary",
    }

    for line in lines:
        cleaned_header = line.lower().strip(":").strip()
        if cleaned_header in header_map:
            current_section = header_map[cleaned_header]
            continue

        if current_section:
            sections[current_section].append(line)

    # Process skills
    extracted_skills: List[str] = []
    for line in sections["skills"]:
        # Handle comma or bullet separated skills
        items = re.split(r"[,•|;]\s*", line.lstrip("- "))
        for item in items:
            cleaned_item = item.strip()
            if cleaned_item and len(cleaned_item) < 50:
                extracted_skills.append(cleaned_item)

    # Process experience (basic heuristics)
    experiences: List[ExperienceItem] = []
    exp_lines = sections["experience"]
    i = 0
    while i < len(exp_lines):
        line = exp_lines[i]
        if not line.startswith("-"):
            # Potential role and company
            role = line
            company = "Unknown"
            if " at " in line:
                parts = line.split(" at ", 1)
                role, company = parts[0].strip(), parts[1].strip()
            elif " - " in line:
                parts = line.split(" - ", 1)
                role, company = parts[0].strip(), parts[1].strip()

            bullets = []
            i += 1
            while i < len(exp_lines) and exp_lines[i].startswith("-"):
                bullets.append(exp_lines[i].lstrip("- ").strip())
                i += 1

            experiences.append(
                ExperienceItem(
                    role=role,
                    company=company,
                    highlights=bullets,
                    description="\n".join(bullets) if bullets else None,
                )
            )
        else:
            i += 1

    # Process education
    education_items: List[EducationItem] = []
    edu_lines = sections["education"]
    for line in edu_lines:
        if line.startswith("-"):
            line = line.lstrip("- ").strip()
        if any(deg in line.lower() for deg in ["bachelor", "master", "phd", "b.s.", "m.s.", "b.tech", "degree", "university", "college"]):
            institution = "University"
            degree = line
            if " - " in line:
                parts = line.split(" - ", 1)
                degree, institution = parts[0].strip(), parts[1].strip()
            elif " from " in line.lower():
                parts = re.split(r"\s+from\s+", line, flags=re.IGNORECASE)
                degree, institution = parts[0].strip(), parts[1].strip()
            education_items.append(
                EducationItem(
                    degree=degree,
                    institution=institution,
                )
            )

    # Process projects
    project_items: List[ProjectItem] = []
    proj_lines = sections["projects"]
    j = 0
    while j < len(proj_lines):
        line = proj_lines[j]
        if not line.startswith("-"):
            title = line.strip()
            bullets = []
            j += 1
            while j < len(proj_lines) and proj_lines[j].startswith("-"):
                bullets.append(proj_lines[j].lstrip("- ").strip())
                j += 1
            project_items.append(
                ProjectItem(
                    title=title,
                    description="; ".join(bullets) if bullets else None,
                )
            )
        else:
            j += 1

    summary_text = " ".join(sections["summary"]).strip() if sections["summary"] else None

    return StructuredResume(
        candidate_name=candidate_name,
        email=email,
        phone=phone,
        summary=summary_text,
        skills=extracted_skills,
        experience=experiences,
        education=education_items,
        projects=project_items,
        raw_text=cleaned_text,
    )

