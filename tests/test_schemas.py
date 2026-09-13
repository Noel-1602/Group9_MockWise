import pytest
from datetime import datetime, timezone

from app.database import Base, engine, SessionLocal
from app.models import Answer, InterviewSession, Question, Resume, SessionStatus
from app.schemas import (
    AnswerResponse,
    AnswerSubmitRequest,
    QuestionResponse,
    ResumeResponse,
    SessionCreateRequest,
    SessionResponse,
)


@pytest.fixture(autouse=True)
def setup_database():
    """Create all tables before each test and tear down after."""
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def db():
    """Provide a clean database session."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def test_session_create_request_validation():
    """Verify SessionCreateRequest with defaults and custom values."""
    req_default = SessionCreateRequest()
    assert req_default.candidate_name is None
    assert req_default.resume_filename is None

    req_custom = SessionCreateRequest(
        candidate_name="Jane Doe",
        resume_filename="jane_doe.pdf",
    )
    assert req_custom.candidate_name == "Jane Doe"
    assert req_custom.resume_filename == "jane_doe.pdf"


def test_answer_submit_request_validation():
    """Verify AnswerSubmitRequest field parsing."""
    req = AnswerSubmitRequest(
        transcript_text="Python supports multiple inheritance.",
        score=9.0,
        feedback_text="Excellent answer.",
    )
    assert req.transcript_text == "Python supports multiple inheritance."
    assert req.score == 9.0
    assert req.feedback_text == "Excellent answer."


def test_orm_models_to_pydantic_schemas(db):
    """Verify SessionResponse, QuestionResponse, AnswerResponse, ResumeResponse from ORM models."""
    session_orm = InterviewSession(
        candidate_name="Alice Candidate",
        resume_filename="alice.pdf",
        status=SessionStatus.in_progress,
    )
    db.add(session_orm)
    db.commit()
    db.refresh(session_orm)

    resume_orm = Resume(
        session_id=session_orm.id,
        skills_json='["FastAPI", "SQLAlchemy"]',
        raw_text="Alice's resume text",
    )
    q1_orm = Question(
        session_id=session_orm.id,
        question_index=1,
        question_text="What is ASGI?",
        question_type="technical",
    )
    db.add_all([resume_orm, q1_orm])
    db.commit()
    db.refresh(q1_orm)

    a1_orm = Answer(
        question_id=q1_orm.id,
        transcript_text="Asynchronous Server Gateway Interface",
        score=9.5,
        feedback_text="Accurate definition",
    )
    db.add(a1_orm)
    db.commit()
    db.refresh(session_orm)

    # Test ResumeResponse from ORM
    resume_dto = ResumeResponse.model_validate(session_orm.resume)
    assert resume_dto.id == resume_orm.id
    assert resume_dto.session_id == session_orm.id
    assert resume_dto.skills_json == '["FastAPI", "SQLAlchemy"]'
    assert resume_dto.raw_text == "Alice's resume text"

    # Test AnswerResponse from ORM
    answer_dto = AnswerResponse.model_validate(q1_orm.answer)
    assert answer_dto.id == a1_orm.id
    assert answer_dto.question_id == q1_orm.id
    assert answer_dto.score == 9.5
    assert answer_dto.transcript_text == "Asynchronous Server Gateway Interface"

    # Test QuestionResponse from ORM
    question_dto = QuestionResponse.model_validate(q1_orm)
    assert question_dto.id == q1_orm.id
    assert question_dto.question_index == 1
    assert question_dto.question_text == "What is ASGI?"
    assert question_dto.answer is not None
    assert question_dto.answer.id == a1_orm.id

    # Test SessionResponse from ORM with nested resume and questions
    session_dto = SessionResponse.model_validate(session_orm)
    assert session_dto.id == session_orm.id
    assert session_dto.candidate_name == "Alice Candidate"
    assert session_dto.status == SessionStatus.in_progress
    assert session_dto.resume is not None
    assert session_dto.resume.id == resume_orm.id
    assert len(session_dto.questions) == 1
    assert session_dto.questions[0].id == q1_orm.id
    assert session_dto.questions[0].answer is not None
    assert session_dto.questions[0].answer.score == 9.5
