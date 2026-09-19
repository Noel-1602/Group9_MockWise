from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field

from app.models import SessionStatus


# =============================================================================
# Request Schemas
# =============================================================================

class SessionCreateRequest(BaseModel):
    """Payload for creating a new interview session."""
    candidate_name: Optional[str] = Field(default=None, description="Name of the candidate")
    resume_filename: Optional[str] = Field(default=None, description="Filename of the uploaded resume")


class AnswerSubmitRequest(BaseModel):
    """Payload for submitting an answer to a question."""
    transcript_text: Optional[str] = Field(default=None, description="Transcribed audio or text answer")
    score: Optional[float] = Field(default=None, description="Evaluation score (e.g. 0.0 - 10.0)")
    feedback_text: Optional[str] = Field(default=None, description="Evaluator feedback on the answer")
    evaluation_json: Optional[str] = Field(default=None, description="Detailed JSON evaluation payload")


# =============================================================================
# Response Schemas (ORM compatible with from_attributes = True)
# =============================================================================

class ResumeResponse(BaseModel):
    """Schema representing parsed resume data associated with a session."""
    model_config = ConfigDict(from_attributes=True)

    id: str
    session_id: str
    skills_json: Optional[str] = None
    projects_json: Optional[str] = None
    experience_json: Optional[str] = None
    education_json: Optional[str] = None
    raw_text: Optional[str] = None
    created_at: datetime


class AnswerResponse(BaseModel):
    """Schema representing an answer given to a question."""
    model_config = ConfigDict(from_attributes=True)

    id: str
    question_id: str
    transcript_text: Optional[str] = None
    score: Optional[float] = None
    feedback_text: Optional[str] = None
    evaluation_json: Optional[str] = None
    created_at: datetime


class QuestionResponse(BaseModel):
    """Schema representing an interview question."""
    model_config = ConfigDict(from_attributes=True)

    id: str
    session_id: str
    question_index: int
    question_text: str
    question_type: str
    created_at: datetime
    answer: Optional[AnswerResponse] = None


class SessionSummary(BaseModel):
    """Schema representing computed summary metrics for an interview session."""
    total_questions: int = Field(default=0, description="Total number of questions in the session")
    answered_count: int = Field(default=0, description="Number of answered questions")
    average_score: Optional[float] = Field(default=None, description="Average score across answered questions, or None")
    resume_specific_count: int = Field(default=0, description="Number of resume-specific questions")
    general_count: int = Field(default=0, description="Number of general questions")


class SessionResponse(BaseModel):
    """Schema representing an interview session with its resume, questions, and summary metrics."""
    model_config = ConfigDict(from_attributes=True)

    id: str
    candidate_name: Optional[str] = None
    resume_filename: Optional[str] = None
    status: SessionStatus
    created_at: datetime
    resume: Optional[ResumeResponse] = None
    questions: List[QuestionResponse] = []
    total_questions: int = 0
    answered_count: int = 0
    average_score: Optional[float] = None
    resume_specific_count: int = 0
    general_count: int = 0
