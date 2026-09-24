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


def test_ollama_backend_raises_not_implemented(well_populated_resume):
    """Verify calling with backend='ollama' raises NotImplementedError."""
    with pytest.raises(NotImplementedError):
        generate_questions(well_populated_resume, backend="ollama")


def test_groq_backend_missing_api_key_raises_environment_error(well_populated_resume, monkeypatch):
    """Verify groq backend raises EnvironmentError when GROQ_API_KEY is unset."""
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    with pytest.raises(EnvironmentError, match="GROQ_API_KEY"):
        generate_questions(well_populated_resume, backend="groq")


def test_groq_backend_successful_mocked_call(well_populated_resume, monkeypatch):
    """Verify groq backend correctly formats prompts, calls Groq client, and parses response."""
    monkeypatch.setenv("GROQ_API_KEY", "mock_key")

    mock_llm_json = """
    {
      "questions": [
        {"question_text": "How did you scale Celery and Redis in TaskMaster?", "type": "resume_specific"},
        {"question_text": "Can you discuss your experience using FastAPI and Python?", "type": "resume_specific"},
        {"question_text": "What challenges did you face building CloudMetrics?", "type": "resume_specific"},
        {"question_text": "Tell me about your time as Senior Software Engineer at Acme Corp.", "type": "resume_specific"},
        {"question_text": "How do you handle technical disagreements in a team?", "type": "general"},
        {"question_text": "What is your approach to system reliability and monitoring?", "type": "general"},
        {"question_text": "Describe a difficult debugging scenario you resolved.", "type": "general"}
      ]
    }
    """

    class MockChoice:
        message = type("Message", (), {"content": mock_llm_json})()

    class MockCompletion:
        choices = [MockChoice()]

    captured_call = {}

    class MockCompletionsResource:
        def create(self, **kwargs):
            captured_call.update(kwargs)
            return MockCompletion()

    class MockChatResource:
        completions = MockCompletionsResource()

    class MockGroqClient:
        def __init__(self, api_key=None):
            self.api_key = api_key
            self.chat = MockChatResource()

    monkeypatch.setattr("groq.Groq", MockGroqClient)

    questions = generate_questions(well_populated_resume, backend="groq", count=7)

    assert len(questions) == 7
    assert captured_call.get("model") == "openai/gpt-oss-120b"
    assert captured_call.get("temperature") == 0.7
    assert any("TaskMaster" in msg["content"] or "Python" in msg["content"] for msg in captured_call.get("messages", []))

    specific_count = sum(1 for q in questions if q.type == "resume_specific")
    general_count = sum(1 for q in questions if q.type == "general")
    assert specific_count == 4
    assert general_count == 3
    assert all(isinstance(q, GeneratedQuestion) for q in questions)


def test_groq_backend_handles_markdown_code_fences(well_populated_resume, monkeypatch):
    """Verify groq backend strips markdown code fences before parsing JSON."""
    monkeypatch.setenv("GROQ_API_KEY", "mock_key")

    mock_llm_fenced_json = """```json
    {
      "questions": [
        {"question_text": "Can you explain your work with Docker and Kubernetes?", "type": "resume_specific"},
        {"question_text": "How do you design REST APIs in FastAPI?", "type": "resume_specific"},
        {"question_text": "Describe your background at Acme Corp.", "type": "resume_specific"},
        {"question_text": "What is your philosophy on writing automated tests?", "type": "general"},
        {"question_text": "Tell me about a time you led an incident response.", "type": "general"},
        {"question_text": "How do you stay up-to-date with emerging tech?", "type": "general"}
      ]
    }
    ```"""

    class MockChoice:
        message = type("Message", (), {"content": mock_llm_fenced_json})()

    class MockCompletion:
        choices = [MockChoice()]

    class MockCompletionsResource:
        def create(self, **kwargs):
            return MockCompletion()

    class MockChatResource:
        completions = MockCompletionsResource()

    class MockGroqClient:
        def __init__(self, api_key=None):
            self.chat = MockChatResource()

    monkeypatch.setattr("groq.Groq", MockGroqClient)

    questions = generate_questions(well_populated_resume, backend="groq", count=6)
    assert len(questions) == 6
    assert questions[0].question_text == "Can you explain your work with Docker and Kubernetes?"
    assert questions[0].type == "resume_specific"


