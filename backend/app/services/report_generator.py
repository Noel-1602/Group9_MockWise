import json
import logging
from pathlib import Path
from typing import Dict, Any, List
from datetime import datetime, timezone

from app.models.session import InterviewSession, SessionReport
from app.schemas.session import QuestionAnswerReportItem, SessionReportResponse
from app.config import settings

logger = logging.getLogger("mockwise.report_generator")

class ReportGeneratorService:

    @classmethod
    def compile_session_report(cls, session: InterviewSession) -> SessionReport:
        """
        Compile full session results into a structured SessionReport ORM object.
        """
        total_questions = len(session.questions)
        answered_evaluations = [q.evaluation for q in session.questions if q.evaluation]
        
        if not answered_evaluations:
            overall_score = 70
            strengths_summary = "Completed mock interview session."
            weakness_summary = "Practice answering questions thoroughly."
            detailed_items = []
        else:
            scores = [e.overall_score for e in answered_evaluations]
            overall_score = round(sum(scores) / len(scores))

            # Gather all strengths and improvements
            all_strengths = []
            all_improvements = []
            detailed_items = []

            for q in session.questions:
                if q.answer and q.evaluation:
                    ev = q.evaluation
                    ans = q.answer
                    
                    if ev.strengths_json:
                        all_strengths.extend(ev.strengths_json)
                    if ev.improvements_json:
                        all_improvements.extend(ev.improvements_json)

                    detailed_items.append({
                        "question_number": q.question_number,
                        "question_text": q.question_text,
                        "category": q.category,
                        "transcript_text": ans.transcript_text,
                        "score": ev.overall_score,
                        "clarity_score": ev.clarity_score,
                        "relevance_score": ev.relevance_score,
                        "communication_score": ev.communication_score,
                        "filler_words": ev.filler_word_count,
                        "feedback": ev.feedback_text
                    })

            # Unique top strengths & weaknesses
            unique_strengths = list(dict.fromkeys(all_strengths))[:3]
            unique_improvements = list(dict.fromkeys(all_improvements))[:3]

            strengths_summary = "; ".join(unique_strengths) if unique_strengths else "Good communication and domain relevance."
            weakness_summary = "; ".join(unique_improvements) if unique_improvements else "Focus on providing deeper technical implementation details."

        report_data = {
            "session_id": session.id,
            "candidate_name": session.candidate_name,
            "target_role": session.target_role,
            "overall_score": overall_score,
            "strengths_summary": strengths_summary,
            "weakness_summary": weakness_summary,
            "detailed_breakdown": detailed_items
        }

        # Save to disk as JSON file
        report_file = settings.REPORTS_DIR / f"report_{session.id}.json"
        with open(report_file, "w") as f:
            json.dump(report_data, f, indent=2)

        # Also write a Markdown export version
        md_file = settings.REPORTS_DIR / f"report_{session.id}.md"
        cls.export_markdown_report(report_data, md_file)

        session_report = SessionReport(
            session_id=session.id,
            overall_score=overall_score,
            strengths_summary=strengths_summary,
            weakness_summary=weakness_summary,
            detailed_report_json=report_data
        )

        return session_report

    @staticmethod
    def export_markdown_report(data: Dict[str, Any], output_path: Path):
        """Export session report to Markdown format."""
        md = f"""# MockWise Interview Evaluation Report

**Candidate Name**: {data.get('candidate_name')}  
**Target Role**: {data.get('target_role')}  
**Overall Performance Score**: {data.get('overall_score')}%  
**Generated At**: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}  

---

## Executive Summary

- **Key Strengths**: {data.get('strengths_summary')}
- **Areas for Improvement**: {data.get('weakness_summary')}

---

## Detailed Question & Answer Breakdown

"""
        for item in data.get("detailed_breakdown", []):
            md += f"""### Question {item['question_number']} ({item['category'].title()})
**Question**: {item['question_text']}  
**Transcript**: "{item['transcript_text']}"  
**Score**: {item['score']}% (Clarity: {item['clarity_score']}, Relevance: {item['relevance_score']}, Communication: {item['communication_score']})  
**Filler Words**: {item['filler_words']}  
**Feedback**: {item['feedback']}  

---
"""
        with open(output_path, "w") as f:
            f.write(md)
