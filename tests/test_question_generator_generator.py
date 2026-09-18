import pytest

from app.services.question_generator.generator import generate_questions
from app.services.question_generator.schema import GeneratedQuestion
from app.services.resume_parser.schema import ParsedResume, ResumeProject


@pytest.fixture
def sample_parsed_resume() -> ParsedResume:
    """Fixture providing a populated ParsedResume instance."""
    return ParsedResume(
        skills=["Python", "FastAPI", "PostgreSQL", "Docker"],
        projects=[
            ResumeProject(
                title="MockWise",
                description="AI-powered mock interview preparation platform.",
            ),
            ResumeProject(
                title="TaskMaster",
                description="Distributed workflow orchestrator built with Celery and Redis.",
            ),
        ],
        experience=[
            "Senior Software Engineer at Acme Corp (2022-2024)",
            "Software Developer at TechStart (2020-2022)",
        ],
        education=[
            "B.S. in Computer Science, State University, 2020",
        ],
    )


def test_mock_backend_returns_valid_questions(sample_parsed_resume):
    """Verify mock backend returns a non-empty list of valid GeneratedQuestion objects."""
    questions = generate_questions(sample_parsed_resume, backend="mock")

    assert isinstance(questions, list)
    assert len(questions) > 0

    for q in questions:
        assert isinstance(q, GeneratedQuestion)
        assert isinstance(q.question_text, str)
        assert len(q.question_text.strip()) > 0
        assert q.type in ("resume_specific", "general")

    # Check that both resume_specific and general questions exist
    types = {q.type for q in questions}
    assert "resume_specific" in types
    assert "general" in types

    # Check grounding in resume data
    question_texts = " ".join(q.question_text for q in questions)
    assert sample_parsed_resume.skills[0] in question_texts
    assert sample_parsed_resume.projects[0].title in question_texts


def test_mock_backend_default_parameter(sample_parsed_resume):
    """Verify default backend parameter is 'mock'."""
    questions = generate_questions(sample_parsed_resume)
    assert isinstance(questions, list)
    assert len(questions) > 0


@pytest.mark.parametrize("backend", ["ollama", "groq"])
def test_unimplemented_backends_raise_not_implemented(sample_parsed_resume, backend):
    """Verify calling with backend='ollama' or 'groq' raises NotImplementedError."""
    with pytest.raises(NotImplementedError):
        generate_questions(sample_parsed_resume, backend=backend)


def test_unknown_backend_raises_value_error(sample_parsed_resume):
    """Verify unknown backend raises ValueError."""
    with pytest.raises(ValueError):
        generate_questions(sample_parsed_resume, backend="invalid_backend")  # type: ignore[arg-type]


def test_mock_backend_handles_empty_resume():
    """Verify mock backend doesn't crash when resume.skills and resume.projects are empty."""
    empty_resume = ParsedResume(
        skills=[],
        projects=[],
        experience=[],
        education=[],
    )

    questions = generate_questions(empty_resume, backend="mock")

    assert isinstance(questions, list)
    assert len(questions) > 0

    for q in questions:
        assert isinstance(q, GeneratedQuestion)
        assert isinstance(q.question_text, str)
        assert len(q.question_text.strip()) > 0
        assert q.type == "general"
