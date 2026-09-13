import pytest
from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app

# SQLite in-memory with StaticPool to share a single connection and in-memory state
SQLALCHEMY_TEST_DATABASE_URL = "sqlite:///:memory:"

test_engine = create_engine(
    SQLALCHEMY_TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)


@event.listens_for(Engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


TestingSessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=test_engine,
)


@pytest.fixture(autouse=True)
def setup_database():
    """Create all tables in memory before each test and drop them after."""
    Base.metadata.create_all(bind=test_engine)
    yield
    Base.metadata.drop_all(bind=test_engine)


@pytest.fixture
def client():
    """TestClient using the in-memory SQLite database with StaticPool."""
    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def test_health_check(client):
    """Verify that the health check endpoint returns 200 and ok status."""
    response = client.get("/health")
    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {"status": "ok"}


def test_create_session(client):
    """Verify creating an interview session."""
    payload = {
        "candidate_name": "Jane Doe",
        "resume_filename": "resume_jane.pdf",
    }
    response = client.post("/sessions", json=payload)
    assert response.status_code == status.HTTP_201_CREATED
    data = response.json()
    assert data["id"] is not None
    assert data["candidate_name"] == "Jane Doe"
    assert data["resume_filename"] == "resume_jane.pdf"
    assert data["status"] == "in_progress"
    assert "created_at" in data
    assert data["questions"] == []
    assert data["resume"] is None


def test_fetch_nonexistent_session(client):
    """Verify fetching a nonexistent session returns 404."""
    response = client.get("/sessions/nonexistent-session-id-12345")
    assert response.status_code == status.HTTP_404_NOT_FOUND
    data = response.json()
    assert "detail" in data
    assert "not found" in data["detail"].lower()


def test_full_session_flow_and_duplicate_answer_rejection(client):
    """Full flow:

    1. Create a session.
    2. Add the next question.
    3. Submit an answer to the question.
    4. Confirm a second answer to the same question is rejected.
    5. Fetch the session and confirm the state.
    """
    # 1. Create a session
    create_res = client.post(
        "/sessions",
        json={"candidate_name": "Alex Smith", "resume_filename": "alex_cv.pdf"},
    )
    assert create_res.status_code == status.HTTP_201_CREATED
    session_data = create_res.json()
    session_id = session_data["id"]

    # 2. Add a question
    add_q_res = client.post(f"/sessions/{session_id}/questions")
    assert add_q_res.status_code == status.HTTP_201_CREATED
    q_data = add_q_res.json()
    question_id = q_data["id"]
    assert q_data["session_id"] == session_id
    assert q_data["question_index"] == 1
    assert "Placeholder" in q_data["question_text"]
    assert q_data["answer"] is None

    # 3. Submit an answer
    ans_payload = {
        "transcript_text": "I have 4 years of experience building scalable backend microservices.",
    }
    ans_res = client.post(f"/questions/{question_id}/answer", json=ans_payload)
    assert ans_res.status_code == status.HTTP_201_CREATED
    ans_data = ans_res.json()
    assert ans_data["question_id"] == question_id
    assert ans_data["transcript_text"] == ans_payload["transcript_text"]
    assert ans_data["score"] is None
    assert ans_data["feedback_text"] is None

    # 4. Confirm a second answer to the same question is rejected
    second_ans_payload = {
        "transcript_text": "Trying to submit another answer to the same question.",
    }
    duplicate_res = client.post(f"/questions/{question_id}/answer", json=second_ans_payload)
    assert duplicate_res.status_code == status.HTTP_400_BAD_REQUEST
    duplicate_data = duplicate_res.json()
    assert "already been submitted" in duplicate_data["detail"].lower()

    # 5. Fetch the session and confirm the structure
    get_res = client.get(f"/sessions/{session_id}")
    assert get_res.status_code == status.HTTP_200_OK
    fetched_session = get_res.json()
    assert fetched_session["id"] == session_id
    assert fetched_session["candidate_name"] == "Alex Smith"
    assert len(fetched_session["questions"]) == 1
    assert fetched_session["questions"][0]["id"] == question_id
    assert fetched_session["questions"][0]["answer"] is not None
    assert (
        fetched_session["questions"][0]["answer"]["transcript_text"]
        == ans_payload["transcript_text"]
    )
