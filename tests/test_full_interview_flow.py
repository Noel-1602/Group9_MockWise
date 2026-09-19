import io
import json
import pytest
from fastapi import status
from fastapi.testclient import TestClient
from reportlab.pdfgen import canvas
from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app

# SQLite in-memory database with StaticPool to share connection state across requests
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
    """TestClient using the in-memory SQLite database with dependency override."""
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


def _make_sample_resume_pdf() -> bytes:
    """Generate in-memory PDF resume bytes containing rich candidate sections."""
    buf = io.BytesIO()
    c = canvas.Canvas(buf)
    lines = [
        "Alex Mercer",
        "alex.mercer@example.com",
        "",
        "Skills",
        "Python, FastAPI, Docker, Kubernetes, PostgreSQL, Distributed Systems",
        "",
        "Experience",
        "Senior Backend Engineer at CloudScale Systems (2021-2024)",
        "Backend Developer at DataStream Corp (2019-2021)",
        "",
        "Projects",
        "MockWise: AI-driven Speech Mock Interview Platform",
        "EventFlow: High-throughput Kafka Stream Processing Engine",
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


def test_full_interview_backend_loop_e2e(client):
    """Comprehensive end-to-end backend interview flow test:

    1. Create a session (POST /sessions).
    2. Upload a resume (POST /sessions/{id}/resume), triggering automatic question generation.
    3. Fetch GET /sessions/{id} and confirm 6-8 questions exist with the expected resume_specific/general split.
    4. For each question, fetch its audio via GET /questions/{id}/audio and confirm a valid WAV response.
    5. Submit an audio answer for most (not all) questions via POST /questions/{id}/answer/audio.
    6. Call POST /sessions/{id}/complete to evaluate unscored answers and mark the session completed.
    7. Fetch GET /sessions/{id} again and confirm:
       - answered questions have non-null score and valid evaluation_json,
       - the unanswered question has no Answer row,
       - average_score reflects only the answered ones,
       - answered_count, total_questions, resume_specific_count, and general_count are all correct.
    """
    # -------------------------------------------------------------------------
    # 1. Create a session
    # -------------------------------------------------------------------------
    create_payload = {
        "candidate_name": "Alex Mercer",
        "resume_filename": "alex_mercer_resume.pdf",
    }
    create_res = client.post("/sessions", json=create_payload)
    assert create_res.status_code == status.HTTP_201_CREATED
    session_data = create_res.json()
    session_id = session_data["id"]

    assert session_data["candidate_name"] == "Alex Mercer"
    assert session_data["resume_filename"] == "alex_mercer_resume.pdf"
    assert session_data["status"] == "in_progress"
    assert session_data["questions"] == []
    assert session_data["resume"] is None
    assert session_data["total_questions"] == 0
    assert session_data["answered_count"] == 0
    assert session_data["average_score"] is None

    # -------------------------------------------------------------------------
    # 2. Upload resume (triggers question generation)
    # -------------------------------------------------------------------------
    pdf_bytes = _make_sample_resume_pdf()
    upload_res = client.post(
        f"/sessions/{session_id}/resume",
        files={"file": ("alex_mercer_resume.pdf", pdf_bytes, "application/pdf")},
    )
    assert upload_res.status_code == status.HTTP_201_CREATED
    resume_data = upload_res.json()
    assert resume_data["session_id"] == session_id
    assert "Python" in (resume_data.get("skills_json") or "")

    # -------------------------------------------------------------------------
    # 3. Fetch GET /sessions/{id} and confirm 6-8 questions and type split
    # -------------------------------------------------------------------------
    get_res_after_upload = client.get(f"/sessions/{session_id}")
    assert get_res_after_upload.status_code == status.HTTP_200_OK
    session_state = get_res_after_upload.json()

    questions = session_state["questions"]
    total_q = len(questions)
    assert 6 <= total_q <= 8, f"Expected 6-8 questions, got {total_q}"

    resume_specific_qs = [q for q in questions if q["question_type"] == "resume_specific"]
    general_qs = [q for q in questions if q["question_type"] == "general"]

    assert len(resume_specific_qs) > 0, "Expected at least one resume_specific question"
    assert len(general_qs) > 0, "Expected at least one general question"
    assert len(resume_specific_qs) + len(general_qs) == total_q

    # Check summary metrics before any answers are submitted
    assert session_state["total_questions"] == total_q
    assert session_state["answered_count"] == 0
    assert session_state["average_score"] is None
    assert session_state["resume_specific_count"] == len(resume_specific_qs)
    assert session_state["general_count"] == len(general_qs)

    # Confirm questions are ordered sequentially with non-empty text
    for idx, q in enumerate(questions):
        assert q["question_index"] == idx
        assert len(q["question_text"].strip()) > 0
        assert q["answer"] is None

    # -------------------------------------------------------------------------
    # 4. Fetch TTS audio for each question and confirm valid WAV response
    # -------------------------------------------------------------------------
    for q in questions:
        q_id = q["id"]
        audio_res = client.get(f"/questions/{q_id}/audio")
        assert audio_res.status_code == status.HTTP_200_OK
        assert "audio/wav" in audio_res.headers.get("content-type", "")
        wav_bytes = audio_res.content
        assert len(wav_bytes) >= 44, "WAV audio output should contain at least a standard 44-byte header"
        assert wav_bytes.startswith(b"RIFF"), "WAV audio must start with 'RIFF' header"
        assert wav_bytes[8:12] == b"WAVE", "WAV audio must contain 'WAVE' chunk identifier"

    # -------------------------------------------------------------------------
    # 5. Submit audio answer for most (not all) questions
    # -------------------------------------------------------------------------
    # Leave the last question unanswered to verify partial answering handling
    questions_to_answer = questions[:-1]
    unanswered_question = questions[-1]
    expected_answered_count = len(questions_to_answer)
    assert expected_answered_count >= 5

    audio_payload_bytes = b"RIFF\x24\x00\x00\x00WAVEfmt \x10\x00\x00\x00"

    for q in questions_to_answer:
        q_id = q["id"]
        submit_res = client.post(
            f"/questions/{q_id}/answer/audio",
            files={"file": (f"answer_{q_id}.wav", audio_payload_bytes, "audio/wav")},
        )
        assert submit_res.status_code == status.HTTP_201_CREATED
        ans_data = submit_res.json()
        assert ans_data["question_id"] == q_id
        assert len(ans_data["transcript_text"].strip()) > 0
        # Score is not assigned yet (assigned during complete session)
        assert ans_data["score"] is None
        assert ans_data["feedback_text"] is None

    # Verify session state before completing
    get_res_before_complete = client.get(f"/sessions/{session_id}")
    assert get_res_before_complete.status_code == status.HTTP_200_OK
    session_before_complete = get_res_before_complete.json()
    assert session_before_complete["status"] == "in_progress"
    assert session_before_complete["answered_count"] == expected_answered_count
    assert session_before_complete["total_questions"] == total_q
    # average_score should still be None since answers have not been scored yet
    assert session_before_complete["average_score"] is None

    # -------------------------------------------------------------------------
    # 6. Complete session (triggers evaluation of unscored answers)
    # -------------------------------------------------------------------------
    complete_res = client.post(f"/sessions/{session_id}/complete")
    assert complete_res.status_code == status.HTTP_200_OK
    completed_session_data = complete_res.json()
    assert completed_session_data["status"] == "completed"

    # -------------------------------------------------------------------------
    # 7. Fetch GET /sessions/{id} again and confirm final evaluation & summary
    # -------------------------------------------------------------------------
    final_res = client.get(f"/sessions/{session_id}")
    assert final_res.status_code == status.HTTP_200_OK
    final_session = final_res.json()

    assert final_session["status"] == "completed"
    assert final_session["total_questions"] == total_q
    assert final_session["answered_count"] == expected_answered_count
    assert final_session["resume_specific_count"] == len(resume_specific_qs)
    assert final_session["general_count"] == len(general_qs)

    answered_scores = []
    for q in final_session["questions"]:
        if q["id"] == unanswered_question["id"]:
            # Confirm unanswered question has no Answer row
            assert q["answer"] is None, f"Question {q['id']} was expected to be unanswered"
        else:
            # Confirm answered question has non-null score and valid evaluation_json
            assert q["answer"] is not None, f"Question {q['id']} should have an Answer"
            score = q["answer"]["score"]
            assert score is not None, f"Answer for question {q['id']} should have a score"
            assert isinstance(score, float)
            assert 0.0 <= score <= 10.0
            answered_scores.append(score)

            eval_json_str = q["answer"]["evaluation_json"]
            assert eval_json_str is not None, f"Answer for question {q['id']} should have evaluation_json"
            eval_data = json.loads(eval_json_str)

            # Check standard evaluation fields
            assert "overall_score" in eval_data
            assert "feedback_text" in eval_data
            assert eval_data["overall_score"] == score
            assert len(q["answer"]["feedback_text"]) > 0

    # Verify average_score reflects only the answered questions with exact arithmetic
    assert len(answered_scores) == expected_answered_count
    expected_average_score = sum(answered_scores) / len(answered_scores)
    assert final_session["average_score"] == pytest.approx(expected_average_score, rel=1e-5)
