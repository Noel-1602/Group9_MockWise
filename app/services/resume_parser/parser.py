"""Orchestrator pipeline connecting extract, clean, and structure stages."""

import logging
import os
from typing import Any, Callable, Optional, Union

from pydantic import ValidationError

from app.services.resume_parser.clean import clean_resume_text, clean_text
from app.services.resume_parser.extract import (
    CorruptedFileError,
    EmptyFileError,
    ResumeExtractionError,
    UnsupportedFileTypeError,
    extract_text,
    extract_text_from_docx,
    extract_text_from_pdf,
)
from app.services.resume_parser.schema import ParsedResume, StructuredResume
from app.services.resume_parser.structure import (
    heuristic_structure_resume,
    structure_resume,
)

logger = logging.getLogger(__name__)


class ResumeParsingError(Exception):
    """Exception raised when the resume parsing pipeline fails."""
    pass


def parse_resume(
    file_path: Optional[Union[str, os.PathLike]] = None,
    backend: str = "mock",
    content: Optional[bytes] = None,
    filename: Optional[str] = None,
    llm_callable: Optional[Callable[[str], str]] = None,
    *args: Any,
    **kwargs: Any,
) -> Union[ParsedResume, StructuredResume]:
    """Run the resume parsing pipeline: extract -> clean -> structure -> validate.

    When given a file path, extracts text from PDF or DOCX, cleans it,
    structures it using the specified backend ('mock', 'ollama', 'groq'),
    and validates against the ParsedResume schema (retrying once if validation fails).

    Args:
        file_path: Absolute or relative path to the resume file (.pdf or .docx).
        backend: Structuring backend ('mock', 'ollama', 'groq'). Default is 'mock'.
        content: (Legacy) Raw binary file content in bytes.
        filename: (Legacy) Name of the uploaded file.
        llm_callable: (Legacy) Optional callable for LLM invocation.

    Returns:
        ParsedResume instance when file_path is provided, or StructuredResume
        when legacy byte content is provided.

    Raises:
        UnsupportedFileTypeError: If the file extension is not supported (.pdf, .docx).
        ResumeParsingError: If extraction, cleaning, structuring, or validation fails.
    """
    # Support legacy binary content invocation: parse_resume(content=..., filename=...) or parse_resume(bytes, filename)
    if isinstance(file_path, (bytes, bytearray)) or content is not None:
        raw_bytes = content if content is not None else file_path
        name = filename or (backend if isinstance(backend, str) and not backend.startswith("-") else "resume.pdf")
        return _parse_resume_legacy(raw_bytes, name, llm_callable)

    if file_path is None:
        if args and isinstance(args[0], (bytes, bytearray)):
            name = filename or (args[1] if len(args) > 1 else "resume.pdf")
            return _parse_resume_legacy(args[0], name, llm_callable)
        raise ResumeParsingError("No file path or content provided to parse_resume.")

    path_str = str(file_path)
    target_backend = kwargs.get("backend", backend)

    logger.info(f"Starting resume parsing for '{path_str}' using backend '{target_backend}'")

    # 1. Detect PDF vs DOCX by file extension and extract text
    _, ext = os.path.splitext(path_str)
    ext_lower = ext.lower()

    if ext_lower == ".pdf":
        try:
            raw_text = extract_text_from_pdf(path_str)
        except Exception as exc:
            logger.error(f"Failed to extract text from PDF '{path_str}': {exc}", exc_info=True)
            raise ResumeParsingError(f"Failed to extract text from PDF '{path_str}': {exc}") from exc
    elif ext_lower == ".docx":
        try:
            raw_text = extract_text_from_docx(path_str)
        except Exception as exc:
            logger.error(f"Failed to extract text from DOCX '{path_str}': {exc}", exc_info=True)
            raise ResumeParsingError(f"Failed to extract text from DOCX '{path_str}': {exc}") from exc
    else:
        raise UnsupportedFileTypeError(
            f"Unsupported file format '{ext}'. Only .pdf and .docx are supported by parse_resume."
        )

    # 2. Clean text
    cleaned_text = clean_resume_text(raw_text)

    # 3, 4, 5. Structure, validate against ParsedResume schema, with 1 retry on validation failure
    def _attempt_structuring() -> ParsedResume:
        raw_result = structure_resume(cleaned_text, backend=target_backend)
        if isinstance(raw_result, ParsedResume):
            return raw_result
        if not isinstance(raw_result, dict):
            raise ResumeParsingError(
                f"Expected dict from structure_resume, got {type(raw_result).__name__}"
            )
        return ParsedResume.model_validate(raw_result)

    try:
        return _attempt_structuring()
    except (ValidationError, Exception) as first_err:
        logger.warning(
            f"First structuring/validation attempt failed for '{path_str}' ({first_err}); retrying once..."
        )
        try:
            return _attempt_structuring()
        except Exception as retry_err:
            logger.error(
                f"Resume structuring/validation failed after retry for '{path_str}': {retry_err}",
                exc_info=True,
            )
            raise ResumeParsingError(
                f"Failed to structure and validate resume from '{path_str}': {retry_err}"
            ) from retry_err


def _parse_resume_legacy(
    content: bytes,
    filename: str,
    llm_callable: Optional[Callable[[str], str]] = None,
) -> StructuredResume:
    """Run the legacy full resume parsing pipeline: extract -> clean -> structure."""
    logger.info(f"Starting legacy resume parsing pipeline for file: {filename} ({len(content)} bytes)")

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
        cleaned_text = raw_text

    # 3. Structuring
    try:
        if llm_callable is not None:
            structured = structure_resume(cleaned_text, llm_callable=llm_callable)
        else:
            structured = heuristic_structure_resume(cleaned_text)
        structured.raw_text = raw_text
        logger.info(f"Resume parsing completed successfully for {filename}")
        return structured
    except Exception as exc:
        logger.error(f"Resume structuring failed for {filename}: {exc}", exc_info=True)
        raise ResumeParsingError(f"Failed to structure resume content: {exc}") from exc

