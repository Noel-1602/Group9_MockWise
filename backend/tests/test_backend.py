import os
import sys
import pytest
from pathlib import Path

# Add backend dir to sys.path
backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))

from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_health_check():
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "providers" in data

def test_create_session_and_interview_flow():
    # 1. Create Session
    response = client.post(
        "/api/sessions/create",
        data={
            "candidate_name": "Alex Smith",
            "target_role": "Backend Engineer",
            "total_questions": 3
        }
    )
    assert response.status_code == 200
    session_data = response.json()
    session_id = session_data["id"]
    assert session_data["candidate_name"] == "Alex Smith"
    assert session_data["target_role"] == "Backend Engineer"
    assert len(session_data["questions"]) == 3
    assert session_data["status"] == "IN_PROGRESS"

    q1 = session_data["questions"][0]

    # 2. Get Question Audio
    audio_resp = client.get(f"/api/speech/questions/{q1['id']}/audio")
    assert audio_resp.status_code == 200
    assert len(audio_resp.content) > 0

    # 3. Submit Answer for Q1
    ans1_resp = client.post(
        f"/api/sessions/{session_id}/questions/{q1['id']}/answer",
        data={
            "transcript_text": "I am a backend developer experienced in Python, FastAPI, SQLite, and building RESTful microservices.",
            "duration_seconds": 12.5
        }
    )
    assert ans1_resp.status_code == 200
    ans1_data = ans1_resp.json()
    assert ans1_data["evaluation_score"] >= 50
    assert ans1_data["session_completed"] is False
    assert ans1_data["next_question"] is not None

    q2 = ans1_data["next_question"]

    # 4. Submit Answer for Q2
    ans2_resp = client.post(
        f"/api/sessions/{session_id}/questions/{q2['id']}/answer",
        data={
            "transcript_text": "I designed a database schema with foreign keys and index optimization to maintain consistency.",
            "duration_seconds": 10.0
        }
    )
    assert ans2_resp.status_code == 200
    ans2_data = ans2_resp.json()
    assert ans2_data["session_completed"] is False

    q3 = ans2_data["next_question"]

    # 5. Submit Answer for Q3 (Final Question)
    ans3_resp = client.post(
        f"/api/sessions/{session_id}/questions/{q3['id']}/answer",
        data={
            "transcript_text": "I aim to build high performance scalable backends and continue learning distributed systems.",
            "duration_seconds": 15.0
        }
    )
    assert ans3_resp.status_code == 200
    ans3_data = ans3_resp.json()
    assert ans3_data["session_completed"] is True

    # 6. Fetch Compiled Session Report
    report_resp = client.get(f"/api/sessions/{session_id}/report")
    assert report_resp.status_code == 200
    report_data = report_resp.json()
    assert report_data["session_id"] == session_id
    assert report_data["overall_score"] > 0
    assert len(report_data["detailed_breakdown"]) == 3

def test_standalone_tts_and_stt():
    # Test TTS
    tts_resp = client.post("/api/speech/tts", data={"text": "Hello world from MockWise"})
    assert tts_resp.status_code == 200
    assert len(tts_resp.content) > 0

if __name__ == "__main__":
    print("--- Running Backend API Endpoint Tests ---")
    test_health_check()
    print("[✓] Health Check passed")
    test_create_session_and_interview_flow()
    print("[✓] Session & Interview Flow passed")
    test_standalone_tts_and_stt()
    print("[✓] TTS & STT Standalone endpoints passed")
    print("--- ALL BACKEND ENDPOINT TESTS PASSED SUCCESSFULLY ---")

