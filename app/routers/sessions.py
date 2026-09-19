import json
import logging
import os
import tempfile
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Answer, InterviewSession, Question, Resume, SessionStatus
from app.schemas import ResumeResponse, SessionCreateRequest, SessionResponse
from app.services.evaluation import evaluate_answer
from app.services.resume_parser import (
    ResumeParsingError,
    UnsupportedFileTypeError,
    parse_resume,
)
from app.services.resume_parser.schema import ParsedResume

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/sessions",
    tags=["Sessions"],
)


def _populate_session_summary(session: InterviewSession) -> InterviewSession:
    """Compute summary metrics from session's existing questions/answers relationships and attach to the session."""
    questions = session.questions or []
    total_questions = len(questions)
    answered_questions = [q for q in questions if q.answer is not None]
    answered_count = len(answered_questions)

    scored_values = [
        q.answer.score for q in answered_questions if q.answer.score is not None
    ]
    average_score = (sum(scored_values) / len(scored_values)) if scored_values else None

    resume_specific_count = sum(1 for q in questions if q.question_type == "resume_specific")
    general_count = sum(1 for q in questions if q.question_type == "general")

    session.total_questions = total_questions
    session.answered_count = answered_count
    session.average_score = average_score
    session.resume_specific_count = resume_specific_count
    session.general_count = general_count
    return session


@router.post(
    "",
    response_model=SessionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new interview session",
)
def create_session(
    payload: SessionCreateRequest,
    db: Session = Depends(get_db),
):
    """Create a new interview session record."""
    try:
        session = InterviewSession(
            candidate_name=payload.candidate_name,
            resume_filename=payload.resume_filename,
            status=SessionStatus.in_progress,
        )
        db.add(session)
        db.commit()
        db.refresh(session)
        return _populate_session_summary(session)
    except SQLAlchemyError as exc:
        db.rollback()
        logger.error(f"Database error while creating session: {exc}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create session due to a database error.",
        )


@router.get(
    "/{session_id}",
    response_model=SessionResponse,
    status_code=status.HTTP_200_OK,
    summary="Fetch an interview session by ID",
)
def get_session(
    session_id: str,
    db: Session = Depends(get_db),
):
    """Fetch an interview session along with its resume, questions, and answers."""
    try:
        session = db.query(InterviewSession).filter(InterviewSession.id == session_id).first()
    except SQLAlchemyError as exc:
        logger.error(f"Database error while fetching session {session_id}: {exc}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve session due to a database error.",
        )

    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Interview session with ID '{session_id}' not found.",
        )

    return _populate_session_summary(session)


@router.post(
    "/{session_id}/complete",
    response_model=SessionResponse,
    status_code=status.HTTP_200_OK,
    summary="Mark an interview session as completed",
)
def complete_session(
    session_id: str,
    db: Session = Depends(get_db),
):
    """Mark an existing interview session as completed and evaluate unscored answers."""
    try:
        session = db.query(InterviewSession).filter(InterviewSession.id == session_id).first()
    except SQLAlchemyError as exc:
        logger.error(f"Database error while finding session {session_id} for completion: {exc}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update session due to a database error.",
        )

    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Interview session with ID '{session_id}' not found.",
        )

    try:
        session.status = SessionStatus.completed

        answers_with_questions = (
            db.query(Answer, Question)
            .join(Question, Answer.question_id == Question.id)
            .filter(Question.session_id == session_id)
            .all()
        )

        for answer, question in answers_with_questions:
            if answer.score is not None:
                continue

            transcript = answer.transcript_text or ""
            if not transcript.strip():
                continue

            result = evaluate_answer(
                question_text=question.question_text,
                transcript_text=transcript,
                backend="mock",
            )
            answer.score = result.overall_score
            answer.feedback_text = result.feedback_text
            answer.evaluation_json = result.model_dump_json()

        db.commit()
        db.refresh(session)
        return _populate_session_summary(session)
    except SQLAlchemyError as exc:
        db.rollback()
        logger.error(f"Database error while marking session {session_id} completed: {exc}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update session due to a database error.",
        )


