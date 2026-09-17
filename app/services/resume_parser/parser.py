"""Orchestrator pipeline connecting extract, clean, and structure stages."""

import logging
from typing import Callable, Optional

from app.services.resume_parser.clean import clean_text
from app.services.resume_parser.extract import (
    CorruptedFileError,
    EmptyFileError,
    ResumeExtractionError,
    UnsupportedFileTypeError,
    extract_text,
)
from app.services.resume_parser.schema import StructuredResume
from app.services.resume_parser.structure import (
    heuristic_structure_resume,
    structure_resume,
)

logger = logging.getLogger(__name__)


class ResumeParsingError(Exception):
    """Exception raised when the resume parsing pipeline fails."""
    pass


def parse_resume(
    content: bytes,
    filename: str,
    llm_callable: Optional[Callable[[str], str]] = None,
) -> StructuredResume:
    """Run the full resume parsing pipeline: extract -> clean -> structure.

    Args:
        content: Raw file content in bytes.
        filename: Name of the uploaded file.
        llm_callable: Optional callable for LLM invocation.

    Returns:
        StructuredResume instance with parsed data and raw text.

    Raises:
        EmptyFileError: If file has 0 bytes.
        UnsupportedFileTypeError: If file format is not supported.
        CorruptedFileError: If file extraction encounters a format corruption.
        ResumeParsingError: If any pipeline stage fails unexpectedly.
    """
    logger.info(f"Starting resume parsing pipeline for file: {filename} ({len(content)} bytes)")

    # 1. Text Extraction
    try:
        raw_text = extract_text(content=content, filename=filename)
    except (EmptyFileError, UnsupportedFileTypeError, CorruptedFileError):
        raise
    except Exception as exc:
        logger.error(f"Unexpected extraction failure for {filename}: {exc}", exc_info=True)
        raise ResumeParsingError(f"Failed to extract text from {filename}: {exc}") from exc

    if not raw_text or not raw_text.strip():
        raise ResumeParsingError(f"Extracted text from {filename} is empty or unreadable.")

    # 2. Text Cleaning & Normalization
    try:
        cleaned_text = clean_text(raw_text)
    except Exception as exc:
        logger.error(f"Text cleaning failure for {filename}: {exc}", exc_info=True)
        # Fall back to raw text if cleaning raises an unexpected error
        cleaned_text = raw_text

    # 3. Structuring
    try:
        if llm_callable is not None:
            structured = structure_resume(cleaned_text, llm_callable=llm_callable)
        else:
            structured = heuristic_structure_resume(cleaned_text)
        # Ensure raw_text is stored
        structured.raw_text = raw_text
        logger.info(f"Resume parsing completed successfully for {filename}")
        return structured
    except Exception as exc:
        logger.error(f"Resume structuring failed for {filename}: {exc}", exc_info=True)
        raise ResumeParsingError(f"Failed to structure resume content: {exc}") from exc
