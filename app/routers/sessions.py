import logging
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import InterviewSession, SessionStatus
from app.schemas import SessionCreateRequest, SessionResponse

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
