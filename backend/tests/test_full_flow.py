import asyncio
import sys
from pathlib import Path

backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))

from app.models.session import InterviewSession, Question, Answer, Evaluation
from app.services.report_generator import ReportGeneratorService
from app.services.evaluator import AnswerEvaluatorService
from app.config import settings

async def test_full_session_flow():
    print("--- Running Full MockWise Session & Report Generation Test ---")
    
    # 1. Instantiate Session
    session = InterviewSession(
        candidate_name="Noel Biju",
        target_role="Software Engineer",
        total_questions=3
    )

    # 2. Add Questions
    q1 = Question(
        session_id=session.id,
        question_number=1,
        question_text="Could you introduce yourself and talk about your experience in FastAPI?",
        category="behavioral"
    )
    q2 = Question(
        session_id=session.id,
        question_number=2,
        question_text="Tell us about the speech-to-speech mock interview platform project.",
        category="resume_specific"
    )
    q3 = Question(
        session_id=session.id,
        question_number=3,
        question_text="How do you handle database concurrency and error recovery in backend services?",
        category="technical"
    )
    session.questions = [q1, q2, q3]

    # 3. Simulate Answers & Rubric Evaluations
    answers_text = [
        "I am a Computer Science student with experience building Python backend services, designing SQLite schemas, and writing RESTful APIs using FastAPI.",
        "The speech-to-speech mock interview platform processes candidate resumes, generates tailored questions, converts questions to speech audio, and transcribes candidate answers for rubric scoring.",
        "I use database connection pooling, transactions, async engines, and retry logic to gracefully recover from database connection drops."
    ]

    for q, ans_text in zip(session.questions, answers_text):
        ans = Answer(
            session_id=session.id,
            question_id=q.id,
            transcript_text=ans_text,
            duration_seconds=15.0
        )
        q.answer = ans

        eval_res = await AnswerEvaluatorService.evaluate_answer(
            question_text=q.question_text,
            transcript_text=ans_text,
            category=q.category
        )

        ev = Evaluation(
            session_id=session.id,
            question_id=q.id,
            answer_id=ans.id,
            overall_score=eval_res["overall_score"],
            clarity_score=eval_res["clarity_score"],
            relevance_score=eval_res["relevance_score"],
            communication_score=eval_res["communication_score"],
            filler_word_count=eval_res["filler_word_count"],
            feedback_text=eval_res["feedback_text"],
            strengths_json=eval_res["strengths"],
            improvements_json=eval_res["improvements"]
        )
        q.evaluation = ev
        session.evaluations.append(ev)

    # 4. Compile Session Summary Report
    report = ReportGeneratorService.compile_session_report(session)
    print(f"[✓] Session Report Compiled Successfully:")
    print(f"    Report ID: {report.id}")
    print(f"    Overall Performance Score: {report.overall_score}%")
    print(f"    Strengths Summary: {report.strengths_summary}")
    print(f"    Areas for Improvement: {report.weakness_summary}")

    # Check Markdown report export file
    md_report_path = settings.REPORTS_DIR / f"report_{session.id}.md"
    assert md_report_path.exists()
    print(f"[✓] Markdown Report Exported: {md_report_path} (Size: {md_report_path.stat().st_size} bytes)")

    print("--- FULL SESSION FLOW & REPORT GENERATION TEST PASSED ---")

if __name__ == "__main__":
    asyncio.run(test_full_session_flow())
