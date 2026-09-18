import io
from unittest.mock import patch
import pytest
from fastapi import status
from fastapi.testclient import TestClient
from reportlab.pdfgen import canvas
from sqlalchemy.exc import SQLAlchemyError

from app.database import Base, engine, get_db, SessionLocal
from app.main import app
from app.models import Answer, InterviewSession, Question, Resume


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


def _make_sample_resume_pdf() -> bytes:
    """Generate in-memory PDF resume bytes."""
    buf = io.BytesIO()
    c = canvas.Canvas(buf)
    lines = [
        "Alice Candidate",
        "alice@example.com",
        "",
        "Skills",
        "Python, FastAPI, SQL, Docker",
        "",
        "Experience",
        "Software Engineer at Acme Corp 2021-2024",
        "",
        "Projects",
        "MockWise: Speech AI Mock Interview Platform",
        "",
        "Education",
        "B.S. Computer Science, 2020",
    ]
    y = 750
    for line in lines:
        c.drawString(72, y, line)
        y -= 20
    c.save()
    return buf.getvalue()


def test_get_next_question_flow(client):
    """Uploading a resume triggers question generation, and GET /questions/next walks them sequentially."""
    db = SessionLocal()
    session = InterviewSession(candidate_name="Alice")
    db.add(session)
    db.commit()
    session_id = session.id
    db.close()

    # Upload resume to trigger generation
    pdf_bytes = _make_sample_resume_pdf()
    upload_res = client.post(
        f"/sessions/{session_id}/resume",
        files={"file": ("resume.pdf", pdf_bytes, "application/pdf")},
    )
    assert upload_res.status_code == status.HTTP_201_CREATED

    # GET /sessions/{session_id}/questions/next returns first question (index 0)
    res_next1 = client.get(f"/sessions/{session_id}/questions/next")
    assert res_next1.status_code == status.HTTP_200_OK
    q0_data = res_next1.json()
    assert q0_data["session_id"] == session_id
    assert q0_data["question_index"] == 0
    assert len(q0_data["question_text"]) > 0
    assert q0_data["answer"] is None

    # Submit answer for index 0
    ans_res = client.post(
        f"/questions/{q0_data['id']}/answer",
        json={"transcript_text": "Answer for first question."},
    )
    assert ans_res.status_code == status.HTTP_201_CREATED

    # Now next question should be index 1
    res_next2 = client.get(f"/sessions/{session_id}/questions/next")
    assert res_next2.status_code == status.HTTP_200_OK
    q1_data = res_next2.json()
    assert q1_data["question_index"] == 1
    assert q1_data["id"] != q0_data["id"]


def test_get_next_question_session_not_found(client):
    """GET /sessions/{session_id}/questions/next returns 404 for invalid session."""
    response_get = client.get("/sessions/non-existent-session/questions/next")
    assert response_get.status_code == status.HTTP_404_NOT_FOUND
    assert "not found" in response_get.json()["detail"].lower()


def test_get_next_question_no_unanswered_remaining(client):
    """GET /sessions/{session_id}/questions/next returns 404 when session has no unanswered questions."""
    db = SessionLocal()
    session = InterviewSession(candidate_name="Bob")
    db.add(session)
    db.commit()
    session_id = session.id
    db.close()

    # Session exists but has no questions generated/remaining
    res = client.get(f"/sessions/{session_id}/questions/next")
    assert res.status_code == status.HTTP_404_NOT_FOUND
    assert "no unanswered questions" in res.json()["detail"].lower()


def test_get_next_question_database_error(client):
    """GET /sessions/{session_id}/questions/next handles database errors with 500."""
    db = SessionLocal()
    session = InterviewSession(candidate_name="Bob")
    db.add(session)
    db.commit()
    session_id = session.id
    db.close()

    with patch("app.routers.questions.Session.query", side_effect=SQLAlchemyError("DB read fail")):
        response = client.get(f"/sessions/{session_id}/questions/next")
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        assert "database error" in response.json()["detail"].lower()


def test_submit_answer_success(client):
    """POST /questions/{question_id}/answer creates answer with transcript and None score/feedback."""
    db = SessionLocal()
    session = InterviewSession(candidate_name="Charlie")
    db.add(session)
    db.commit()

    question = Question(session_id=session.id, question_index=0, question_text="What is SQL?")
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

    question = Question(session_id=session.id, question_index=0, question_text="Question")
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

    question = Question(session_id=session.id, question_index=0, question_text="Question")
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


def test_get_question_audio_flow(client):
    """Create session, upload resume, fetch next question, and get its audio as WAV."""
    db = SessionLocal()
    session = InterviewSession(candidate_name="Grace")
    db.add(session)
    db.commit()
    session_id = session.id
    db.close()

    # Upload resume to trigger generation
    pdf_bytes = _make_sample_resume_pdf()
    upload_res = client.post(
        f"/sessions/{session_id}/resume",
        files={"file": ("resume.pdf", pdf_bytes, "application/pdf")},
    )
    assert upload_res.status_code == status.HTTP_201_CREATED

    # Fetch next question
    res_next = client.get(f"/sessions/{session_id}/questions/next")
    assert res_next.status_code == status.HTTP_200_OK
    question_data = res_next.json()
    question_id = question_data["id"]

    # Call GET /questions/{question_id}/audio
    audio_res = client.get(f"/questions/{question_id}/audio")
    assert audio_res.status_code == status.HTTP_200_OK
    assert "audio/wav" in audio_res.headers.get("content-type", "")
    assert audio_res.content.startswith(b"RIFF")
    assert audio_res.content[8:12] == b"WAVE"


