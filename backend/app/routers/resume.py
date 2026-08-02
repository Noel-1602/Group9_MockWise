import uuid
from pathlib import Path
from fastapi import APIRouter, UploadFile, File, HTTPException, status, Depends
from app.schemas.session import ResumeParseResponse, StructuredResume
from app.services.resume_parser import ResumeParserService
from app.config import settings

router = APIRouter(prefix="/resume", tags=["Resume Parsing"])

@router.post("/parse", response_model=ResumeParseResponse)
async def parse_resume_endpoint(file: UploadFile = File(...)):
    """
    Upload a PDF or DOCX resume file and extract structured candidate profile.
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="Filename missing.")

    suffix = Path(file.filename).suffix.lower()
    if suffix not in [".pdf", ".docx", ".doc", ".txt"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file format: {suffix}. Allowed formats: .pdf, .docx, .txt"
        )

    # Save uploaded file to storage
    file_id = str(uuid.uuid4())
    saved_path = settings.UPLOADS_DIR / f"{file_id}_{file.filename}"
    
    contents = await file.read()
    with open(saved_path, "wb") as f:
        f.write(contents)

    # Parse using ResumeParserService
    try:
        structured_data = await ResumeParserService.parse_resume(saved_path)
        return ResumeParseResponse(status="success", parsed_resume=structured_data)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error parsing resume: {str(e)}"
        )
