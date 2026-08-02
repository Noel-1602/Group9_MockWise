import uuid
from pathlib import Path
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models.session import InterviewSession, Question, Answer, Evaluation
from app.schemas.session import AnswerSubmitResponse, QuestionResponse
from app.services.stt_service import STTService
from app.services.tts_service import TTSService
from app.services.evaluator import AnswerEvaluatorService
from app.services.report_generator import ReportGeneratorService
from app.config import settings

router = APIRouter(prefix="/sessions", tags=["Answer & Evaluation Pipeline"])

@router.post("/{session_id}/questions/{question_id}/answer", response_model=AnswerSubmitResponse)
async def submit_answer(
    session_id: str,
    question_id: str,
    audio_file: Optional[UploadFile] = File(None),
    transcript_text: Optional[str] = Form(None),
    duration_seconds: float = Form(0.0),
    db: AsyncSession = Depends(get_db)
):
    """
    Submit answer for a specific question (audio file or text fallback).
    Transcribes audio, evaluates against scoring rubric, updates session state,
    synthesizes next question TTS audio, and returns score and feedback.
    """
    # Fetch session with questions
    stmt = (
        select(InterviewSession)
        .where(InterviewSession.id == session_id)
        .options(selectinload(InterviewSession.questions))
    )
    res = await db.execute(stmt)
    session = res.scalar_one_or_none()

    if not session:
        raise HTTPException(status_code=404, detail="Session not found.")

    # Find question
    question = next((q for q in session.questions if q.id == question_id), None)
    if not question:
        raise HTTPException(status_code=404, detail="Question not found in this session.")

    # Process Audio / Transcript
    final_transcript = ""
    saved_audio_path = None

    if audio_file and audio_file.filename:
        file_id = str(uuid.uuid4())
        ext = Path(audio_file.filename).suffix or ".wav"
        target_path = settings.AUDIO_DIR / f"ans_{session_id}_{question.question_number}{ext}"
        
        contents = await audio_file.read()
        with open(target_path, "wb") as f:
            f.write(contents)
        saved_audio_path = str(target_path)

        # Transcribe audio file
        final_transcript = await STTService.transcribe_audio(target_path)
    elif transcript_text:
        final_transcript = transcript_text.strip()
    else:
        raise HTTPException(
            status_code=400,
            detail="Either an audio file or transcript_text must be provided."
        )

    # Save Answer record
    answer_id = str(uuid.uuid4())
    answer = Answer(
        id=answer_id,
        session_id=session_id,
        question_id=question_id,
        audio_path=saved_audio_path,
        transcript_text=final_transcript,
        duration_seconds=duration_seconds
    )
    db.add(answer)
    await db.commit()

    # Evaluate Answer using Rubric
    eval_result = await AnswerEvaluatorService.evaluate_answer(
        question_text=question.question_text,
        transcript_text=final_transcript,
        category=question.category
    )

    evaluation_id = str(uuid.uuid4())
    evaluation = Evaluation(
        id=evaluation_id,
        session_id=session_id,
        question_id=question_id,
        answer_id=answer_id,
        overall_score=eval_result["overall_score"],
        clarity_score=eval_result["clarity_score"],
        relevance_score=eval_result["relevance_score"],
        communication_score=eval_result["communication_score"],
        filler_word_count=eval_result["filler_word_count"],
        feedback_text=eval_result["feedback_text"],
        strengths_json=eval_result["strengths"],
        improvements_json=eval_result["improvements"]
    )
    db.add(evaluation)

    # Update session progress turn state
    session.current_question_index += 1
    session_completed = session.current_question_index >= len(session.questions)

    next_q_response = None

    if not session_completed:
        next_q_num = session.current_question_index + 1
        next_question = next((q for q in session.questions if q.question_number == next_q_num), None)
        
        if next_question:
            # Synthesize TTS audio for next question if not already cached
            if not next_question.tts_audio_path or not Path(next_question.tts_audio_path).exists():
                audio_target = settings.AUDIO_DIR / f"{session_id}_q{next_q_num}.wav"
                gen_audio = await TTSService.text_to_speech(next_question.question_text, audio_target)
                next_question.tts_audio_path = str(gen_audio)

            next_q_response = QuestionResponse(
                id=next_question.id,
                session_id=next_question.session_id,
                question_number=next_question.question_number,
                question_text=next_question.question_text,
                category=next_question.category,
                audio_url=f"{settings.API_PREFIX}/speech/questions/{next_question.id}/audio",
                created_at=next_question.created_at
            )
    else:
        session.status = "COMPLETED"
        # Compile session summary report
        await db.flush()
        # Fetch updated session with all answers and evaluations
        stmt_full = (
            select(InterviewSession)
            .where(InterviewSession.id == session_id)
            .options(
                selectinload(InterviewSession.questions)
                .selectinload(Question.answer),
                selectinload(InterviewSession.questions)
                .selectinload(Question.evaluation)
            )
        )
        res_full = await db.execute(stmt_full)
        completed_session = res_full.scalar_one()

        report_obj = ReportGeneratorService.compile_session_report(completed_session)
        db.add(report_obj)

    await db.commit()

    return AnswerSubmitResponse(
        answer_id=answer_id,
        question_id=question_id,
        transcript_text=final_transcript,
        evaluation_score=eval_result["overall_score"],
        clarity_score=eval_result["clarity_score"],
        relevance_score=eval_result["relevance_score"],
        communication_score=eval_result["communication_score"],
        filler_word_count=eval_result["filler_word_count"],
        feedback_text=eval_result["feedback_text"],
        strengths=eval_result["strengths"],
        improvements=eval_result["improvements"],
        next_question=next_q_response,
        session_completed=session_completed
    )
