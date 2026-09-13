import logging
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Answer, InterviewSession, Question
from app.schemas import AnswerResponse, AnswerSubmitRequest, QuestionResponse

logger = logging.getLogger(__name__)

router = APIRouter(
    tags=["Questions"],
)


@router.post(
    "/sessions/{session_id}/questions",
    response_model=QuestionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add next question to an interview session",
)
def add_next_question(
    session_id: str,
    db: Session = Depends(get_db),
):
    """Generate and append the next question for an interview session."""
    # 1. Verify that the session exists
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

    # 2. Determine the next question index (1-based)
    try:
        max_index = (
            db.query(func.max(Question.question_index))
            .filter(Question.session_id == session_id)
            .scalar()
        )
        next_index = (max_index or 0) + 1

        # TODO: Plug in resume-based question generation service here.
        # e.g., question_text, question_type = question_generator.generate_next_question(session, next_index)
        placeholder_text = f"Placeholder interview question #{next_index}. Tell me about your background and relevant technical experience."
        placeholder_type = "general" if next_index == 1 else "technical"

        question = Question(
            session_id=session_id,
            question_index=next_index,
            question_text=placeholder_text,
            question_type=placeholder_type,
        )
        db.add(question)
        db.commit()
        db.refresh(question)
        return question
    except SQLAlchemyError as exc:
        db.rollback()
        logger.error(f"Database error while adding question to session {session_id}: {exc}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create question due to a database error.",
        )


@router.post(
    "/questions/{question_id}/answer",
    response_model=AnswerResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Submit an answer for a question",
)
def submit_answer(
    question_id: str,
    payload: AnswerSubmitRequest,
    db: Session = Depends(get_db),
):
    """Store submitted transcript for a question."""
    # 1. Verify question exists
    try:
        question = db.query(Question).filter(Question.id == question_id).first()
    except SQLAlchemyError as exc:
        logger.error(f"Database error while checking question {question_id}: {exc}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve question due to a database error.",
        )

    if not question:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Question with ID '{question_id}' not found.",
        )

    # 2. Check if an answer already exists for this question (1:0..1 relationship)
    try:
        existing_answer = db.query(Answer).filter(Answer.question_id == question_id).first()
        if existing_answer:
            # Update existing answer with new transcript
            existing_answer.transcript_text = payload.transcript_text
            # TODO: Plug in evaluation service here to calculate score & feedback_text
            existing_answer.score = payload.score if payload.score is not None else None
            existing_answer.feedback_text = payload.feedback_text if payload.feedback_text is not None else None
            db.commit()
            db.refresh(existing_answer)
            return existing_answer

        # Create new Answer
        # TODO: Plug in evaluation service here to calculate score & feedback_text
        answer = Answer(
            question_id=question_id,
            transcript_text=payload.transcript_text,
            score=payload.score if payload.score is not None else None,
            feedback_text=payload.feedback_text if payload.feedback_text is not None else None,
        )
        db.add(answer)
        db.commit()
        db.refresh(answer)
        return answer
    except SQLAlchemyError as exc:
        db.rollback()
        logger.error(f"Database error while storing answer for question {question_id}: {exc}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to save answer due to a database error.",
        )
