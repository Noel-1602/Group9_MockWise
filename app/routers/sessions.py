import logging
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import InterviewSession, Resume, SessionStatus
from app.schemas import ResumeResponse, SessionCreateRequest, SessionResponse
from app.services.resume_parser import (
    CorruptedFileError,
    EmptyFileError,
    ResumeParsingError,
    UnsupportedFileTypeError,
    parse_resume,
)

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/sessions",
    tags=["Sessions"],
)


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
        return session
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

    return session


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
    """Mark an existing interview session as completed."""
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
        db.commit()
        db.refresh(session)
        return session
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

    filename = file.filename or "resume.pdf"
    content = await file.read()
    if not content:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Uploaded file '{filename}' is empty.",
        )

    try:
        parsed_resume = parse_resume(content=content, filename=filename)
    except (UnsupportedFileTypeError, EmptyFileError) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )
    except CorruptedFileError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        )
    except ResumeParsingError as exc:
        logger.error(f"Resume parsing error for session {session_id}: {exc}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to parse resume content.",
        )

    resume_data = parsed_resume.to_db_json()

    try:
        existing_resume = db.query(Resume).filter(Resume.session_id == session_id).first()
        if existing_resume:
            existing_resume.skills_json = resume_data["skills_json"]
            existing_resume.projects_json = resume_data["projects_json"]
            existing_resume.experience_json = resume_data["experience_json"]
            existing_resume.education_json = resume_data["education_json"]
            existing_resume.raw_text = resume_data["raw_text"]
            resume_record = existing_resume
        else:
            resume_record = Resume(
                session_id=session_id,
                **resume_data,
            )
            db.add(resume_record)

        session.resume_filename = filename
        if not session.candidate_name and parsed_resume.candidate_name:
            session.candidate_name = parsed_resume.candidate_name

        db.commit()
        db.refresh(resume_record)
        return resume_record
    except SQLAlchemyError as exc:
        db.rollback()
        logger.error(f"Database error while saving resume for session {session_id}: {exc}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to save resume due to a database error.",
        )