@router.post(
    "/{session_id}/resume",
    response_model=ResumeResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload and parse resume for an interview session",
)
async def upload_session_resume(
    session_id: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """Upload and parse a resume file, associating it with an interview session."""
    filename = file.filename or ""
    _, ext = os.path.splitext(filename)
    ext_lower = ext.lower()

    if ext_lower not in [".pdf", ".docx"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file format '{ext}'. Only PDF and DOCX files are supported.",
        )

    try:
        session = db.query(InterviewSession).filter(InterviewSession.id == session_id).first()
    except SQLAlchemyError as exc:
        logger.error(f"Database error while checking session {session_id}: {exc}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve session due to a database error.",
        )

    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Interview session with ID '{session_id}' not found.",
        )

    content = await file.read()
    if not content:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file is empty.",
        )

    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=ext_lower)
    temp_path = temp_file.name
    try:
        temp_file.write(content)
        temp_file.flush()
        temp_file.close()

        parsed_resume = parse_resume(temp_path, backend="mock")
    except UnsupportedFileTypeError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )
    except ResumeParsingError as exc:
        logger.error(f"Resume parsing error for session {session_id}: {exc}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to parse resume content.",
        )
    except Exception as exc:
        logger.error(f"Unexpected error while parsing resume for session {session_id}: {exc}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while parsing the resume.",
        )
    finally:
        if os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except OSError:
                pass

    if hasattr(parsed_resume, "to_db_columns"):
        cols = parsed_resume.to_db_columns()
        skills_json = cols.get("skills_json")
        projects_json = cols.get("projects_json")
        experience_json = cols.get("experience_json")
        education_json = cols.get("education_json")
        raw_text = getattr(parsed_resume, "raw_text", None)
    elif hasattr(parsed_resume, "to_db_json"):
        cols = parsed_resume.to_db_json()
        skills_json = cols.get("skills_json")
        projects_json = cols.get("projects_json")
        experience_json = cols.get("experience_json")
        education_json = cols.get("education_json")
        raw_text = cols.get("raw_text")
    else:
        skills_json = json.dumps(getattr(parsed_resume, "skills", []))
        projects = getattr(parsed_resume, "projects", [])
        projects_json = json.dumps([
            p.model_dump() if hasattr(p, "model_dump") else p
            for p in projects
        ])
        experience_json = json.dumps(getattr(parsed_resume, "experience", []))
        education_json = json.dumps(getattr(parsed_resume, "education", []))
        raw_text = getattr(parsed_resume, "raw_text", None)

    try:
        existing_resume = db.query(Resume).filter(Resume.session_id == session_id).first()
        if existing_resume:
            existing_resume.skills_json = skills_json
            existing_resume.projects_json = projects_json
            existing_resume.experience_json = experience_json
            existing_resume.education_json = education_json
            existing_resume.raw_text = raw_text
            resume_record = existing_resume
        else:
            resume_record = Resume(
                session_id=session_id,
                skills_json=skills_json,
                projects_json=projects_json,
                experience_json=experience_json,
                education_json=education_json,
                raw_text=raw_text,
            )
            db.add(resume_record)

        session.resume_filename = filename
        db.commit()
        db.refresh(resume_record)

        # Trigger question generation for this session (guarded against duplicate batches)
        from app.routers.questions import generate_and_save_questions_for_session
        generate_and_save_questions_for_session(
            session_id=session_id,
            db=db,
            parsed_resume=parsed_resume if isinstance(parsed_resume, ParsedResume) else None,
        )

        return resume_record
    except SQLAlchemyError as exc:
        db.rollback()
        logger.error(f"Database error while saving resume for session {session_id}: {exc}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to save resume due to a database error.",
        )

