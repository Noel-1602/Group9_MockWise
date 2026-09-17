"""Resume parsing service package.

Provides modular pipeline stages:
- extract: raw text extraction (PDF, DOCX, TXT)
- clean: sanitization and normalization
- schema: Pydantic schemas for structured resume representation
- structure: LLM and heuristic extraction
- parser: full orchestrator pipeline
"""

from app.services.resume_parser.clean import clean_text
from app.services.resume_parser.extract import (
    CorruptedFileError,
    EmptyFileError,
    ResumeExtractionError,
    UnsupportedFileTypeError,
    extract_text,
)
from app.services.resume_parser.parser import ResumeParsingError, parse_resume
from app.services.resume_parser.schema import (
    EducationItem,
    ExperienceItem,
    ProjectItem,
    StructuredResume,
)
from app.services.resume_parser.structure import structure_resume

__all__ = [
    "clean_text",
    "extract_text",
    "structure_resume",
    "parse_resume",
    "ResumeExtractionError",
    "UnsupportedFileTypeError",
    "CorruptedFileError",
    "EmptyFileError",
    "ResumeParsingError",
    "StructuredResume",
    "ExperienceItem",
    "EducationItem",
    "ProjectItem",
]
