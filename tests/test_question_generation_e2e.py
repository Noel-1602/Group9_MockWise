import io
import json
import pytest
from fastapi import status
from fastapi.testclient import TestClient
from reportlab.pdfgen import canvas

from app.database import Base, engine, get_db, SessionLocal
from app.main import app
from app.models import InterviewSession, Question


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
    """Generate in-memory PDF resume for end-to-end testing."""
    buf = io.BytesIO()
    c = canvas.Canvas(buf)
    lines = [
        "Jane Doe",
        "jane.doe@example.com",
        "",
        "Skills",
        "Python, FastAPI, Docker, Kubernetes, PostgreSQL, AWS",
        "",
        "Experience",
        "Senior Backend Engineer at TechNova (2021-2024)",
        "Software Developer at StartUpCo (2019-2021)",
        "",
        "Projects",
        "MockWise: AI-driven speech mock interview platform",
        "DistributedQueue: High-throughput task processing system",
        "",
        "Education",
        "B.S. in Computer Science, State University, 2019",
    ]
    y = 750
    for line in lines:
        c.drawString(72, y, line)
        y -= 20
    c.save()
    return buf.getvalue()


def test_e2e_resume_upload_question_generation_and_answering_flow(client):
    """End-to-end flow:

    1. Create session.
    2. Upload resume -> auto-generates 6-8 Question rows with sequential 0-based indices and no duplicates.
    3. Re-upload / trigger generation again -> confirms no duplicate batch created.
    4. Fetch next question iteratively -> walks through each question in exact order.
    5. After answering all questions -> fetching next question returns 404.
    """
    # 1. Create session
    create_res = client.post(
        "/sessions",
        json={"candidate_name": "Jane Doe", "resume_filename": "resume.pdf"},
    )
    assert create_res.status_code == status.HTTP_201_CREATED
    session_id = create_res.json()["id"]

    # 2. Upload resume
    pdf_bytes = _make_sample_resume_pdf()
    upload_res = client.post(
        f"/sessions/{session_id}/resume",
        files={"file": ("resume.pdf", pdf_bytes, "application/pdf")},
    )
    assert upload_res.status_code == status.HTTP_201_CREATED

    # Verify session now has 6-8 questions
    session_res = client.get(f"/sessions/{session_id}")
    assert session_res.status_code == status.HTTP_200_OK
    session_data = session_res.json()
    questions = session_data["questions"]

    total_q_count = len(questions)
    assert 6 <= total_q_count <= 8

    # Verify question_index is sequential starting from 0
    indices = [q["question_index"] for q in questions]
    assert indices == list(range(total_q_count))

    # Verify no duplicate question texts
    texts = [q["question_text"] for q in questions]
    assert len(texts) == len(set(texts))

    # Verify valid question types
    for q in questions:
        assert q["question_type"] in ("resume_specific", "general")

    # 3. Re-uploading resume (or re-triggering generation) must NOT create a second batch
    reupload_res = client.post(
        f"/sessions/{session_id}/resume",
        files={"file": ("resume_v2.pdf", pdf_bytes, "application/pdf")},
    )
    assert reupload_res.status_code == status.HTTP_201_CREATED

    db = SessionLocal()
    questions_in_db = (
        db.query(Question)
        .filter(Question.session_id == session_id)
        .order_by(Question.question_index.asc())
        .all()
    )
    db.close()
    assert len(questions_in_db) == total_q_count

    # 4. Walk through questions one by one using GET /sessions/{session_id}/questions/next
    for expected_index in range(total_q_count):
        next_res = client.get(f"/sessions/{session_id}/questions/next")
        assert next_res.status_code == status.HTTP_200_OK
        q_item = next_res.json()

        assert q_item["question_index"] == expected_index
        assert q_item["id"] == questions[expected_index]["id"]
        assert q_item["answer"] is None

        # Submit answer for this question
        ans_res = client.post(
            f"/questions/{q_item['id']}/answer",
            json={"transcript_text": f"Answer for question index {expected_index}."},
        )
        assert ans_res.status_code == status.HTTP_201_CREATED

    # 5. After answering all questions, fetching next question must return 404
    exhausted_res = client.get(f"/sessions/{session_id}/questions/next")
    assert exhausted_res.status_code == status.HTTP_404_NOT_FOUND
    assert "no unanswered questions" in exhausted_res.json()["detail"].lower()


def test_two_sessions_same_resume_generate_different_question_sets(client):
    """Verify that uploading the same resume across distinct sessions produces differing question sets."""
    pdf_bytes = _make_sample_resume_pdf()

    # Create session 1 and upload resume
    res1 = client.post("/sessions", json={"candidate_name": "Jane Doe 1", "resume_filename": "resume.pdf"})
    assert res1.status_code == status.HTTP_201_CREATED
    s1_id = res1.json()["id"]

    upload1 = client.post(
        f"/sessions/{s1_id}/resume",
        files={"file": ("resume.pdf", pdf_bytes, "application/pdf")},
    )
    assert upload1.status_code == status.HTTP_201_CREATED

    session1 = client.get(f"/sessions/{s1_id}").json()
    q_texts_1 = [q["question_text"] for q in session1["questions"]]

    # Create session 2 and upload identical resume
    res2 = client.post("/sessions", json={"candidate_name": "Jane Doe 2", "resume_filename": "resume.pdf"})
    assert res2.status_code == status.HTTP_201_CREATED
    s2_id = res2.json()["id"]

    upload2 = client.post(
        f"/sessions/{s2_id}/resume",
        files={"file": ("resume.pdf", pdf_bytes, "application/pdf")},
    )
    assert upload2.status_code == status.HTTP_201_CREATED

    session2 = client.get(f"/sessions/{s2_id}").json()
    q_texts_2 = [q["question_text"] for q in session2["questions"]]

    # Multiple distinct sessions with identical resume produce different question sequences / sets
    # (If by low chance 1 attempt matches, we do a few iterations to ensure variance is demonstrated)
    attempts = 0
    while q_texts_1 == q_texts_2 and attempts < 5:
        attempts += 1
        res = client.post("/sessions", json={"candidate_name": f"Jane Doe {attempts + 2}", "resume_filename": "resume.pdf"})
        s_id = res.json()["id"]
        client.post(f"/sessions/{s_id}/resume", files={"file": ("resume.pdf", pdf_bytes, "application/pdf")})
        q_texts_2 = [q["question_text"] for q in client.get(f"/sessions/{s_id}").json()["questions"]]

    assert q_texts_1 != q_texts_2
