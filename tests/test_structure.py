"""Tests for structure_resume() -- mock backend only.

The ollama and groq backends require external services and are not tested here.
"""

import pytest

from app.services.resume_parser.structure import structure_resume


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _assert_parsed_resume_shape(result: dict) -> None:
    """Assert *result* has all four ParsedResume keys with list values."""
    assert isinstance(result, dict), "structure_resume must return a dict"
    for key in ("skills", "projects", "experience", "education"):
        assert key in result, f"Missing key: {key!r}"
        assert isinstance(result[key], list), f"{key!r} must be a list, got {type(result[key])}"


# ---------------------------------------------------------------------------
# Sample resume texts
# ---------------------------------------------------------------------------

RESUME_FULL = (
    "Jane Doe\n"
    "jane@example.com | (555) 123-4567\n"
    "\n"
    "Skills\n"
    "Python, FastAPI, PostgreSQL, Docker, Kubernetes\n"
    "React, TypeScript\n"
    "\n"
    "Experience\n"
    "Senior Software Engineer at Acme Corp\n"
    "- Led migration of monolith to microservices\n"
    "- Reduced p99 latency by 40%\n"
    "Junior Developer at StartupXYZ\n"
    "- Built REST APIs in Django\n"
    "\n"
    "Education\n"
    "B.Sc. Computer Science - State University, 2019\n"
    "\n"
    "Projects\n"
    "ResumeParser\n"
    "- Open-source NLP pipeline for resume extraction\n"
    "- Used Python, spaCy, and FastAPI\n"
    "PersonalSite\n"
    "- Portfolio website with Next.js and Vercel\n"
)

RESUME_SKILLS_ONLY = (
    "Technical Skills\n"
    "JavaScript \u2022 TypeScript \u2022 Node.js \u2022 React \u2022 Vue\n"
    "AWS; GCP; Azure\n"
    "SQL | NoSQL | Redis\n"
)

RESUME_NO_SECTIONS = (
    "John Smith\n"
    "Experienced software developer with 10 years of industry experience.\n"
    "Worked on various enterprise projects involving Java and Spring Boot.\n"
    "Graduated from the University of Technology in 2012.\n"
)


# ---------------------------------------------------------------------------
# Tests -- full resume
# ---------------------------------------------------------------------------

class TestMockBackendFullResume:
    """structure_resume("mock") on a resume with all four sections present."""

    def setup_method(self):
        self.result = structure_resume(RESUME_FULL, backend="mock")

    def test_returns_dict_with_correct_keys(self):
        _assert_parsed_resume_shape(self.result)

    def test_skills_extracted(self):
        skills = self.result["skills"]
        assert len(skills) > 0, "Expected at least one skill"
        skill_lower = [s.lower() for s in skills]
        assert "python" in skill_lower
        assert "fastapi" in skill_lower
        assert "docker" in skill_lower

    def test_experience_extracted(self):
        experience = self.result["experience"]
        assert len(experience) >= 2, "Expected at least 2 experience entries"
        combined = " ".join(experience).lower()
        assert "acme" in combined
        assert "startupxyz" in combined

    def test_education_extracted(self):
        education = self.result["education"]
        assert len(education) >= 1, "Expected at least 1 education entry"
        combined = " ".join(education).lower()
        assert "university" in combined or "b.sc" in combined

    def test_projects_extracted(self):
        projects = self.result["projects"]
        assert len(projects) >= 2, "Expected at least 2 project entries"
        titles = [p["title"] for p in projects]
        assert any("resumeparser" in t.lower() for t in titles)

    def test_project_items_have_title_and_description(self):
        for project in self.result["projects"]:
            assert "title" in project
            assert "description" in project
            assert isinstance(project["title"], str)
            assert isinstance(project["description"], str)

    def test_experience_bullets_appended(self):
        """Bullet points under an experience entry should be merged."""
        experience = self.result["experience"]
        first = experience[0] if experience else ""
        assert ("latency" in first.lower()
                or "migration" in first.lower()
                or "\u2014" in first)


# ---------------------------------------------------------------------------
# Tests -- skills-only resume
# ---------------------------------------------------------------------------

class TestMockBackendSkillsOnly:
    """structure_resume("mock") on a resume with only a Technical Skills section."""

    def setup_method(self):
        self.result = structure_resume(RESUME_SKILLS_ONLY, backend="mock")

    def test_returns_dict_with_correct_keys(self):
        _assert_parsed_resume_shape(self.result)

    def test_skills_split_on_bullets_and_semicolons(self):
        skills = self.result["skills"]
        assert len(skills) >= 5, f"Expected >=5 skills, got {skills}"
        lower = [s.lower() for s in skills]
        assert "javascript" in lower
        assert "typescript" in lower
        assert "aws" in lower
        assert "gcp" in lower

    def test_skills_split_on_pipe(self):
        lower = [s.lower() for s in self.result["skills"]]
        assert "sql" in lower or "nosql" in lower or "redis" in lower

    def test_other_sections_empty(self):
        assert self.result["experience"] == []
        assert self.result["education"] == []
        assert self.result["projects"] == []


# ---------------------------------------------------------------------------
# Tests -- unstructured text (no recognised section headers)
# ---------------------------------------------------------------------------

class TestMockBackendNoSections:
    """structure_resume("mock") on plain prose with no section headers."""

    def setup_method(self):
        self.result = structure_resume(RESUME_NO_SECTIONS, backend="mock")

    def test_returns_dict_with_correct_keys(self):
        _assert_parsed_resume_shape(self.result)

    def test_all_sections_empty_lists(self):
        """When there are no recognised headers all lists should be empty."""
        assert self.result["skills"] == []
        assert self.result["experience"] == []
        assert self.result["education"] == []
        assert self.result["projects"] == []


# ---------------------------------------------------------------------------
# Edge-case tests
# ---------------------------------------------------------------------------

class TestMockBackendEdgeCases:
    def test_empty_string_returns_valid_shape(self):
        result = structure_resume("", backend="mock")
        _assert_parsed_resume_shape(result)
        assert all(result[k] == [] for k in ("skills", "projects", "experience", "education"))

    def test_whitespace_only_returns_valid_shape(self):
        result = structure_resume("   \n\n\t  ", backend="mock")
        _assert_parsed_resume_shape(result)

    def test_default_backend_is_mock(self):
        """Calling without backend= should behave identically to backend="mock"."""
        result_default = structure_resume(RESUME_SKILLS_ONLY)
        result_mock = structure_resume(RESUME_SKILLS_ONLY, backend="mock")
        assert result_default == result_mock

    def test_unknown_backend_raises_value_error(self):
        with pytest.raises(ValueError, match="Unknown backend"):
            structure_resume("some text", backend="nonexistent")

    def test_section_header_case_insensitive(self):
        """Headers should be matched case-insensitively."""
        text = "SKILLS\nRust, Go, C++"
        result = structure_resume(text, backend="mock")
        lower = [s.lower() for s in result["skills"]]
        assert "rust" in lower
        assert "go" in lower

    def test_section_header_with_trailing_colon(self):
        """Headers ending in : should still be recognised."""
        text = "Skills:\nElixir, Erlang"
        result = structure_resume(text, backend="mock")
        lower = [s.lower() for s in result["skills"]]
        assert "elixir" in lower
        assert "erlang" in lower
