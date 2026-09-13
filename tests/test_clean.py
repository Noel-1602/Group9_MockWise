"""Tests for clean_resume_text in app/services/resume_parser/clean.py."""

import pytest

from app.services.resume_parser.clean import clean_resume_text


class TestCleanResumeText:
    """Unit tests for the clean_resume_text function."""

    # ------------------------------------------------------------------
    # Happy-path: normal text should come back unchanged (modulo strip)
    # ------------------------------------------------------------------

    def test_normal_text_unchanged(self) -> None:
        """Single blank lines and single spaces are left intact."""
        text = "Jane Doe\n\nSkills\nPython, FastAPI\n\nProjects\nMockWise"
        assert clean_resume_text(text) == text

    def test_single_spaces_unchanged(self) -> None:
        """A single space between words is not collapsed."""
        text = "Software Engineer at Acme Corp"
        assert clean_resume_text(text) == text

    def test_single_newline_unchanged(self) -> None:
        """A lone newline between lines is preserved."""
        text = "Line one\nLine two\nLine three"
        assert clean_resume_text(text) == text

    # ------------------------------------------------------------------
    # Excessive blank lines (3+ newlines → 2)
    # ------------------------------------------------------------------

    def test_triple_newlines_collapsed(self) -> None:
        """Three consecutive newlines are reduced to two."""
        raw = "Section A\n\n\nSection B"
        assert clean_resume_text(raw) == "Section A\n\nSection B"

    def test_many_newlines_collapsed(self) -> None:
        """Five consecutive newlines are also reduced to two."""
        raw = "Header\n\n\n\n\nBody"
        assert clean_resume_text(raw) == "Header\n\nBody"

    def test_multiple_gaps_all_collapsed(self) -> None:
        """Every run of 3+ newlines in the text is collapsed."""
        raw = "A\n\n\nB\n\n\n\nC\n\nD"
        assert clean_resume_text(raw) == "A\n\nB\n\nC\n\nD"

    def test_exactly_two_newlines_preserved(self) -> None:
        """Exactly two newlines (one blank line) are not touched."""
        raw = "Skills\n\nPython, FastAPI"
        assert clean_resume_text(raw) == raw

    # ------------------------------------------------------------------
    # Excessive spaces / tabs (2+ → 1 space)
    # ------------------------------------------------------------------

    def test_double_space_collapsed(self) -> None:
        """Two consecutive spaces become one."""
        raw = "Python,  FastAPI"
        assert clean_resume_text(raw) == "Python, FastAPI"

    def test_many_spaces_collapsed(self) -> None:
        """Many consecutive spaces become one."""
        raw = "Name:     Jane     Doe"
        assert clean_resume_text(raw) == "Name: Jane Doe"

    def test_tabs_collapsed(self) -> None:
        """Two or more tabs become a single space."""
        raw = "Skill\t\tLevel"
        assert clean_resume_text(raw) == "Skill Level"

    def test_mixed_spaces_and_tabs_collapsed(self) -> None:
        """A mix of spaces and tabs on one line is collapsed to one space."""
        raw = "Python\t  FastAPI"
        assert clean_resume_text(raw) == "Python FastAPI"

    def test_spaces_do_not_cross_newlines(self) -> None:
        """Space-collapsing must not merge content across line boundaries."""
        raw = "Line one\n  indented line"
        result = clean_resume_text(raw)
        assert "\n" in result
        assert "Line one" in result
        assert "indented line" in result

    # ------------------------------------------------------------------
    # Leading / trailing whitespace is stripped
    # ------------------------------------------------------------------

    def test_leading_whitespace_stripped(self) -> None:
        raw = "\n\n  Jane Doe"
        assert clean_resume_text(raw) == "Jane Doe"

    def test_trailing_whitespace_stripped(self) -> None:
        raw = "Jane Doe  \n\n"
        assert clean_resume_text(raw) == "Jane Doe"

    def test_both_ends_stripped(self) -> None:
        raw = "\n\n  Jane Doe\n\n  "
        assert clean_resume_text(raw) == "Jane Doe"

    # ------------------------------------------------------------------
    # Edge cases
    # ------------------------------------------------------------------

    def test_empty_string_returns_empty(self) -> None:
        """An empty string must return an empty string without raising."""
        assert clean_resume_text("") == ""

    def test_whitespace_only_string_returns_empty(self) -> None:
        """A string with only whitespace returns an empty string."""
        assert clean_resume_text("   \n\n\t  ") == ""

    def test_realistic_resume_block(self) -> None:
        """A realistic chunk with multiple issues is cleaned correctly."""
        raw = (
            "\n\n\n"
            "Jane Doe\n"
            "jane.doe@example.com\n"
            "\n\n\n"
            "Skills\n"
            "Python,  FastAPI,   PostgreSQL\n"
            "\n\n\n\n"
            "Projects\n"
            "MockWise:  AI-powered  mock interview  platform\n"
            "\n\n"
        )
        result = clean_resume_text(raw)

        # Leading/trailing stripped
        assert not result.startswith("\n")
        assert not result.endswith("\n")

        # No run of 3+ newlines remains
        assert "\n\n\n" not in result

        # No run of 2+ spaces/tabs remains
        import re
        assert not re.search(r"[ \t]{2,}", result)

        # Content preserved
        assert "Jane Doe" in result
        assert "Python, FastAPI, PostgreSQL" in result
        assert "MockWise: AI-powered mock interview platform" in result
