import uuid
from typing import List, Optional
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models.session import InterviewSession, Question
from app.schemas.session import (
    SessionDetailResponse,
    QuestionResponse,
    StructuredResume
)
from app.services.resume_parser import ResumeParserService
from app.services.question_generator import QuestionGeneratorService
from app.services.tts_service import TTSService
from app.config import settings

router = APIRouter(prefix="/sessions", tags=["Session Management"])

@router.post("/create", response_model=SessionDetailResponse)
async def create_session(
    candidate_name: Optional[str] = Form("Candidate"),
    target_role: Optional[str] = Form("Software Engineer"),
    total_questions: int = Form(6),
    resume_file: Optional[UploadFile] = File(None),
    db: AsyncSession = Depends(get_db)
):
    """
    Create a new interview session.
    Optionally accepts a resume file. Extracts resume, generates tailored questions,
    synthesizes speech audio for question 1, and initializes session state.
    """
    resume_path_str = None
    parsed_resume_data = None

    if resume_file and resume_file.filename:
        file_id = str(uuid.uuid4())
        saved_path = settings.UPLOADS_DIR / f"{file_id}_{resume_file.filename}"
        contents = await resume_file.read()
        with open(saved_path, "wb") as f:
            f.write(contents)
        resume_path_str = str(saved_path)

        # Parse resume into structured profile
        parsed_resume_obj = await ResumeParserService.parse_resume(saved_path)
        parsed_resume_data = parsed_resume_obj.model_dump()
        if parsed_resume_obj.candidate_name and parsed_resume_obj.candidate_name != "Candidate":
            candidate_name = parsed_resume_obj.candidate_name
    else:
        # Construct default structured profile
        default_profile = StructuredResume(
            candidate_name=candidate_name or "Candidate",
            skills=["Software Development", "Problem Solving", "APIs"],
            projects=[{"title": "Web Application", "description": "Developed fullstack web application."}]
        )
        parsed_resume_data = default_profile.model_dump()

    # Create InterviewSession record
    session_id = str(uuid.uuid4())
    session = InterviewSession(
        id=session_id,
        candidate_name=candidate_name or "Candidate",
        target_role=target_role or "Software Engineer",
        resume_path=resume_path_str,
        parsed_resume_json=parsed_resume_data,
        status="GENERATING_QUESTIONS",
        total_questions=total_questions,
        current_question_index=0
    )
    db.add(session)
    await db.commit()

    # Generate personalized questions
    resume_struct = StructuredResume(**parsed_resume_data)
    raw_questions = await QuestionGeneratorService.generate_questions(
        resume=resume_struct,
        target_role=target_role or "Software Engineer",
        num_questions=total_questions
    )

    # Save Question models & synthesize audio for Q1
    created_questions = []
    for idx, q_item in enumerate(raw_questions, start=1):
        q_id = str(uuid.uuid4())
        q_text = q_item.get("question_text", "Could you introduce yourself?")
        q_cat = q_item.get("category", "technical")

        # Synthesize audio for Q1 immediately
        audio_path_str = None
        if idx == 1:
            audio_path = settings.AUDIO_DIR / f"{session_id}_q1.wav"
            generated_audio = await TTSService.text_to_speech(q_text, audio_path)
            audio_path_str = str(generated_audio)

        question = Question(
            id=q_id,
            session_id=session_id,
            question_number=idx,
            question_text=q_text,
            category=q_cat,
            tts_audio_path=audio_path_str
        )
        db.add(question)
        created_questions.append(question)

    session.status = "IN_PROGRESS"
    await db.commit()
    await db.refresh(session)

    # Fetch with relations
    stmt = (
        select(InterviewSession)
        .where(InterviewSession.id == session_id)
        .options(selectinload(InterviewSession.questions))
    )
    res = await db.execute(stmt)
    full_session = res.scalar_one()

    return _to_session_detail_response(full_session)


@router.get("/{session_id}", response_model=SessionDetailResponse)
async def get_session(session_id: str, db: AsyncSession = Depends(get_db)):
    """Fetch session details, questions, current question, and state."""
    stmt = (
        select(InterviewSession)
        .where(InterviewSession.id == session_id)
        .options(selectinload(InterviewSession.questions))
    )
    res = await db.execute(stmt)
    session = res.scalar_one_or_none()

    if not session:
        raise HTTPException(status_code=404, detail="Session not found.")

    return _to_session_detail_response(session)


@router.get("", response_model=List[SessionDetailResponse])
async def list_sessions(db: AsyncSession = Depends(get_db)):
    """List all interview sessions."""
    stmt = (
        select(InterviewSession)
        .options(selectinload(InterviewSession.questions))
        .order_by(InterviewSession.created_at.desc())
    )
    res = await db.execute(stmt)
    sessions = res.scalars().all()
    return [_to_session_detail_response(s) for s in sessions]


def _to_session_detail_response(session: InterviewSession) -> SessionDetailResponse:
    q_responses = []
    current_q_resp = None

    for q in session.questions:
        audio_url = f"{settings.API_PREFIX}/speech/questions/{q.id}/audio" if q.tts_audio_path else None
        q_resp = QuestionResponse(
            id=q.id,
            session_id=q.session_id,
            question_number=q.question_number,
            question_text=q.question_text,
            category=q.category,
            audio_url=audio_url,
            created_at=q.created_at
        )
        q_responses.append(q_resp)
        if session.current_question_index < len(session.questions) and q.question_number == session.current_question_index + 1:
            current_q_resp = q_resp

    parsed_res = StructuredResume(**session.parsed_resume_json) if session.parsed_resume_json else None

    return SessionDetailResponse(
        id=session.id,
        candidate_name=session.candidate_name,
        target_role=session.target_role,
        status=session.status,
        total_questions=session.total_questions,
        current_question_index=session.current_question_index,
        created_at=session.created_at,
        parsed_resume=parsed_res,
        questions=q_responses,
        current_question=current_q_resp
    )
