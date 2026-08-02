from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models.session import InterviewSession, SessionReport, Question
from app.schemas.session import SessionReportResponse, QuestionAnswerReportItem
from app.services.report_generator import ReportGeneratorService
from app.config import settings

router = APIRouter(prefix="/sessions", tags=["Reports & Analytics"])

@router.get("/{session_id}/report", response_model=SessionReportResponse)
async def get_session_report(session_id: str, db: AsyncSession = Depends(get_db)):
    """
    Get completed interview session report and feedback summary.
    """
    stmt = (
        select(SessionReport)
        .where(SessionReport.session_id == session_id)
    )
    res = await db.execute(stmt)
    report = res.scalar_one_or_none()

    if not report:
        # Check if session exists and compile report on the fly if session completed
        stmt_sess = (
            select(InterviewSession)
            .where(InterviewSession.id == session_id)
            .options(
                selectinload(InterviewSession.questions).selectinload(Question.answer),
                selectinload(InterviewSession.questions).selectinload(Question.evaluation)
            )
        )
        res_sess = await db.execute(stmt_sess)
        session = res_sess.scalar_one_or_none()

        if not session:
            raise HTTPException(status_code=404, detail="Session not found.")

        report = ReportGeneratorService.compile_session_report(session)
        db.add(report)
        await db.commit()
        await db.refresh(report)

    data = report.detailed_report_json
    breakdown_items = [
        QuestionAnswerReportItem(**item) for item in data.get("detailed_breakdown", [])
    ]

    return SessionReportResponse(
        report_id=report.id,
        session_id=session_id,
        candidate_name=data.get("candidate_name", "Candidate"),
        target_role=data.get("target_role", "Software Engineer"),
        overall_score=report.overall_score,
        strengths_summary=report.strengths_summary,
        weakness_summary=report.weakness_summary,
        total_questions_answered=len(breakdown_items),
        detailed_breakdown=breakdown_items,
        compiled_at=report.compiled_at
    )


@router.get("/{session_id}/report/download")
async def download_session_report(
    session_id: str,
    format: str = Query("md", pattern="^(md|json)$")
):
    """
    Download session report as Markdown (.md) or JSON (.json).
    """
    ext = ".md" if format == "md" else ".json"
    report_file = settings.REPORTS_DIR / f"report_{session_id}{ext}"

    if not report_file.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Report file in format '{format}' not found for session {session_id}."
        )

    media_type = "text/markdown" if format == "md" else "application/json"
    return FileResponse(path=report_file, media_type=media_type, filename=report_file.name)
