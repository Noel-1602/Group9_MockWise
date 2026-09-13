"""Tests for extract_text_from_pdf and extract_text_from_docx.

Sample files are generated programmatically so the test suite is fully
self-contained — no fixture files are committed to the repository.

Dependencies (must be installed in the active venv):
    pip install reportlab python-docx pymupdf
"""
import pathlib

import pytest


# ---------------------------------------------------------------------------
# Helpers – build sample files with realistic resume-like content
# ---------------------------------------------------------------------------

SAMPLE_NAME = "Jane Doe"
SAMPLE_EMAIL = "jane.doe@example.com"
SAMPLE_SKILLS = "Python, FastAPI, PostgreSQL, Docker"
SAMPLE_PROJECT = "MockWise: an AI-powered mock interview platform built with FastAPI"
SAMPLE_EDUCATION = "B.Sc. Computer Science, University of Technology, 2022"


def _build_sample_pdf(dest: pathlib.Path) -> None:
    """Write a minimal, text-searchable PDF using reportlab."""
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas

    c = canvas.Canvas(str(dest), pagesize=A4)
    _, height = A4

    lines = [
        SAMPLE_NAME,
        SAMPLE_EMAIL,
        "",
        "Skills",
        SAMPLE_SKILLS,
        "",
        "Projects",
        SAMPLE_PROJECT,
        "",
        "Education",
        SAMPLE_EDUCATION,
    ]

    y = height - 72  # start 1 inch from the top
    for line in lines:
        c.drawString(72, y, line)
        y -= 18  # 18-point line spacing

    c.save()


def _build_sample_docx(dest: pathlib.Path) -> None:
    """Write a minimal DOCX with paragraphs using python-docx."""
    import docx

    doc = docx.Document()
    doc.add_heading(SAMPLE_NAME, level=1)
    doc.add_paragraph(SAMPLE_EMAIL)
    doc.add_heading("Skills", level=2)
    doc.add_paragraph(SAMPLE_SKILLS)
    doc.add_heading("Projects", level=2)
    doc.add_paragraph(SAMPLE_PROJECT)
    doc.add_heading("Education", level=2)
    doc.add_paragraph(SAMPLE_EDUCATION)
    doc.save(str(dest))


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def sample_pdf(tmp_path: pathlib.Path) -> pathlib.Path:
    """Return the path to a temporary sample PDF."""
    pdf_path = tmp_path / "sample_resume.pdf"
    _build_sample_pdf(pdf_path)
    return pdf_path


@pytest.fixture()
def sample_docx(tmp_path: pathlib.Path) -> pathlib.Path:
    """Return the path to a temporary sample DOCX."""
    docx_path = tmp_path / "sample_resume.docx"
    _build_sample_docx(docx_path)
    return docx_path


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestExtractTextFromPdf:
    """Tests for extract_text_from_pdf (PyMuPDF backend)."""

    def test_returns_string(self, sample_pdf: pathlib.Path) -> None:
        from app.services.resume_parser.extract import extract_text_from_pdf

        result = extract_text_from_pdf(str(sample_pdf))
        assert isinstance(result, str)

    def test_contains_name(self, sample_pdf: pathlib.Path) -> None:
        from app.services.resume_parser.extract import extract_text_from_pdf

        result = extract_text_from_pdf(str(sample_pdf))
        assert SAMPLE_NAME in result, f"Expected '{SAMPLE_NAME}' in extracted text"

    def test_contains_skills(self, sample_pdf: pathlib.Path) -> None:
        from app.services.resume_parser.extract import extract_text_from_pdf

        result = extract_text_from_pdf(str(sample_pdf))
        # Check at least one technology from the skills line
        assert "FastAPI" in result or "Python" in result, (
            f"Expected skill keywords in extracted text; got: {result[:300]}"
        )

    def test_contains_project_description(self, sample_pdf: pathlib.Path) -> None:
        from app.services.resume_parser.extract import extract_text_from_pdf

        result = extract_text_from_pdf(str(sample_pdf))
        assert "MockWise" in result, f"Expected 'MockWise' in extracted text"

    def test_no_cleaning_applied(self, sample_pdf: pathlib.Path) -> None:
        """The function must return raw text; no stripping of whitespace etc."""
        from app.services.resume_parser.extract import extract_text_from_pdf

        result = extract_text_from_pdf(str(sample_pdf))
        # Raw PyMuPDF output preserves newline characters
        assert "\n" in result, "Expected raw text with newline characters preserved"


class TestExtractTextFromDocx:
    """Tests for extract_text_from_docx (python-docx backend)."""

    def test_returns_string(self, sample_docx: pathlib.Path) -> None:
        from app.services.resume_parser.extract import extract_text_from_docx

        result = extract_text_from_docx(str(sample_docx))
        assert isinstance(result, str)

    def test_contains_name(self, sample_docx: pathlib.Path) -> None:
        from app.services.resume_parser.extract import extract_text_from_docx

        result = extract_text_from_docx(str(sample_docx))
        assert SAMPLE_NAME in result, f"Expected '{SAMPLE_NAME}' in extracted text"

    def test_contains_skills(self, sample_docx: pathlib.Path) -> None:
        from app.services.resume_parser.extract import extract_text_from_docx

        result = extract_text_from_docx(str(sample_docx))
        assert "PostgreSQL" in result or "Python" in result, (
            f"Expected skill keywords in extracted text; got: {result[:300]}"
        )

    def test_contains_project_description(self, sample_docx: pathlib.Path) -> None:
        from app.services.resume_parser.extract import extract_text_from_docx

        result = extract_text_from_docx(str(sample_docx))
        assert "MockWise" in result, f"Expected 'MockWise' in extracted text"

    def test_contains_education(self, sample_docx: pathlib.Path) -> None:
        from app.services.resume_parser.extract import extract_text_from_docx

        result = extract_text_from_docx(str(sample_docx))
        assert "Computer Science" in result, (
            f"Expected 'Computer Science' in extracted text"
        )

    def test_no_cleaning_applied(self, sample_docx: pathlib.Path) -> None:
        """The function must return raw text; empty paragraphs kept as blank lines."""
        from app.services.resume_parser.extract import extract_text_from_docx

        result = extract_text_from_docx(str(sample_docx))
        # python-docx inserts a blank paragraph at document start; raw output
        # will therefore contain at least one newline.
        assert "\n" in result, "Expected raw text with newline characters preserved"
