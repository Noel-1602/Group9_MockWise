import json
import logging
from typing import List, Dict, Any

try:
    import httpx
except ImportError:
    httpx = None

from app.schemas.session import StructuredResume
from app.config import settings

logger = logging.getLogger("mockwise.question_generator")

class QuestionGeneratorService:

    @classmethod
    async def generate_questions(
        cls,
        resume: StructuredResume,
        target_role: str,
        num_questions: int = 6
    ) -> List[Dict[str, str]]:
        """
        Generate a list of interview questions tailored to the resume and target role.
        Each question dict: {"question_text": "...", "category": "resume_specific" | "technical" | "behavioral"}
        """
        if httpx:
            if settings.LLM_PROVIDER == "groq" and settings.GROQ_API_KEY:
                try:
                    return await cls._generate_with_groq(resume, target_role, num_questions)
                except Exception as e:
                    logger.error(f"Groq question generation failed: {e}. Falling back to templates.")

            elif settings.LLM_PROVIDER == "ollama":
                try:
                    return await cls._generate_with_ollama(resume, target_role, num_questions)
                except Exception as e:
                    logger.error(f"Ollama question generation failed: {e}. Falling back to templates.")

            elif settings.LLM_PROVIDER == "openai" and settings.OPENAI_API_KEY:
                try:
                    return await cls._generate_with_openai(resume, target_role, num_questions)
                except Exception as e:
                    logger.error(f"OpenAI question generation failed: {e}. Falling back to templates.")

        # Heuristic fallback generator
        return cls._generate_fallback_questions(resume, target_role, num_questions)

    @classmethod
    async def _generate_with_groq(cls, resume: StructuredResume, target_role: str, num_questions: int) -> List[Dict[str, str]]:
        prompt = cls._build_question_prompt(resume, target_role, num_questions)
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={"Authorization": f"Bearer {settings.GROQ_API_KEY}"},
                json={
                    "model": "llama-3.3-70b-versatile",
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.5,
                    "response_format": {"type": "json_object"}
                }
            )
            res_data = response.json()
            content = res_data["choices"][0]["message"]["content"]
            parsed = json.loads(content)
            return parsed.get("questions", [])

    @classmethod
    async def _generate_with_ollama(cls, resume: StructuredResume, target_role: str, num_questions: int) -> List[Dict[str, str]]:
        prompt = cls._build_question_prompt(resume, target_role, num_questions)
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
            parsed = json.loads(content)
            return parsed.get("questions", [])

    @classmethod
    async def _generate_with_openai(cls, resume: StructuredResume, target_role: str, num_questions: int) -> List[Dict[str, str]]:
        prompt = cls._build_question_prompt(resume, target_role, num_questions)
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {settings.OPENAI_API_KEY}"},
                json={
                    "model": "gpt-3.5-turbo",
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.5,
                    "response_format": {"type": "json_object"}
                }
            )
            res_data = response.json()
            content = res_data["choices"][0]["message"]["content"]
            parsed = json.loads(content)
            return parsed.get("questions", [])

    @staticmethod
    def _build_question_prompt(resume: StructuredResume, target_role: str, num_questions: int) -> str:
        return f"""
You are an expert technical interviewer conducting a mock interview for a candidate applying for: {target_role}.

Candidate Profile:
- Name: {resume.candidate_name}
- Skills: {", ".join(resume.skills)}
- Projects: {json.dumps(resume.projects)}
- Work Experience: {json.dumps(resume.work_experience)}

Generate exactly {num_questions} interview questions tailored to this candidate.
Return JSON format:
{{
  "questions": [
    {{"question_text": "...", "category": "resume_specific"}},
    {{"question_text": "...", "category": "technical"}},
    {{"question_text": "...", "category": "behavioral"}}
  ]
}}
Ensure the questions explicitly reference named projects or skills from their resume where applicable.
"""

    @classmethod
    def _generate_fallback_questions(cls, resume: StructuredResume, target_role: str, num_questions: int) -> List[Dict[str, str]]:
        questions = []
        skills_str = ", ".join(resume.skills[:4]) if resume.skills else "software engineering"
        
        # 1. Introduction
        questions.append({
            "question_text": f"Welcome to your interview for the {target_role} position. Could you introduce yourself and walk us through your background in {skills_str}?",
            "category": "behavioral"
        })

        # 2. Project specific 1
        if resume.projects and len(resume.projects) > 0:
            proj = resume.projects[0]
            title = proj.get("title", "your key project")
            questions.append({
                "question_text": f"In your resume, you highlighted the project '{title}'. Could you explain the architecture of this project and what key technical challenges you faced?",
                "category": "resume_specific"
            })
        else:
            questions.append({
                "question_text": f"Can you describe a challenging technical project you built recently using {skills_str}? What was your specific contribution?",
                "category": "resume_specific"
            })

        # 3. Project specific 2 / Technical
        if resume.projects and len(resume.projects) > 1:
            proj2 = resume.projects[1]
            title2 = proj2.get("title", "another project")
            questions.append({
                "question_text": f"Tell me more about '{title2}'. How did you validate performance and ensure scalability in that implementation?",
                "category": "resume_specific"
            })
        elif resume.skills:
            primary_skill = resume.skills[0]
            questions.append({
                "question_text": f"You mentioned proficiency in {primary_skill}. How do you approach debugging complex runtime issues or performance bottlenecks in {primary_skill} applications?",
                "category": "technical"
            })
        else:
            questions.append({
                "question_text": "How do you design scalable REST APIs and handle state management in web application backends?",
                "category": "technical"
            })

        # 4. Domain Technical Question
        questions.append({
            "question_text": f"As a {target_role}, how do you ensure code maintainability, write unit tests, and maintain CI/CD pipelines in a team setting?",
            "category": "technical"
        })

        # 5. Behavioral / Problem Solving
        questions.append({
            "question_text": "Describe a situation where a technical project did not go according to plan or deadlines were tight. How did you handle it and what did you learn?",
            "category": "behavioral"
        })

        # 6. Conclusion / Role Fit
        questions.append({
            "question_text": f"Why are you interested in the {target_role} role, and what are your long-term goals for professional growth in engineering?",
            "category": "behavioral"
        })

        return questions[:num_questions]
