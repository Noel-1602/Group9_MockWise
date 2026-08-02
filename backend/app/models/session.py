import uuid
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional

try:
    from sqlalchemy import Column, String, Integer, Float, Text, JSON, DateTime, ForeignKey
    from sqlalchemy.orm import relationship
    from app.database import Base
    HAVE_SQLALCHEMY = True
except ImportError:
    HAVE_SQLALCHEMY = False
    Base = object

def generate_uuid():
    return str(uuid.uuid4())

if HAVE_SQLALCHEMY:
    class InterviewSession(Base):
        __tablename__ = "sessions"

        id = Column(String, primary_key=True, default=generate_uuid)
        candidate_name = Column(String, nullable=False, default="Candidate")
        target_role = Column(String, nullable=False, default="Software Engineer")
        resume_path = Column(String, nullable=True)
        parsed_resume_json = Column(JSON, nullable=True)
        status = Column(String, nullable=False, default="CREATED")  # CREATED, GENERATING_QUESTIONS, IN_PROGRESS, COMPLETED
        total_questions = Column(Integer, default=6)
        current_question_index = Column(Integer, default=0)
        created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))
        updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None), onupdate=lambda: datetime.now(timezone.utc).replace(tzinfo=None))

        questions = relationship("Question", back_populates="session", cascade="all, delete-orphan", order_by="Question.question_number")
        answers = relationship("Answer", back_populates="session", cascade="all, delete-orphan")
        evaluations = relationship("Evaluation", back_populates="session")
        report = relationship("SessionReport", back_populates="session", uselist=False, cascade="all, delete-orphan")

    class Question(Base):
        __tablename__ = "questions"

        id = Column(String, primary_key=True, default=generate_uuid)
        session_id = Column(String, ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False)
        question_number = Column(Integer, nullable=False)
        question_text = Column(Text, nullable=False)
        category = Column(String, default="technical")
        tts_audio_path = Column(String, nullable=True)
        created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))

        session = relationship("InterviewSession", back_populates="questions")
        answer = relationship("Answer", back_populates="question", uselist=False, cascade="all, delete-orphan")
        evaluation = relationship("Evaluation", back_populates="question", uselist=False)

    class Answer(Base):
        __tablename__ = "answers"

        id = Column(String, primary_key=True, default=generate_uuid)
        session_id = Column(String, ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False)
        question_id = Column(String, ForeignKey("questions.id", ondelete="CASCADE"), nullable=False)
        audio_path = Column(String, nullable=True)
        transcript_text = Column(Text, nullable=False)
        duration_seconds = Column(Float, default=0.0)
        submitted_at = Column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))

        session = relationship("InterviewSession", back_populates="answers")
        question = relationship("Question", back_populates="answer")
        evaluation = relationship("Evaluation", back_populates="answer", uselist=False, cascade="all, delete-orphan")

    class Evaluation(Base):
        __tablename__ = "evaluations"

        id = Column(String, primary_key=True, default=generate_uuid)
        session_id = Column(String, ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False)
        question_id = Column(String, ForeignKey("questions.id", ondelete="CASCADE"), nullable=False)
        answer_id = Column(String, ForeignKey("answers.id", ondelete="CASCADE"), nullable=False)
        overall_score = Column(Integer, nullable=False)
        clarity_score = Column(Integer, default=7)
        relevance_score = Column(Integer, default=7)
        communication_score = Column(Integer, default=7)
        filler_word_count = Column(Integer, default=0)
        feedback_text = Column(Text, nullable=False)
        strengths_json = Column(JSON, default=lambda: [])
        improvements_json = Column(JSON, default=lambda: [])
        created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))

        session = relationship("InterviewSession", back_populates="evaluations")
        question = relationship("Question", back_populates="evaluation")
        answer = relationship("Answer", back_populates="evaluation")

    class SessionReport(Base):
        __tablename__ = "session_reports"

        id = Column(String, primary_key=True, default=generate_uuid)
        session_id = Column(String, ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False, unique=True)
        overall_score = Column(Integer, nullable=False)
        strengths_summary = Column(Text, nullable=False)
        weakness_summary = Column(Text, nullable=False)
        detailed_report_json = Column(JSON, nullable=False)
        compiled_at = Column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))

        session = relationship("InterviewSession", back_populates="report")

