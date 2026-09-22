import pytest

from app.services.question_generator.generator import generate_questions
from app.services.question_generator.schema import GeneratedQuestion
from app.services.resume_parser.schema import ParsedResume, ResumeProject


@pytest.fixture
def well_populated_resume() -> ParsedResume:
    """Fixture providing a well-populated ParsedResume instance."""
    return ParsedResume(
        skills=["Python", "FastAPI", "PostgreSQL", "Docker", "Kubernetes", "Redis", "AWS"],
        projects=[
            ResumeProject(
                title="MockWise",
                description="AI-powered mock interview preparation platform.",
            ),
            ResumeProject(
                title="TaskMaster",
                description="Distributed workflow orchestrator built with Celery and Redis.",
            ),
            ResumeProject(
                title="CloudMetrics",
                description="Real-time telemetry and metrics aggregator.",
            ),
        ],
        experience=[
            "Senior Software Engineer at Acme Corp (2022-2024)",
            "Software Developer at TechStart (2020-2022)",
            "Junior Backend Developer at InnovateLabs (2018-2020)",
        ],
        education=[
            "B.S. in Computer Science, State University, 2018",
        ],
    )


@pytest.fixture
def thin_resume() -> ParsedResume:
    """Fixture providing a resume with only one skill and no other items."""
    return ParsedResume(
        skills=["Python"],
        projects=[],
        experience=[],
        education=[],
    )


@pytest.mark.parametrize("target_count,expected_specific,expected_general", [
    (6, 4, 2),
    (7, 5, 2),
    (8, 6, 2),
])
def test_explicit_count_well_populated_resume(
    well_populated_resume,
    target_count,
    expected_specific,
    expected_general,
):
    """Verify explicit count produces exact question count with ~70/30 type split and unique texts."""
    questions = generate_questions(well_populated_resume, backend="mock", count=target_count)

    assert len(questions) == target_count

    specific_count = sum(1 for q in questions if q.type == "resume_specific")
    general_count = sum(1 for q in questions if q.type == "general")

    assert specific_count == expected_specific
    assert general_count == expected_general

    # Ensure no duplicate question_text values
    unique_texts = {q.question_text for q in questions}
    assert len(unique_texts) == target_count


def test_default_count_range_over_repeated_calls(well_populated_resume):
    """Verify calling with count=None over repeated calls always returns a total in [6, 8]."""
    for _ in range(50):
        questions = generate_questions(well_populated_resume, backend="mock", count=None)
        assert 6 <= len(questions) <= 8
        for q in questions:
            assert isinstance(q, GeneratedQuestion)
            assert q.type in ("resume_specific", "general")
            assert len(q.question_text.strip()) > 0

        # No duplicates in any single call
        assert len({q.question_text for q in questions}) == len(questions)


def test_thin_resume_fills_shortfall_with_general(thin_resume):
    """Verify a thin resume hits the requested count by filling the shortfall with general questions."""
    count = 7
    questions = generate_questions(thin_resume, backend="mock", count=count)

    assert len(questions) == count

    specific_questions = [q for q in questions if q.type == "resume_specific"]
    general_questions = [q for q in questions if q.type == "general"]

    # Only 1 skill available -> exactly 1 resume_specific question
    assert len(specific_questions) == 1
    assert "Python" in specific_questions[0].question_text
    # Remaining 6 slots filled with general questions
    assert len(general_questions) == 6

    # Verify all question texts are distinct
    assert len({q.question_text for q in questions}) == count


def test_no_duplicate_question_text_across_categories(well_populated_resume):
    """Verify no duplicate question texts are produced in a single call."""
    for count in [6, 7, 8, 10]:
        questions = generate_questions(well_populated_resume, backend="mock", count=count)
        texts = [q.question_text for q in questions]
        assert len(texts) == len(set(texts))


def test_mock_backend_default_parameter(well_populated_resume):
    """Verify default backend parameter is 'mock'."""
    questions = generate_questions(well_populated_resume)
    assert isinstance(questions, list)
    assert 6 <= len(questions) <= 8


@pytest.mark.parametrize("backend", ["ollama", "groq"])
def test_unimplemented_backends_raise_not_implemented(well_populated_resume, backend):
    """Verify calling with backend='ollama' or 'groq' raises NotImplementedError."""
    with pytest.raises(NotImplementedError):
        generate_questions(well_populated_resume, backend=backend)


def test_unknown_backend_raises_value_error(well_populated_resume):
    """Verify unknown backend raises ValueError."""
    with pytest.raises(ValueError):
        generate_questions(well_populated_resume, backend="invalid_backend")  # type: ignore[arg-type]


def test_mock_backend_handles_empty_resume():
    """Verify mock backend handles empty resume by filling entirely with general questions."""
    empty_resume = ParsedResume(
        skills=[],
        projects=[],
        experience=[],
        education=[],
    )

    questions = generate_questions(empty_resume, backend="mock", count=7)

    assert len(questions) == 7
    for q in questions:
        assert isinstance(q, GeneratedQuestion)
        assert q.type == "general"
        assert len(q.question_text.strip()) > 0

    assert len({q.question_text for q in questions}) == 7


def test_repeated_calls_produce_varying_question_sets(well_populated_resume):
    """Verify multiple calls for the same resume produce varying question sets/ordering."""
    runs = [
        [q.question_text for q in generate_questions(well_populated_resume, backend="mock")]
        for _ in range(10)
    ]
    # At least two distinct question sequences across 10 runs
    unique_runs = {tuple(run) for run in runs}
    assert len(unique_runs) > 1
