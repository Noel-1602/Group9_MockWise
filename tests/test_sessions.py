import json
from unittest.mock import patch
import pytest
from fastapi import status
from fastapi.testclient import TestClient

from app.database import Base, SessionLocal, engine, get_db
from app.models import Question
from app.main import app


@pytest.fixture(autouse=True)
def setup_database():
    """Create all tables before each test and drop them after."""
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def client():
    """TestClient using the isolated test database."""
    def override_get_db():
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def _make_sample_pdf_bytes() -> bytes:
    import io
    from reportlab.pdfgen import canvas
    buf = io.BytesIO()
    c = canvas.Canvas(buf)
    lines = [
        "Sarah Connor",
        "sarah@skynet.resistance",
        "",
        "Skills",
        "Tactics, Python, Security",
        "",
        "Experience",
        "Leader at Resistance - Directed tactical operations",
    ]
    y = 750
    for line in lines:
        c.drawString(72, y, line)
        y -= 20
    c.save()
    return buf.getvalue()


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

    # 2. Populate a question for the session
    db = SessionLocal()
    q = Question(
        session_id=session_id,
        question_index=0,
        question_text="Tell me about your experience building backend microservices.",
        question_type="general",
    )
    db.add(q)
    db.commit()
    db.refresh(q)
    question_id = q.id
    db.close()

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


def test_complete_session_evaluates_unscored_answers(client):
    """Verify complete_session evaluates all answered-but-unscored questions.

    1. Create a session.
    2. Upload a resume (generating questions).
    3. Answer 2 of the questions (leaving at least one unanswered).
    4. Call complete_session.
    5. Confirm answered questions have non-null score and valid evaluation_json.
    6. Confirm unanswered questions have no Answer row.
    7. Confirm calling complete a second time is idempotent.
    """
    # 1. Create a session
    create_res = client.post(
        "/sessions",
        json={"candidate_name": "Sarah Connor", "resume_filename": "sarah.pdf"},
    )
    assert create_res.status_code == status.HTTP_201_CREATED
    session_id = create_res.json()["id"]

    # 2. Upload resume
    pdf_bytes = _make_sample_pdf_bytes()
    upload_res = client.post(
        f"/sessions/{session_id}/resume",
        files={"file": ("sarah.pdf", pdf_bytes, "application/pdf")},
    )
    assert upload_res.status_code == status.HTTP_201_CREATED

    # 3. Fetch generated questions and answer 2 of them
    get_res = client.get(f"/sessions/{session_id}")
    assert get_res.status_code == status.HTTP_200_OK
    questions = get_res.json()["questions"]
    assert len(questions) >= 3

    q0_id = questions[0]["id"]
    q1_id = questions[1]["id"]
    q2_id = questions[2]["id"]

    # Answer Q0 with a mid-length answer
    ans0_res = client.post(
        f"/questions/{q0_id}/answer",
        json={
            "transcript_text": (
                "I have worked with Python for about two years building backend APIs using "
                "FastAPI and PostgreSQL, creating endpoints, writing tests, and managing migrations."
            )
        },
    )
    assert ans0_res.status_code == status.HTTP_201_CREATED

    # Answer Q1 with a short answer
    ans1_res = client.post(
        f"/questions/{q1_id}/answer",
        json={"transcript_text": "Short answer here."},
    )
    assert ans1_res.status_code == status.HTTP_201_CREATED

    # Q2 is left unanswered

    # 4. Call complete_session
    complete_res = client.post(f"/sessions/{session_id}/complete")
    assert complete_res.status_code == status.HTTP_200_OK

    # 5. Fetch session and verify answers
    session_res = client.get(f"/sessions/{session_id}")
    assert session_res.status_code == status.HTTP_200_OK
    session_data = session_res.json()
    assert session_data["status"] == "completed"

    q0_data = next(q for q in session_data["questions"] if q["id"] == q0_id)
    q1_data = next(q for q in session_data["questions"] if q["id"] == q1_id)
    q2_data = next(q for q in session_data["questions"] if q["id"] == q2_id)

    # Check Q0 evaluated
    assert q0_data["answer"] is not None
    assert q0_data["answer"]["score"] is not None
    assert 5.0 <= q0_data["answer"]["score"] <= 6.5
    assert q0_data["answer"]["evaluation_json"] is not None
    eval0 = json.loads(q0_data["answer"]["evaluation_json"])
    for key in ["overall_score", "relevance_score", "clarity_score", "structure_score", "feedback_text"]:
        assert key in eval0
    assert eval0["overall_score"] == q0_data["answer"]["score"]

    # Check Q1 evaluated
    assert q1_data["answer"] is not None
    assert q1_data["answer"]["score"] is not None
    assert 2.0 <= q1_data["answer"]["score"] <= 3.5
    assert q1_data["answer"]["evaluation_json"] is not None
    eval1 = json.loads(q1_data["answer"]["evaluation_json"])
    for key in ["overall_score", "relevance_score", "clarity_score", "structure_score", "feedback_text"]:
        assert key in eval1
    assert eval1["overall_score"] == q1_data["answer"]["score"]

    # 6. Check Q2 has no answer row
    assert q2_data["answer"] is None

    # 7. Check idempotency: calling complete again doesn't change scores or re-evaluate
    q0_score_first = q0_data["answer"]["score"]
    q1_score_first = q1_data["answer"]["score"]
    q0_eval_first = q0_data["answer"]["evaluation_json"]
    q1_eval_first = q1_data["answer"]["evaluation_json"]

    with patch("app.routers.sessions.evaluate_answer") as mock_evaluate:
        complete_second_res = client.post(f"/sessions/{session_id}/complete")
        assert complete_second_res.status_code == status.HTTP_200_OK
        assert mock_evaluate.call_count == 0

    session_second_res = client.get(f"/sessions/{session_id}")
    session_second_data = session_second_res.json()
    q0_second = next(q for q in session_second_data["questions"] if q["id"] == q0_id)
    q1_second = next(q for q in session_second_data["questions"] if q["id"] == q1_id)
    q2_second = next(q for q in session_second_data["questions"] if q["id"] == q2_id)

    assert q0_second["answer"]["score"] == q0_score_first
    assert q1_second["answer"]["score"] == q1_score_first
    assert q0_second["answer"]["evaluation_json"] == q0_eval_first
    assert q1_second["answer"]["evaluation_json"] == q1_eval_first
    assert q2_second["answer"] is None


