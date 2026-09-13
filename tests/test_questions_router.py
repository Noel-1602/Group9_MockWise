import pytest
from fastapi import status
from fastapi.testclient import TestClient
from unittest.mock import patch
from sqlalchemy.exc import SQLAlchemyError

from app.database import Base, engine, get_db, SessionLocal
from app.main import app
from app.models import Answer, InterviewSession, Question


@pytest.fixture(autouse=True)
def setup_database():
    """Create all tables before each test and drop them after."""
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def client():
    """TestClient with dependency override for clean db per request."""
    def override_get_db():
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def test_add_next_question_success(client):
    """POST /sessions/{session_id}/questions creates sequential questions."""
    db = SessionLocal()
    session = InterviewSession(candidate_name="Alice")
    db.add(session)
    db.commit()
    session_id = session.id
    db.close()

    # First question (index 1)
    res1 = client.post(f"/sessions/{session_id}/questions")
    assert res1.status_code == status.HTTP_201_CREATED
    q1_data = res1.json()
    assert q1_data["session_id"] == session_id
    assert q1_data["question_index"] == 1
    assert "Placeholder" in q1_data["question_text"]
    assert q1_data["answer"] is None

    # Second question (index 2)
    res2 = client.post(f"/sessions/{session_id}/questions")
    assert res2.status_code == status.HTTP_201_CREATED
    q2_data = res2.json()
    assert q2_data["session_id"] == session_id
    assert q2_data["question_index"] == 2


def test_add_next_question_session_not_found(client):
    """POST /sessions/{session_id}/questions returns 404 for invalid session."""
    response = client.post("/sessions/non-existent-session/questions")
    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert "not found" in response.json()["detail"].lower()


def test_add_next_question_database_error(client):
    """POST /sessions/{session_id}/questions handles database errors with 500."""
    db = SessionLocal()
    session = InterviewSession(candidate_name="Bob")
    db.add(session)
    db.commit()
    session_id = session.id
    db.close()

    with patch("app.routers.questions.Session.commit", side_effect=SQLAlchemyError("DB write fail")):
        response = client.post(f"/sessions/{session_id}/questions")
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        assert response.json()["detail"] == "Failed to create question due to a database error."


def test_submit_answer_success(client):
    """POST /questions/{question_id}/answer creates answer with transcript and None score/feedback."""
    db = SessionLocal()
    session = InterviewSession(candidate_name="Charlie")
    db.add(session)
    db.commit()

    question = Question(session_id=session.id, question_index=1, question_text="What is SQL?")
    db.add(question)
    db.commit()
    question_id = question.id
    session_id = session.id
    db.close()

    payload = {
        "transcript_text": "Structured Query Language is used for relational databases."
    }
    response = client.post(f"/questions/{question_id}/answer", json=payload)
    assert response.status_code == status.HTTP_201_CREATED
    data = response.json()
    assert data["question_id"] == question_id
    assert data["transcript_text"] == "Structured Query Language is used for relational databases."
    assert data["score"] is None
    assert data["feedback_text"] is None

    # Check that answer is properly associated in session
    res_session = client.get(f"/sessions/{session_id}")
    assert res_session.status_code == status.HTTP_200_OK
    session_data = res_session.json()
    assert len(session_data["questions"]) == 1
    assert session_data["questions"][0]["answer"]["transcript_text"] == "Structured Query Language is used for relational databases."


def test_submit_answer_duplicate_rejected(client):
    """POST /questions/{question_id}/answer rejects second answer for same question with 400."""
    db = SessionLocal()
    session = InterviewSession(candidate_name="Dana")
    db.add(session)
    db.commit()

    question = Question(session_id=session.id, question_index=1, question_text="Question")
    db.add(question)
    db.commit()
    question_id = question.id
    db.close()

    # Initial submission succeeds
    res1 = client.post(f"/questions/{question_id}/answer", json={"transcript_text": "First attempt"})
    assert res1.status_code == status.HTTP_201_CREATED
    assert res1.json()["transcript_text"] == "First attempt"

    # Second submission is rejected
    res2 = client.post(f"/questions/{question_id}/answer", json={"transcript_text": "Revised answer"})
    assert res2.status_code == status.HTTP_400_BAD_REQUEST
    assert "already been submitted" in res2.json()["detail"].lower()


def test_submit_answer_question_not_found(client):
    """POST /questions/{question_id}/answer returns 404 when question does not exist."""
    response = client.post(
        "/questions/invalid-question-id/answer",
        json={"transcript_text": "Test transcript"}
    )
    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert "not found" in response.json()["detail"].lower()


def test_submit_answer_database_error(client):
    """POST /questions/{question_id}/answer returns 500 on database error."""
    db = SessionLocal()
    session = InterviewSession(candidate_name="Eve")
    db.add(session)
    db.commit()

    question = Question(session_id=session.id, question_index=1, question_text="Question")
    db.add(question)
    db.commit()
    question_id = question.id
    db.close()

    with patch("app.routers.questions.Session.commit", side_effect=SQLAlchemyError("Commit fail")):
        response = client.post(
            f"/questions/{question_id}/answer",
            json={"transcript_text": "Test transcript"}
        )
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        assert response.json()["detail"] == "Failed to save answer due to a database error."