def test_groq_backend_invalid_json_raises_value_error(well_populated_resume, monkeypatch):
    """Verify invalid JSON from Groq raises a descriptive ValueError."""
    monkeypatch.setenv("GROQ_API_KEY", "mock_key")

    class MockChoice:
        message = type("Message", (), {"content": "This is not valid JSON content."})()

    class MockCompletion:
        choices = [MockChoice()]

    class MockCompletionsResource:
        def create(self, **kwargs):
            return MockCompletion()

    class MockChatResource:
        completions = MockCompletionsResource()

    class MockGroqClient:
        def __init__(self, api_key=None):
            self.chat = MockChatResource()

    monkeypatch.setattr("groq.Groq", MockGroqClient)

    with pytest.raises(ValueError, match="Failed to parse JSON"):
        generate_questions(well_populated_resume, backend="groq")


def test_groq_backend_thin_resume_handles_generation(thin_resume, monkeypatch):
    """Verify groq backend with thin resume generates questions without error."""
    monkeypatch.setenv("GROQ_API_KEY", "mock_key")

    mock_llm_json = """
    {
      "questions": [
        {"question_text": "What experience do you have with Python programming?", "type": "resume_specific"},
        {"question_text": "How do you approach debugging difficult software issues?", "type": "general"},
        {"question_text": "Can you describe a time when you had to learn something quickly?", "type": "general"},
        {"question_text": "What strategies do you use for clean code architecture?", "type": "general"},
        {"question_text": "How do you handle deadlines and project prioritization?", "type": "general"},
        {"question_text": "Tell me about a challenging project you contributed to.", "type": "general"}
      ]
    }
    """

    class MockChoice:
        message = type("Message", (), {"content": mock_llm_json})()

    class MockCompletion:
        choices = [MockChoice()]

    captured_call = {}

    class MockCompletionsResource:
        def create(self, **kwargs):
            captured_call.update(kwargs)
            return MockCompletion()

    class MockChatResource:
        completions = MockCompletionsResource()

    class MockGroqClient:
        def __init__(self, api_key=None):
            self.chat = MockChatResource()

    monkeypatch.setattr("groq.Groq", MockGroqClient)

    questions = generate_questions(thin_resume, backend="groq")
    assert len(questions) == 6
    assert questions[0].type == "resume_specific"
    assert sum(1 for q in questions if q.type == "general") == 5


def test_groq_backend_empty_questions_raises_value_error(well_populated_resume, monkeypatch):
    """Verify empty questions list from Groq raises ValueError."""
    monkeypatch.setenv("GROQ_API_KEY", "mock_key")

    mock_llm_json = '{"questions": []}'

    class MockChoice:
        message = type("Message", (), {"content": mock_llm_json})()

    class MockCompletion:
        choices = [MockChoice()]

    class MockCompletionsResource:
        def create(self, **kwargs):
            return MockCompletion()

    class MockChatResource:
        completions = MockCompletionsResource()

    class MockGroqClient:
        def __init__(self, api_key=None):
            self.chat = MockChatResource()

    monkeypatch.setattr("groq.Groq", MockGroqClient)

    with pytest.raises(ValueError, match="no valid questions"):
        generate_questions(well_populated_resume, backend="groq")


def test_groq_backend_missing_package_raises_import_error(well_populated_resume, monkeypatch):
    """Verify missing groq module raises ImportError."""
    monkeypatch.setenv("GROQ_API_KEY", "mock_key")
    import builtins
    real_import = builtins.__import__

    def mock_import(name, *args, **kwargs):
        if name == "groq":
            raise ImportError("No module named 'groq'")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", mock_import)

    with pytest.raises(ImportError, match="The 'groq' package is required"):
        generate_questions(well_populated_resume, backend="groq")


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
