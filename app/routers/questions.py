import json
import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile, status
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Answer, InterviewSession, Question, Resume
from app.schemas import AnswerResponse, AnswerSubmitRequest, QuestionResponse
from app.services.question_generator import generate_questions
from app.services.resume_parser.schema import ParsedResume, ResumeProject
from app.services.stt import transcribe_audio
from app.services.tts import synthesize_speech

logger = logging.getLogger(__name__)

router = APIRouter(
    tags=["Questions"],
)


def generate_and_save_questions_for_session(
    session_id: str,
    db: Session,
    parsed_resume: Optional[ParsedResume] = None,
) -> List[Question]:
    """Generate and persist Question rows for an interview session if not already present.

    Guards against double-triggering on retries by checking for existing Question rows first.
    """
    existing_questions = (
        db.query(Question)
        .filter(Question.session_id == session_id)
        .order_by(Question.question_index.asc())
        .all()
    )
    if existing_questions:
        logger.info(f"Questions already exist for session {session_id}; skipping generation.")
        return existing_questions

    if parsed_resume is None or not isinstance(parsed_resume, ParsedResume):
        resume_record = db.query(Resume).filter(Resume.session_id == session_id).first()
        if resume_record:
            skills = json.loads(resume_record.skills_json) if resume_record.skills_json else []
            projects_data = json.loads(resume_record.projects_json) if resume_record.projects_json else []
            projects = [
                ResumeProject(**p) if isinstance(p, dict) else ResumeProject(title=str(p), description="")
                for p in projects_data
            ]
            experience = json.loads(resume_record.experience_json) if resume_record.experience_json else []
            education = json.loads(resume_record.education_json) if resume_record.education_json else []
            parsed_resume = ParsedResume(
                skills=skills,
                projects=projects,
                experience=experience,
                education=education,
            )
        else:
            parsed_resume = ParsedResume()

    generated_questions = generate_questions(parsed_resume, backend="mock", count=None)

    created_questions: List[Question] = []
    for idx, gq in enumerate(generated_questions):
        question = Question(
            session_id=session_id,
            question_index=idx,
            question_text=gq.question_text,
            question_type=gq.type,
        )
        db.add(question)
        created_questions.append(question)

    db.commit()
    for q in created_questions:
        db.refresh(q)

    logger.info(f"Generated and saved {len(created_questions)} questions for session {session_id}.")
    return created_questions


@router.get(
    "/sessions/{session_id}/questions/next",
    response_model=QuestionResponse,
    status_code=status.HTTP_200_OK,
    summary="Fetch the next unanswered question for an interview session",
)
def get_next_unanswered_question(
    session_id: str,
    db: Session = Depends(get_db),
):
    """Retrieve the next unanswered question for the given session ordered by question_index."""
    try:
        session = db.query(InterviewSession).filter(InterviewSession.id == session_id).first()
    except SQLAlchemyError as exc:
        logger.error(f"Database error checking session {session_id}: {exc}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve session due to a database error.",
        )

    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Interview session with ID '{session_id}' not found.",
        )

    try:
        next_q = (
            db.query(Question)
            .outerjoin(Answer, Question.id == Answer.question_id)
            .filter(Question.session_id == session_id, Answer.id == None)
            .order_by(Question.question_index.asc())
            .first()
        )
    except SQLAlchemyError as exc:
        logger.error(f"Database error fetching next question for session {session_id}: {exc}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve question due to a database error.",
        )

    if not next_q:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No unanswered questions remaining for session '{session_id}'.",
        )

    return next_q


def _get_question_or_404(question_id: str, db: Session) -> Question:
    """Verify and retrieve question by ID, raising 404 if not found or 500 on DB error."""
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
    return question


def _ensure_question_not_answered(question_id: str, db: Session) -> None:
    """Verify question has not already been answered or skipped, raising 400 if it has or 500 on DB error."""
    try:
        existing_answer = db.query(Answer).filter(Answer.question_id == question_id).first()
    except SQLAlchemyError as exc:
        logger.error(f"Database error while checking existing answer for question {question_id}: {exc}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve question due to a database error.",
        )

    if existing_answer:
        action = "skipped" if existing_answer.skipped else "submitted"
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"An answer has already been {action} for question ID '{question_id}'.",
        )


@router.post(
    "/questions/{question_id}/skip",
    response_model=AnswerResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Skip an interview question",
)
def skip_question(
    question_id: str,
    db: Session = Depends(get_db),
):
    """Mark a question as skipped by creating an Answer row with skipped=True."""
    _get_question_or_404(question_id, db)
    _ensure_question_not_answered(question_id, db)

    try:
        answer = Answer(
            question_id=question_id,
            transcript_text=None,
            score=None,
            feedback_text=None,
            evaluation_json=None,
            skipped=True,
        )
        db.add(answer)
        db.commit()
        db.refresh(answer)
        return answer
    except SQLAlchemyError as exc:
        db.rollback()
        logger.error(f"Database error while skipping question {question_id}: {exc}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to skip question due to a database error.",
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
    _get_question_or_404(question_id, db)
    _ensure_question_not_answered(question_id, db)

    try:
        answer = Answer(
            question_id=question_id,
            transcript_text=payload.transcript_text,
            score=payload.score if payload.score is not None else None,
            feedback_text=payload.feedback_text if payload.feedback_text is not None else None,
            skipped=False,
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



@router.post(
    "/questions/{question_id}/answer/audio",
    response_model=AnswerResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Submit an audio answer for a question",
)
async def submit_audio_answer(
    question_id: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """Transcribe uploaded audio file and store answer for a question."""
    _get_question_or_404(question_id, db)
    _ensure_question_not_answered(question_id, db)

    audio_bytes = await file.read()

    try:
        transcript_text = transcribe_audio(audio_bytes, backend="mock")
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc) or "Uploaded audio file cannot be empty.",
        )

    try:
        answer = Answer(
            question_id=question_id,
            transcript_text=transcript_text,
            score=None,
            feedback_text=None,
        )
        db.add(answer)
        db.commit()
        db.refresh(answer)
        return answer
    except SQLAlchemyError as exc:
        db.rollback()
        logger.error(f"Database error while storing audio answer for question {question_id}: {exc}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to save answer due to a database error.",
        )


@router.get(
    "/questions/{question_id}/audio",
    status_code=status.HTTP_200_OK,
    summary="Fetch synthesized audio for a question",
)
def get_question_audio(
    question_id: str,
    db: Session = Depends(get_db),
):
    """Synthesize speech audio for the question text and return as WAV audio bytes."""
    question = _get_question_or_404(question_id, db)
    audio_bytes = synthesize_speech(question.question_text, backend="mock")
    return Response(content=audio_bytes, media_type="audio/wav")


