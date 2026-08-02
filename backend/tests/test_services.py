import asyncio
import sys
from pathlib import Path

# Add backend directory to sys.path
backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))

from app.schemas.session import StructuredResume
from app.services.resume_parser import ResumeParserService
from app.services.question_generator import QuestionGeneratorService
from app.services.stt_service import STTService
from app.services.tts_service import TTSService
from app.services.evaluator import AnswerEvaluatorService
from app.config import settings

async def run_standalone_service_tests():
    print("--- Running MockWise Backend Service Diagnostic Tests ---")

    # 1. Test Resume Parser Heuristic Extraction
    raw_text = """
    Jane Doe
    Email: jane.doe@example.com
    Skills: Python, FastAPI, React, SQL, Machine Learning
    Projects:
    MockWise Interview Platform: Built an AI speech mock interview system using FastAPI and Speech-to-Text.
    Education: B.Tech Computer Science
    """
    resume_path = settings.UPLOADS_DIR / "sample_resume.txt"
    with open(resume_path, "w") as f:
        f.write(raw_text)

    parsed_resume = await ResumeParserService.parse_resume(resume_path)
    print(f"[✓] Resume Parser Output: Candidate={parsed_resume.candidate_name}, Skills={parsed_resume.skills[:3]}")

    # 2. Test Question Generator
    questions = await QuestionGeneratorService.generate_questions(
        resume=parsed_resume,
        target_role="AI Engineer",
        num_questions=4
    )
    print(f"[✓] Question Generator Output: Generated {len(questions)} questions.")
    for idx, q in enumerate(questions, start=1):
        print(f"    Q{idx} ({q['category']}): {q['question_text']}")

    # 3. Test TTS Synthesizer
    tts_output = settings.AUDIO_DIR / "test_q1.wav"
    audio_path = await TTSService.text_to_speech(questions[0]["question_text"], tts_output)
    print(f"[✓] TTS Audio Synthesizer: Generated audio file at {audio_path} (Size: {audio_path.stat().st_size} bytes)")

    # 4. Test STT Transcription
    transcript = await STTService.transcribe_audio(audio_path)
    print(f"[✓] STT Speech Transcriber: Transcript snippet: '{transcript[:80]}...'")

    # 5. Test Rubric Answer Evaluator
    eval_result = await AnswerEvaluatorService.evaluate_answer(
        question_text=questions[0]["question_text"],
        transcript_text=transcript,
        category=questions[0]["category"]
    )
    print(f"[✓] Rubric Evaluator: Overall Score={eval_result['overall_score']}%, Clarity={eval_result['clarity_score']}, Filler Count={eval_result['filler_word_count']}")
    print(f"    Feedback: {eval_result['feedback_text']}")

    print("\n--- ALL BACKEND SERVICE DIAGNOSTICS PASSED SUCCESSFULLY ---")

if __name__ == "__main__":
    asyncio.run(run_standalone_service_tests())
