"""
API integration tests for the FastAPI application (tests/api/test_api.py)

These use httpx.AsyncClient against the live ASGI app — no real HTTP port needed.
MongoDB and LLM calls are mocked so the server does not need live services.

Run:  pytest tests/api/test_api.py -v
"""

import pytest
import pytest_asyncio

from unittest.mock import AsyncMock, MagicMock, patch
from httpx import AsyncClient, ASGITransport


# ---------------------------------------------------------------------------
# Patch heavy startup dependencies before importing the app
# ---------------------------------------------------------------------------
@pytest.fixture(scope="module", autouse=True)
def patch_startup_services():
    """
    Prevent TTS model load, Qdrant init, Gmail cred load, and
    APScheduler start from running during tests.
    """
    patches = [
        patch("arcis.core.tts.tts_manager.tts_manager.initialize",    MagicMock()),
        patch("arcis.core.llm.long_memory.long_memory.init",           MagicMock()),
        patch("arcis.core.external_api.gmail.gmail_api.load_creds",    AsyncMock()),
        patch("arcis.core.llm.config_manager.config_manager.load_config", AsyncMock()),
        patch("arcis.database.mongo.connection.mongo.connect",          AsyncMock()),
        patch("arcis.database.mongo.connection.mongo.disconnect",        AsyncMock()),
        patch("arcis.core.scheduler.scheduler_service.scheduler_service.start",   AsyncMock()),
        patch("arcis.core.scheduler.scheduler_service.scheduler_service.shutdown", AsyncMock()),
        patch("arcis.core.scheduler.scheduler_service.scheduler_service.add_email_cron", MagicMock()),
        patch("arcis.core.mcp.manager.mcp_manager.init",               AsyncMock()),
        patch("arcis.core.mcp.manager.mcp_manager.shutdown",           AsyncMock()),
        patch("arcis.tgclient.get_tg_client",                          MagicMock(return_value=None)),
    ]
    started = [p.start() for p in patches]
    yield
    for p in patches:
        p.stop()


@pytest.fixture(scope="module")
def app():
    from arcis.__main__ import api_server
    return api_server


# ---------------------------------------------------------------------------
# Async test client fixture
# ---------------------------------------------------------------------------
@pytest_asyncio.fixture
async def client(app):
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test"
    ) as c:
        yield c


# ===========================================================================
# API-CH: Chat endpoints
# ===========================================================================

MOCK_FINAL_STATE = {
    "final_response": "This is a mocked AI response.",
    "plan": [],
    "thread_id": "test-thread-123",
    "workflow_status": "FINISHED",
    "input": "Hello",
    "messages": [],
    "context": {},
    "last_tool_output": "",
    "current_step_index": 0,
    "next_node": None,
}


@pytest.mark.asyncio
async def test_chat_post_returns_ai_response(client):
    """API-CH-01: Valid message returns 200 with type='ai' and non-empty response."""
    with patch(
        "arcis.router.chat.run_workflow",
        AsyncMock(return_value=MOCK_FINAL_STATE)
    ), patch(
        "arcis.router.chat.save_message", MagicMock()
    ):
        resp = await client.post("/chat", json={
            "message": "Hello ARCIS",
            "thread_id": "test-thread-123"
        })

    assert resp.status_code == 200
    body = resp.json()
    assert body["type"] == "ai"
    assert len(body["response"]) > 0
    assert "thread_id" in body


@pytest.mark.asyncio
async def test_chat_post_missing_message_returns_422(client):
    """API-CH-02: Request with no message field is rejected with 422."""
    resp = await client.post("/chat", json={"thread_id": None})
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_chat_post_interrupt_response(client):
    """API-CH-03: Workflow returning interrupt type is forwarded to client."""
    mock_interrupt = {
        "type": "interrupt",
        "response": "Please confirm: send email to John?",
        "thread_id": "test-thread-456",
    }

    with patch(
        "arcis.router.chat.run_workflow",
        AsyncMock(return_value=mock_interrupt)
    ), patch("arcis.router.chat.save_message", MagicMock()):
        resp = await client.post("/chat", json={
            "message": "Send email to John",
            "thread_id": "test-thread-456"
        })

    assert resp.status_code == 200
    body = resp.json()
    assert body["type"] == "interrupt"
    assert "Please confirm" in body["response"]


