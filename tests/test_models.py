import pytest
from datetime import datetime, timezone
from sqlalchemy.exc import IntegrityError

from app.database import engine, Base, SessionLocal
from app.models import InterviewSession, Resume, Question, Answer, SessionStatus


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


def test_models_crud_and_relationships(db):
    """Verify normal creation, relationships, and round-tripping."""
    session = InterviewSession(
        candidate_name="Alice Candidate",
        resume_filename="alice_resume.pdf",
    )
    db.add(session)
    db.commit()
    db.refresh(session)

    assert session.id is not None
    assert session.status == SessionStatus.in_progress
    assert isinstance(session.created_at, datetime)

    # 1:1 Resume
    resume = Resume(
        session_id=session.id,
        skills_json='["Python", "FastAPI"]',
        projects_json='["MockWise"]',
        experience_json='[{"role": "Engineer"}]',
        education_json='[{"degree": "B.Tech"}]',
        raw_text="Alice's Resume Content",
    )
    db.add(resume)
    db.commit()

    # 1:N Questions
    q1 = Question(
        session_id=session.id,
        question_index=1,
        question_text="Explain dependency injection in FastAPI.",
        question_type="technical",
    )
    q2 = Question(
        session_id=session.id,
        question_index=2,
        question_text="Tell me about yourself.",
        question_type="general",
    )
    db.add_all([q1, q2])
    db.commit()

    # 1:0..1 Answer
    a1 = Answer(
        question_id=q1.id,
        transcript_text="Dependency injection allows separating creation of dependencies from usage.",
        score=8.5,
        feedback_text="Clear and concise explanation.",
    )
    db.add(a1)
    db.commit()

    db.refresh(session)
    assert session.resume.id == resume.id
    assert len(session.questions) == 2
    assert session.questions[0].question_index == 1
    assert session.questions[0].answer.id == a1.id
    assert session.questions[1].answer is None


def test_foreign_key_enforcement_active(db):
    """Verify that SQLite foreign key enforcement is active: invalid foreign key fails."""
    invalid_session_id = "non-existent-session-id"
    question = Question(
        session_id=invalid_session_id,
        question_index=1,
        question_text="Invalid question?",
    )
    db.add(question)
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


def test_unique_session_question_index_constraint(db):
    """Verify composite unique constraint: duplicate (session_id, question_index) raises IntegrityError."""
    session = InterviewSession(candidate_name="Bob")
    db.add(session)
    db.commit()
    db.refresh(session)

    q1 = Question(
        session_id=session.id,
        question_index=1,
        question_text="First question",
    )
    db.add(q1)
    db.commit()

    # Attempt to insert a second question with identical session_id and question_index=1
    duplicate_q = Question(
        session_id=session.id,
        question_index=1,
        question_text="Duplicate index question",
    )
    db.add(duplicate_q)
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


def test_cascade_delete(db):
    """Verify that deleting an interview session cascades to resume, questions, and answers."""
    session = InterviewSession(candidate_name="Charlie")
    db.add(session)
    db.commit()
    db.refresh(session)

    resume = Resume(session_id=session.id)
    q1 = Question(session_id=session.id, question_index=1, question_text="Question 1")
    db.add_all([resume, q1])
    db.commit()
    db.refresh(q1)

    a1 = Answer(question_id=q1.id, transcript_text="Answer 1")
    db.add(a1)
    db.commit()

    # Delete session
    db.delete(session)
    db.commit()

    assert db.query(Resume).filter_by(id=resume.id).first() is None
    assert db.query(Question).filter_by(id=q1.id).first() is None
    assert db.query(Answer).filter_by(id=a1.id).first() is None
