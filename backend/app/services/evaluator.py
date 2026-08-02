import re
import json
import logging
from typing import Dict, Any, List

try:
    import httpx
except ImportError:
    httpx = None

from app.schemas.session import EvaluationResponse
from app.config import settings

logger = logging.getLogger("mockwise.evaluator")

FILLER_WORDS = ["um", "uh", "like", "you know", "basically", "actually", "sort of", "kind of", "mean", "i guess"]

class AnswerEvaluatorService:

    @classmethod
    async def evaluate_answer(
        cls,
        question_text: str,
        transcript_text: str,
        category: str = "technical"
    ) -> Dict[str, Any]:
        """
        Evaluate candidate's transcribed answer against the interview rubric.
        Returns dict with: overall_score, clarity_score, relevance_score, communication_score,
        filler_word_count, feedback_text, strengths, improvements.
        """
        filler_count = cls.count_filler_words(transcript_text)

        if httpx:
            if settings.LLM_PROVIDER == "groq" and settings.GROQ_API_KEY:
                try:
                    return await cls._evaluate_with_groq(question_text, transcript_text, category, filler_count)
                except Exception as e:
                    logger.error(f"Groq evaluation failed: {e}. Falling back to rubric rules.")

            elif settings.LLM_PROVIDER == "ollama":
                try:
                    return await cls._evaluate_with_ollama(question_text, transcript_text, category, filler_count)
                except Exception as e:
                    logger.error(f"Ollama evaluation failed: {e}. Falling back to rubric rules.")

            elif settings.LLM_PROVIDER == "openai" and settings.OPENAI_API_KEY:
                try:
                    return await cls._evaluate_with_openai(question_text, transcript_text, category, filler_count)
                except Exception as e:
                    logger.error(f"OpenAI evaluation failed: {e}. Falling back to rubric rules.")

        # Heuristic Rubric Evaluator Fallback
        return cls._heuristic_rubric_evaluation(question_text, transcript_text, category, filler_count)

    @staticmethod
    def count_filler_words(text: str) -> int:
        text_lower = text.lower()
        count = 0
        for word in FILLER_WORDS:
            pattern = r'\b' + re.escape(word) + r'\b'
            count += len(re.findall(pattern, text_lower))
        return count

    @classmethod
    async def _evaluate_with_groq(cls, q: str, a: str, cat: str, filler_cnt: int) -> Dict[str, Any]:
        prompt = cls._build_eval_prompt(q, a, cat, filler_cnt)
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={"Authorization": f"Bearer {settings.GROQ_API_KEY}"},
                json={
                    "model": "llama-3.3-70b-versatile",
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.2,
                    "response_format": {"type": "json_object"}
                }
            )
            res_data = response.json()
            content = res_data["choices"][0]["message"]["content"]
            return json.loads(content)

    @classmethod
    async def _evaluate_with_ollama(cls, q: str, a: str, cat: str, filler_cnt: int) -> Dict[str, Any]:
        prompt = cls._build_eval_prompt(q, a, cat, filler_cnt)
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
            return json.loads(content)

    @classmethod
    async def _evaluate_with_openai(cls, q: str, a: str, cat: str, filler_cnt: int) -> Dict[str, Any]:
        prompt = cls._build_eval_prompt(q, a, cat, filler_cnt)
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {settings.OPENAI_API_KEY}"},
                json={
                    "model": "gpt-3.5-turbo",
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.2,
                    "response_format": {"type": "json_object"}
                }
            )
            res_data = response.json()
            content = res_data["choices"][0]["message"]["content"]
            return json.loads(content)

    @staticmethod
    def _build_eval_prompt(q: str, a: str, cat: str, filler_cnt: int) -> str:
        return f"""
Evaluate the candidate's spoken interview response according to this scoring rubric:
1. Clarity & Structure (1-10)
2. Relevance & Depth (1-10)
3. Communication & Tone (1-10)

Question ({cat}): {q}
Candidate Response: {a}
Filler Word Count Detected: {filler_cnt}

Return JSON strictly formatted as:
{{
  "overall_score": 8,
  "clarity_score": 8,
  "relevance_score": 8,
  "communication_score": 8,
  "filler_word_count": {filler_cnt},
  "feedback_text": "Short qualitative assessment paragraph...",
  "strengths": ["Clear technical explanation", "Good structure"],
  "improvements": ["Reduce filler words", "Elaborate more on design trade-offs"]
}}
"""

    @classmethod
    def _heuristic_rubric_evaluation(cls, q: str, a: str, cat: str, filler_cnt: int) -> Dict[str, Any]:
        word_count = len(a.split())
        
        if word_count < 10:
            clarity = 5
            relevance = 4
            communication = 5
            feedback = "The answer was very brief. Try elaborating with specific technical details and examples."
            strengths = ["Responded to the prompt"]
            improvements = ["Provide a more comprehensive explanation", "Include concrete examples from past projects"]
        elif word_count < 30:
            clarity = 7
            relevance = 7
            communication = 7
            feedback = "Good direct response. Elaborating slightly more on key technical principles would improve the answer."
            strengths = ["Direct and concise answer", "Relevant topic coverage"]
            improvements = ["Elaborate further on architectural trade-offs", "Lower reliance on filler phrases"]
        else:
            clarity = 8
            relevance = 9
            communication = 8
            feedback = "Strong, well-structured response demonstrating technical understanding and project experience."
            strengths = ["Comprehensive explanation", "Clear technical focus", "Structured narrative"]
            improvements = ["Maintain steady pacing", "Highlight measurable outcomes"]

        if filler_cnt > 3:
            communication = max(4, communication - 2)
            improvements.append(f"Detected {filler_cnt} filler words. Practice pausing briefly instead of using filler sounds.")

        overall = round((clarity * 0.3 + relevance * 0.4 + communication * 0.3) * 10)

        return {
            "overall_score": overall,
            "clarity_score": clarity * 10,
            "relevance_score": relevance * 10,
            "communication_score": communication * 10,
            "filler_word_count": filler_cnt,
            "feedback_text": feedback,
            "strengths": strengths,
            "improvements": improvements
        }