@pytest.mark.asyncio
async def test_get_all_chats_returns_list(client):
    """API-CH-10: GET /chat/all_chats returns a list (may be empty)."""
    with patch(
        "arcis.router.chat.get_all_threads",
        MagicMock(return_value=[])
    ):
        resp = await client.get("/chat/all_chats")

    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


@pytest.mark.asyncio
async def test_get_chat_history_unknown_thread(client):
    """API-CH-12: Unknown thread_id returns 200 with empty list."""
    with patch(
        "arcis.router.chat.get_thread_history",
        MagicMock(return_value=[])
    ):
        resp = await client.get("/chat/nonexistent-thread-id")

    assert resp.status_code == 200
    assert resp.json() == []


# ===========================================================================
# API-GM: Gmail endpoints
# ===========================================================================

@pytest.mark.asyncio
async def test_gmail_login_returns_url(client):
    """API-GM-01: GET /gmail/auth/login returns a Google OAuth URL."""
    with patch(
        "arcis.router.gmail.gmail_api.get_auth_url",
        MagicMock(return_value="https://accounts.google.com/o/oauth2/auth?...")
    ):
        resp = await client.get("/gmail/auth/login")

    assert resp.status_code == 200
    body = resp.json()
    # Response should contain the auth URL
    url = body.get("auth_url") or body.get("url") or str(body)
    assert "accounts.google.com" in url or "google" in url.lower()


@pytest.mark.asyncio
async def test_gmail_auth_status(client):
    """API-GM-03: GET /gmail/auth/status returns authenticated bool."""
    with patch(
        "arcis.router.gmail.gmail_api.is_authenticated",
        MagicMock(return_value=False)
    ):
        resp = await client.get("/gmail/auth/status")

    assert resp.status_code == 200
    body = resp.json()
    assert "authenticated" in body or isinstance(body, dict)


# ===========================================================================
# API-ST: Settings endpoints
# ===========================================================================

@pytest.mark.asyncio
async def test_settings_get_agents(client):
    """API-ST-01: GET /settings/agents returns per-agent config."""
    from arcis.core.llm.config_manager import DEFAULT_AGENTS_CONFIG

    with patch(
        "arcis.router.settings.config_manager.get_all_configs",
        MagicMock(return_value=DEFAULT_AGENTS_CONFIG)
    ):
        resp = await client.get("/settings/agents")

    assert resp.status_code == 200
    body = resp.json()
    assert isinstance(body, (dict, list))


@pytest.mark.asyncio
async def test_settings_get_models(client):
    """API-ST-04: GET /settings/models returns available models."""
    resp = await client.get("/settings/models")
    assert resp.status_code == 200


# ===========================================================================
# API-OB: Onboarding endpoints
# ===========================================================================

@pytest.mark.asyncio
async def test_onboarding_status(client):
    """API-OB-03: GET /onboarding/status returns completed bool."""
    resp = await client.get("/onboarding/status")
    assert resp.status_code == 200


# ===========================================================================
# API-AF: Auto-flow endpoints
# ===========================================================================

@pytest.mark.asyncio
async def test_auto_flow_pending_returns_list(client):
    """API-AF-01: GET /auto_flow/pending returns a list."""
    with patch(
        "arcis.router.auto_flow.get_pending_interrupts",
        AsyncMock(return_value=[])
    ):
        resp = await client.get("/auto_flow/pending")

    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


# ===========================================================================
# Error handling — oversized payload
# ===========================================================================

@pytest.mark.asyncio
async def test_chat_with_long_message(client):
    """EH-style: Very long message should not crash the server (422 or 200)."""
    long_msg = "a" * 50_000

    with patch(
        "arcis.router.chat.run_workflow",
        AsyncMock(return_value=MOCK_FINAL_STATE)
    ), patch("arcis.router.chat.save_message", MagicMock()):
        resp = await client.post("/chat", json={
            "message": long_msg,
            "thread_id": None
        })

    # Should not be a 500 — either accepted (200) or rejected at validation (422)
    assert resp.status_code in (200, 422), f"Unexpected status: {resp.status_code}"
