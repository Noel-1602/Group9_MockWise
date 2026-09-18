import enum
import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, DateTime, Enum, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import relationship

from app.database import Base


def generate_uuid() -> str:
    """Generate a UUID4 hex string for primary keys."""
    return str(uuid.uuid4())


def get_utc_now() -> datetime:
    """Return the current UTC timestamp."""
    return datetime.now(timezone.utc)


class SessionStatus(str, enum.Enum):
    in_progress = "in_progress"
    completed = "completed"


class InterviewSession(Base):
    __tablename__ = "interview_sessions"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    candidate_name = Column(String, nullable=True)
    resume_filename = Column(String, nullable=True)
    status = Column(
        Enum(SessionStatus, values_callable=lambda obj: [e.value for e in obj]),
        nullable=False,
        default=SessionStatus.in_progress,
    )
    created_at = Column(DateTime(timezone=True), nullable=False, default=get_utc_now)

    # 1:1 relationship with Resume (cascades delete)
    resume = relationship(
        "Resume",
        back_populates="session",
        uselist=False,
        cascade="all, delete-orphan",
    )

    # 1:N relationship with Question (cascades delete)
    questions = relationship(
        "Question",
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="Question.question_index",
    )


class Resume(Base):
    __tablename__ = "resumes"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    session_id = Column(
        String(36),
        ForeignKey("interview_sessions.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    skills_json = Column(Text, nullable=True)
    projects_json = Column(Text, nullable=True)
    experience_json = Column(Text, nullable=True)
    education_json = Column(Text, nullable=True)
    raw_text = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=get_utc_now)

    # Relationship back to InterviewSession
    session = relationship("InterviewSession", back_populates="resume")


class Question(Base):
    __tablename__ = "questions"
    __table_args__ = (
        UniqueConstraint("session_id", "question_index", name="uq_session_question_index"),
    )

    id = Column(String(36), primary_key=True, default=generate_uuid)
    session_id = Column(
        String(36),
        ForeignKey("interview_sessions.id", ondelete="CASCADE"),
        nullable=False,
    )
    question_index = Column(Integer, nullable=False)
    question_text = Column(Text, nullable=False)
    question_type = Column(String, nullable=False, default="general")
    created_at = Column(DateTime(timezone=True), nullable=False, default=get_utc_now)

    # Relationship back to InterviewSession
    session = relationship("InterviewSession", back_populates="questions")

    # 1:0..1 relationship with Answer (cascades delete)
    answer = relationship(
        "Answer",
        back_populates="question",
        uselist=False,
        cascade="all, delete-orphan",
    )


class Answer(Base):
    __tablename__ = "answers"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    question_id = Column(
        String(36),
        ForeignKey("questions.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    transcript_text = Column(Text, nullable=True)
    score = Column(Float, nullable=True)
    feedback_text = Column(Text, nullable=True)
    evaluation_json = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=get_utc_now)

    # Relationship back to Question
    question = relationship("Question", back_populates="answer")
