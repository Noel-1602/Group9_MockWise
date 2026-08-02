from typing import List, Optional, Dict, Any
from datetime import datetime

try:
    from pydantic import BaseModel, Field
except ImportError:
    class BaseModel:
        def __init__(self, **kwargs):
            for k, v in kwargs.items():
                setattr(self, k, v)
        def model_dump(self):
            res = {}
            for k, v in self.__dict__.items():
                if k.startswith('_'):
                    continue
                if isinstance(v, BaseModel):
                    res[k] = v.model_dump()
                elif isinstance(v, list):
                    res[k] = [i.model_dump() if isinstance(i, BaseModel) else i for i in v]
                else:
                    res[k] = v
            return res
        def dict(self):
            return self.model_dump()
        @classmethod
        def model_validate(cls, obj):
            if isinstance(obj, dict):
                return cls(**obj)
            return obj

    def Field(default=None, **kwargs):
        return default

# --- Parsed Resume Schemas ---
class StructuredResume(BaseModel):
    candidate_name: str = "Candidate"
    email: Optional[str] = None
    phone: Optional[str] = None
    skills: List[str] = []
    projects: List[Dict[str, str]] = []  # [{"title": "...", "description": "..."}]
    work_experience: List[Dict[str, str]] = []  # [{"role": "...", "company": "...", "details": "..."}]
    education: List[Dict[str, str]] = []  # [{"degree": "...", "institution": "..."}]
    raw_text_snippet: Optional[str] = None

class ResumeParseResponse(BaseModel):
    status: str = "success"
    parsed_resume: StructuredResume

# --- Question Schemas ---
class QuestionResponse(BaseModel):
    id: str
    session_id: str
    question_number: int
    question_text: str
    category: str
    audio_url: Optional[str] = None
    created_at: Any = None

    class Config:
        from_attributes = True

# --- Answer & Evaluation Schemas ---
class AnswerSubmitResponse(BaseModel):
    answer_id: str
    question_id: str
    transcript_text: str
    evaluation_score: int
    clarity_score: int
    relevance_score: int
    communication_score: int
    filler_word_count: int
    feedback_text: str
    strengths: List[str] = []
    improvements: List[str] = []
    next_question: Optional[QuestionResponse] = None
    session_completed: bool = False

class EvaluationResponse(BaseModel):
    id: str
    question_id: str
    answer_id: str
    overall_score: int
    clarity_score: int
    relevance_score: int
    communication_score: int
    filler_word_count: int
    feedback_text: str
    strengths_json: List[str] = []
    improvements_json: List[str] = []

    class Config:
        from_attributes = True

# --- Session Schemas ---
class SessionCreateRequest(BaseModel):
    candidate_name: Optional[str] = "Candidate"
    target_role: str = "Software Engineer"
    total_questions: int = 6

class SessionDetailResponse(BaseModel):
    id: str
    candidate_name: str
    target_role: str
    status: str
    total_questions: int
    current_question_index: int
    created_at: Any = None
    parsed_resume: Optional[StructuredResume] = None
    questions: List[QuestionResponse] = []
    current_question: Optional[QuestionResponse] = None

    class Config:
        from_attributes = True

# --- Report Schemas ---
class QuestionAnswerReportItem(BaseModel):
    question_number: int
    question_text: str
    category: str
    transcript_text: str
    score: int
    clarity_score: int
    relevance_score: int
    communication_score: int
    filler_words: int
    feedback: str

class SessionReportResponse(BaseModel):
    report_id: str
    session_id: str
    candidate_name: str
    target_role: str
    overall_score: int
    strengths_summary: str
    weakness_summary: str
    total_questions_answered: int
    detailed_breakdown: List[QuestionAnswerReportItem] = []
    compiled_at: Any = None

    class Config:
        from_attributes = True