def test_session_summary_computation(client):
    """Verify computed session summary metrics:

    1. A session with questions but no answers returns average_score: None and answered_count: 0.
    2. A session with generated question mix computes correct resume_specific_count and general_count.
    3. A session with some answered and scored questions returns the exact average_score (e.g. 4.0 and 6.0 average to 5.0).
    """
    # 1. Create a session and upload resume to generate questions
    create_res = client.post(
        "/sessions",
        json={"candidate_name": "John Summary", "resume_filename": "john_cv.pdf"},
    )
    assert create_res.status_code == status.HTTP_201_CREATED
    session_id = create_res.json()["id"]

    pdf_bytes = _make_sample_pdf_bytes()
    upload_res = client.post(
        f"/sessions/{session_id}/resume",
        files={"file": ("john_cv.pdf", pdf_bytes, "application/pdf")},
    )
    assert upload_res.status_code == status.HTTP_201_CREATED

    # 2. Fetch session when no questions have been answered yet
    get_res = client.get(f"/sessions/{session_id}")
    assert get_res.status_code == status.HTTP_200_OK
    session_data = get_res.json()

    questions = session_data["questions"]
    total_q = len(questions)
    assert total_q >= 3

    expected_resume_specific = sum(1 for q in questions if q["question_type"] == "resume_specific")
    expected_general = sum(1 for q in questions if q["question_type"] == "general")

    assert session_data["total_questions"] == total_q
    assert session_data["answered_count"] == 0
    assert session_data["average_score"] is None
    assert session_data["resume_specific_count"] == expected_resume_specific
    assert session_data["general_count"] == expected_general
    assert expected_resume_specific + expected_general == total_q

    # 3. Answer two questions with explicit scores 4.0 and 6.0
    q0_id = questions[0]["id"]
    q1_id = questions[1]["id"]

    ans0_res = client.post(
        f"/questions/{q0_id}/answer",
        json={"transcript_text": "Answer to first question", "score": 4.0},
    )
    assert ans0_res.status_code == status.HTTP_201_CREATED

    ans1_res = client.post(
        f"/questions/{q1_id}/answer",
        json={"transcript_text": "Answer to second question", "score": 6.0},
    )
    assert ans1_res.status_code == status.HTTP_201_CREATED

    # 4. Fetch session again and verify the computed average score and counts
    get_res_scored = client.get(f"/sessions/{session_id}")
    assert get_res_scored.status_code == status.HTTP_200_OK
    scored_session_data = get_res_scored.json()

    assert scored_session_data["total_questions"] == total_q
    assert scored_session_data["answered_count"] == 2
    # Verify exact arithmetic: (4.0 + 6.0) / 2 == 5.0
    assert scored_session_data["average_score"] == 5.0
    assert scored_session_data["resume_specific_count"] == expected_resume_specific
    assert scored_session_data["general_count"] == expected_general


def test_session_summary_manual_question_mix(client):
    """Verify session summary metrics on manually configured question types and scores."""
    create_res = client.post(
        "/sessions",
        json={"candidate_name": "Test Candidate"},
    )
    assert create_res.status_code == status.HTTP_201_CREATED
    session_id = create_res.json()["id"]

    # Add 3 questions: 2 resume_specific, 1 general
    db = SessionLocal()
    q1 = Question(
        session_id=session_id,
        question_index=0,
        question_text="Resume Q1",
        question_type="resume_specific",
    )
    q2 = Question(
        session_id=session_id,
        question_index=1,
        question_text="Resume Q2",
        question_type="resume_specific",
    )
    q3 = Question(
        session_id=session_id,
        question_index=2,
        question_text="General Q1",
        question_type="general",
    )
    db.add_all([q1, q2, q3])
    db.commit()
    db.refresh(q1)
    db.refresh(q2)
    db.refresh(q3)
    q1_id, q2_id, q3_id = q1.id, q2.id, q3.id
    db.close()

    # Verify initial summary with 0 answered
    res = client.get(f"/sessions/{session_id}")
    assert res.status_code == status.HTTP_200_OK
    data = res.json()
    assert data["total_questions"] == 3
    assert data["answered_count"] == 0
    assert data["average_score"] is None
    assert data["resume_specific_count"] == 2
    assert data["general_count"] == 1

    # Answer q1 with 4.0 and q2 with 6.0
    client.post(f"/questions/{q1_id}/answer", json={"transcript_text": "Ans 1", "score": 4.0})
    client.post(f"/questions/{q2_id}/answer", json={"transcript_text": "Ans 2", "score": 6.0})

    # Verify updated summary
    res = client.get(f"/sessions/{session_id}")
    assert res.status_code == status.HTTP_200_OK
    data = res.json()
    assert data["total_questions"] == 3
    assert data["answered_count"] == 2
    assert data["average_score"] == 5.0
    assert data["resume_specific_count"] == 2
    assert data["general_count"] == 1

