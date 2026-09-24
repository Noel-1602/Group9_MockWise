import os
import pytest

# Ensure all tests run against an isolated in-memory test database, not production/development mockwise.db
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["QUESTION_GENERATOR_BACKEND"] = "mock"
os.environ["STT_BACKEND"] = "mock"


