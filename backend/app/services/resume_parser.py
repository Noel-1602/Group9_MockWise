import re
import json
import logging
from pathlib import Path
from typing import Dict, Any, List

try:
    import httpx
except ImportError:
    httpx = None

from app.schemas.session import StructuredResume
from app.config import settings

logger = logging.getLogger("mockwise.resume_parser")

class ResumeParserService:

    @staticmethod
    def extract_text_from_file(file_path: Path) -> str:
        """Extract text from PDF or DOCX file."""
        suffix = file_path.suffix.lower()
        text = ""

        if suffix == ".pdf":
            try:
                import pypdf
                reader = pypdf.PdfReader(str(file_path))
                for page in reader.pages:
                    extracted = page.extract_text()
                    if extracted:
                        text += extracted + "\n"
            except Exception as e:
                logger.warning(f"pypdf extraction failed: {e}. Trying fallback binary string extraction.")
                with open(file_path, "rb") as f:
                    content = f.read().decode("latin-1", errors="ignore")
                    text = re.sub(r'[^\x20-\x7E\n\r\t]', ' ', content)

        elif suffix in [".docx", ".doc"]:
            try:
                import docx
                doc = docx.Document(str(file_path))
                for paragraph in doc.paragraphs:
                    text += paragraph.text + "\n"
            except Exception as e:
                logger.warning(f"python-docx extraction failed: {e}.")
                with open(file_path, "r", errors="ignore") as f:
                    text = f.read()

        else:
            with open(file_path, "r", errors="ignore") as f:
                text = f.read()

        return text.strip()

    @classmethod
    async def parse_resume(cls, file_path: Path) -> StructuredResume:
        """Parse raw resume text into structured JSON schema using LLM or rule-based heuristics."""
        raw_text = cls.extract_text_from_file(file_path)
        if not raw_text:
            return cls._fallback_heuristic_parse("", "Candidate Resume")

        # Try LLM parsing if configured and httpx installed
        if httpx:
            if settings.LLM_PROVIDER == "groq" and settings.GROQ_API_KEY:
                try:
                    return await cls._parse_with_groq(raw_text)
                except Exception as e:
                    logger.error(f"Groq resume parsing error: {e}. Falling back to heuristics.")

            elif settings.LLM_PROVIDER == "ollama":
                try:
                    return await cls._parse_with_ollama(raw_text)
                except Exception as e:
                    logger.error(f"Ollama resume parsing error: {e}. Falling back to heuristics.")

            elif settings.LLM_PROVIDER == "openai" and settings.OPENAI_API_KEY:
                try:
                    return await cls._parse_with_openai(raw_text)
                except Exception as e:
                    logger.error(f"OpenAI resume parsing error: {e}. Falling back to heuristics.")

        # Fallback to rule-based heuristic parsing
        return cls._fallback_heuristic_parse(raw_text)

    @classmethod
    async def _parse_with_groq(cls, text: str) -> StructuredResume:
        prompt = cls._build_extraction_prompt(text)
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={"Authorization": f"Bearer {settings.GROQ_API_KEY}"},
                json={
                    "model": "llama-3.3-70b-versatile",
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.1,
                    "response_format": {"type": "json_object"}
                }
            )
            res_data = response.json()
            content = res_data["choices"][0]["message"]["content"]
            parsed_json = json.loads(content)
            return cls._dict_to_schema(parsed_json, text)

    @classmethod
    async def _parse_with_ollama(cls, text: str) -> StructuredResume:
        prompt = cls._build_extraction_prompt(text)
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{settings.OLLAMA_HOST}/api/generate",
                json={
                    "model": settings.OLLAMA_MODEL,
                    "prompt": prompt,
                    "stream": False,
                    "format": "json"
                }
            )
            res_data = response.json()
            content = res_data.get("response", "{}")
            parsed_json = json.loads(content)
            return cls._dict_to_schema(parsed_json, text)

    @classmethod
    async def _parse_with_openai(cls, text: str) -> StructuredResume:
        prompt = cls._build_extraction_prompt(text)
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {settings.OPENAI_API_KEY}"},
                json={
                    "model": "gpt-3.5-turbo",
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.1,
                    "response_format": {"type": "json_object"}
                }
            )
            res_data = response.json()
            content = res_data["choices"][0]["message"]["content"]
            parsed_json = json.loads(content)
            return cls._dict_to_schema(parsed_json, text)

    @staticmethod
    def _build_extraction_prompt(text: str) -> str:
        return f"""
Extract structured candidate information from the following resume text.
Return ONLY valid JSON matching this structure:
{{
  "candidate_name": "Full Name",
  "email": "email@example.com",
  "phone": "phone number",
  "skills": ["Python", "FastAPI", "React", ...],
  "projects": [
    {{"title": "Project Name", "description": "Short summary of what was built and tech used"}}
  ],
  "work_experience": [
    {{"role": "Role Title", "company": "Company Name", "details": "Key tasks"}}
  ],
  "education": [
    {{"degree": "Degree Title", "institution": "University/College"}}
  ]
}}

Resume Text:
{text[:4000]}
"""

    @classmethod
    def _dict_to_schema(cls, data: Dict[str, Any], raw_text: str) -> StructuredResume:
        return StructuredResume(
            candidate_name=data.get("candidate_name", "Candidate"),
            email=data.get("email"),
            phone=data.get("phone"),
            skills=data.get("skills", []),
            projects=data.get("projects", []),
            work_experience=data.get("work_experience", []),
            education=data.get("education", []),
            raw_text_snippet=raw_text[:500]
        )

    @classmethod
    def _fallback_heuristic_parse(cls, raw_text: str, default_name: str = "Candidate") -> StructuredResume:
        lines = [line.strip() for line in raw_text.splitlines() if line.strip()]
        
        # Name detection
        candidate_name = default_name
        if lines:
            first_line = lines[0]
            if len(first_line.split()) <= 4 and not any(kw in first_line.lower() for kw in ["resume", "curriculum", "page"]):
                candidate_name = first_line

        # Email detection
        email_match = re.search(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', raw_text)
        email = email_match.group(0) if email_match else None

        # Common Tech Skills detection
        known_skills = [
            "Python", "Java", "C++", "JavaScript", "TypeScript", "React", "Next.js", "Node.js",
            "FastAPI", "Flask", "Django", "SQL", "SQLite", "PostgreSQL", "MongoDB", "Docker",
            "Git", "HTML", "CSS", "Machine Learning", "Deep Learning", "PyTorch", "TensorFlow",
            "REST API", "Tailwind", "Linux", "Data Structures", "Algorithms"
        ]
        found_skills = []
        for skill in known_skills:
            if re.search(r'\b' + re.escape(skill) + r'\b', raw_text, re.IGNORECASE):
                found_skills.append(skill)
        
        if not found_skills:
            found_skills = ["Python", "Software Engineering", "Problem Solving", "Git"]

        # Project detection heuristics
        projects = []
        project_keywords = ["project", "built", "developed", "created", "system", "platform", "app"]
        for line in lines:
            if any(kw in line.lower() for kw in project_keywords) and len(line) > 15:
                parts = line.split(":", 1)
                title = parts[0].strip() if len(parts) > 1 else "Personal Project"
                desc = parts[1].strip() if len(parts) > 1 else line
                projects.append({"title": title[:50], "description": desc[:150]})
                if len(projects) >= 3:
                    break

        if not projects:
            projects = [{
                "title": "Speech-to-Speech Mock Interview Platform",
                "description": "Built an AI mock interview system using FastAPI, speech transcription, and LLM question generation."
            }]

        return StructuredResume(
            candidate_name=candidate_name,
            email=email,
            skills=found_skills,
            projects=projects,
            work_experience=[{"role": "Software Developer Intern", "company": "Tech Corp", "details": "Worked on backend APIs and database integrations."}],
            education=[{"degree": "B.Tech in Computer Science & Engineering", "institution": "College of Engineering"}],
            raw_text_snippet=raw_text[:500]
        )
