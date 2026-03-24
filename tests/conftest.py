"""
conftest.py — Shared pytest fixtures for the ARCIS test suite.

Sets DATABASE_URL before any arcis module is imported, so Config does not exit(1).
All external services (MongoDB, Qdrant, LLMs) are mocked by default.
"""

import os
import pytest
import pytest_asyncio

# ── Must be set BEFORE arcis.config is imported ──────────────────────────────
os.environ.setdefault("DATABASE_URL", "mongodb://localhost:27017/")
os.environ.setdefault("DATABASE_NAME", "arcis_test_db")
os.environ.setdefault("GEMINI_API",    "test-gemini-key")
os.environ.setdefault("GROQ_API_KEY",  "test-groq-key")
os.environ.setdefault("EMBEDDING_MODE", "offline")
os.environ.setdefault("QDRANT_URL",    "http://localhost:6333")
# ─────────────────────────────────────────────────────────────────────────────

from unittest.mock import AsyncMock, MagicMock, patch
from arcis.models.llm import LLMProvider


# ---------------------------------------------------------------------------
# Async event-loop policy (required for pytest-asyncio)
# ---------------------------------------------------------------------------
@pytest.fixture(scope="session")
def event_loop_policy():
    import asyncio
    return asyncio.DefaultEventLoopPolicy()


# ---------------------------------------------------------------------------
# Fake MongoDB client / db fixture
# ---------------------------------------------------------------------------
class FakeCollection:
    """In-memory collection that satisfies Motor's async interface."""

    def __init__(self):
        self._data = []

    async def find_one(self, query=None):
        return None  # no records by default

    async def update_one(self, query, update, upsert=False):
        return MagicMock(matched_count=1, modified_count=1)

    async def insert_one(self, doc):
        self._data.append(doc)
        return MagicMock(inserted_id="fake-id")

    def find(self, query=None):
        async def _iter():
            for doc in self._data:
                yield doc
        return _iter()


class FakeDB:
    def __getitem__(self, name):
        return FakeCollection()

    def __getattr__(self, name):
        return FakeCollection()


class FakeMongo:
    client = MagicMock()
    db = FakeDB()

    async def connect(self):
        pass

    async def disconnect(self):
        pass


@pytest.fixture
def fake_mongo():
    return FakeMongo()


# ---------------------------------------------------------------------------
# Mock LLM client
# ---------------------------------------------------------------------------
@pytest.fixture
def mock_llm():
    llm = MagicMock()
    llm.invoke = MagicMock(return_value=MagicMock(content="Mocked LLM response"))
    llm.ainvoke = AsyncMock(return_value=MagicMock(content="Mocked LLM response"))
    return llm