def test_get_question_audio_not_found(client):
    """GET /questions/{question_id}/audio returns 404 for nonexistent question ID."""
    response = client.get("/questions/nonexistent-question-id/audio")
    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert "not found" in response.json()["detail"].lower()


def test_get_question_audio_database_error(client):
    """GET /questions/{question_id}/audio returns 500 on database error."""
    with patch("app.routers.questions.Session.query", side_effect=SQLAlchemyError("DB lookup fail")):
        response = client.get("/questions/some-id/audio")
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        assert "database error" in response.json()["detail"].lower()


def test_submit_audio_answer_success(client):
    """POST /questions/{question_id}/answer/audio transcribes audio and stores answer."""
    db = SessionLocal()
    session = InterviewSession(candidate_name="Hannah")
    db.add(session)
    db.commit()
    session_id = session.id
    db.close()

    # Upload resume to trigger generation
    pdf_bytes = _make_sample_resume_pdf()
    upload_res = client.post(
        f"/sessions/{session_id}/resume",
        files={"file": ("resume.pdf", pdf_bytes, "application/pdf")},
    )
    assert upload_res.status_code == status.HTTP_201_CREATED

    # Fetch next question
    res_next = client.get(f"/sessions/{session_id}/questions/next")
    assert res_next.status_code == status.HTTP_200_OK
    question_data = res_next.json()
    question_id = question_data["id"]

    # Submit audio answer
    audio_content = b"RIFF\x24\x00\x00\x00WAVEfmt \x10\x00\x00\x00"
    submit_res = client.post(
        f"/questions/{question_id}/answer/audio",
        files={"file": ("recording.wav", audio_content, "audio/wav")},
    )
    assert submit_res.status_code == status.HTTP_201_CREATED
    data = submit_res.json()
    assert data["question_id"] == question_id
    assert data["transcript_text"] == "This is a mock transcription of the candidate's answer."
    assert data["score"] is None
    assert data["feedback_text"] is None

    # Check that session reflects the answer
    res_session = client.get(f"/sessions/{session_id}")
    assert res_session.status_code == status.HTTP_200_OK
    session_json = res_session.json()
    matching_q = [q for q in session_json["questions"] if q["id"] == question_id][0]
    assert matching_q["answer"] is not None
    assert matching_q["answer"]["transcript_text"] == "This is a mock transcription of the candidate's answer."


def test_submit_audio_answer_duplicate_rejected(client):
    """POST /questions/{question_id}/answer/audio rejects duplicate answer with 400."""
    db = SessionLocal()
    session = InterviewSession(candidate_name="Ian")
    db.add(session)
    db.commit()

    question = Question(session_id=session.id, question_index=0, question_text="Question")
    db.add(question)
    db.commit()
    question_id = question.id
    db.close()

    # First audio submission succeeds
    audio_bytes = b"valid audio bytes"
    res1 = client.post(
        f"/questions/{question_id}/answer/audio",
        files={"file": ("recording1.wav", audio_bytes, "audio/wav")},
    )
    assert res1.status_code == status.HTTP_201_CREATED

    # Second audio submission fails with 400
    res2 = client.post(
        f"/questions/{question_id}/answer/audio",
        files={"file": ("recording2.wav", audio_bytes, "audio/wav")},
    )
    assert res2.status_code == status.HTTP_400_BAD_REQUEST
    assert "already been submitted" in res2.json()["detail"].lower()


def test_submit_audio_answer_empty_audio_rejected(client):
    """POST /questions/{question_id}/answer/audio returns 400 (not 500) when audio file is empty."""
    db = SessionLocal()
    session = InterviewSession(candidate_name="Jack")
    db.add(session)
    db.commit()

    question = Question(session_id=session.id, question_index=0, question_text="Question")
    db.add(question)
    db.commit()
    question_id = question.id
    db.close()

    # Upload empty file bytes
    res = client.post(
        f"/questions/{question_id}/answer/audio",
        files={"file": ("empty.wav", b"", "audio/wav")},
    )
    assert res.status_code == status.HTTP_400_BAD_REQUEST
    assert "empty" in res.json()["detail"].lower()


def test_submit_audio_answer_question_not_found(client):
    """POST /questions/{question_id}/answer/audio returns 404 for nonexistent question ID."""
    res = client.post(
        "/questions/nonexistent-id/answer/audio",
        files={"file": ("recording.wav", b"audio data", "audio/wav")},
    )
    assert res.status_code == status.HTTP_404_NOT_FOUND
    assert "not found" in res.json()["detail"].lower()