else:
    # Pure Python dataclass fallback representations when SQLAlchemy is not installed
    class InterviewSession:
        def __init__(self, **kwargs):
            self.id = kwargs.get("id", generate_uuid())
            self.candidate_name = kwargs.get("candidate_name", "Candidate")
            self.target_role = kwargs.get("target_role", "Software Engineer")
            self.resume_path = kwargs.get("resume_path")
            self.parsed_resume_json = kwargs.get("parsed_resume_json")
            if self.parsed_resume_json is None:
                self.parsed_resume_json = {}
            self.status = kwargs.get("status", "CREATED")
            self.total_questions = kwargs.get("total_questions", 6)
            self.current_question_index = kwargs.get("current_question_index", 0)
            self.created_at = kwargs.get("created_at")
            if self.created_at is None:
                self.created_at = datetime.now(timezone.utc).replace(tzinfo=None)
            self.questions = kwargs.get("questions")
            if self.questions is None:
                self.questions = []
            self.answers = kwargs.get("answers")
            if self.answers is None:
                self.answers = []
            self.evaluations = kwargs.get("evaluations")
            if self.evaluations is None:
                self.evaluations = []
            self.report = kwargs.get("report")

    class Question:
        def __init__(self, **kwargs):
            self.id = kwargs.get("id", generate_uuid())
            self.session_id = kwargs.get("session_id")
            self.question_number = kwargs.get("question_number", 1)
            self.question_text = kwargs.get("question_text", "")
            self.category = kwargs.get("category", "technical")
            self.tts_audio_path = kwargs.get("tts_audio_path")
            self.created_at = kwargs.get("created_at")
            if self.created_at is None:
                self.created_at = datetime.now(timezone.utc).replace(tzinfo=None)
            self.answer = kwargs.get("answer")
            self.evaluation = kwargs.get("evaluation")

    class Answer:
        def __init__(self, **kwargs):
            self.id = kwargs.get("id", generate_uuid())
            self.session_id = kwargs.get("session_id")
            self.question_id = kwargs.get("question_id")
            self.audio_path = kwargs.get("audio_path")
            self.transcript_text = kwargs.get("transcript_text", "")
            self.duration_seconds = kwargs.get("duration_seconds", 0.0)
            self.submitted_at = kwargs.get("submitted_at")
            if self.submitted_at is None:
                self.submitted_at = datetime.now(timezone.utc).replace(tzinfo=None)

    class Evaluation:
        def __init__(self, **kwargs):
            self.id = kwargs.get("id", generate_uuid())
            self.session_id = kwargs.get("session_id")
            self.question_id = kwargs.get("question_id")
            self.answer_id = kwargs.get("answer_id")
            self.overall_score = kwargs.get("overall_score", 70)
            self.clarity_score = kwargs.get("clarity_score", 70)
            self.relevance_score = kwargs.get("relevance_score", 70)
            self.communication_score = kwargs.get("communication_score", 70)
            self.filler_word_count = kwargs.get("filler_word_count", 0)
            self.feedback_text = kwargs.get("feedback_text", "")
            self.strengths_json = kwargs.get("strengths_json")
            if self.strengths_json is None:
                self.strengths_json = []
            self.improvements_json = kwargs.get("improvements_json")
            if self.improvements_json is None:
                self.improvements_json = []

    class SessionReport:
        def __init__(self, **kwargs):
            self.id = kwargs.get("id", generate_uuid())
            self.session_id = kwargs.get("session_id")
            self.overall_score = kwargs.get("overall_score", 70)
            self.strengths_summary = kwargs.get("strengths_summary", "")
            self.weakness_summary = kwargs.get("weakness_summary", "")
            self.detailed_report_json = kwargs.get("detailed_report_json")
            if self.detailed_report_json is None:
                self.detailed_report_json = {}
            self.compiled_at = kwargs.get("compiled_at")
            if self.compiled_at is None:
                self.compiled_at = datetime.now(timezone.utc).replace(tzinfo=None)
