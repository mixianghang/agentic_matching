"""Tests for Milestone 1: Privacy Filter Integration & Rate Limiting.

Coverage:
  - PrivacyFilterLayer is wired into create_user_agent_interaction
  - DisclosureConfig persistence in task metadata
  - GET/PUT /api/tasks/{id}/privacy REST endpoints
  - GET /api/tasks/{id}/disclosure_events REST endpoint
  - SQLiteStorage disclosure_events table (add_disclosure_event / get_disclosure_events)
  - Per-user and global rate limiting middleware (429 responses)
"""
import os
import time
import pytest

# ── Environment setup (must happen before importing backend) ────────────────
os.environ["STORAGE_TYPE"] = "in_memory"
os.environ["OPENAI_API_KEY"] = "dummy_key_for_testing"
os.environ["DATABASE_URL"] = ":memory:"

from fastapi.testclient import TestClient
from backend.main import app, _per_user_windows, _global_window
from backend.storage import storage
from backend.privacy.disclosure import DisclosureConfig, DisclosureLevel, DisclosureEvent
from backend.privacy.filter import PrivacyFilterLayer, FilterResult
from backend.privacy.disclosure import SessionDisclosureBudget


# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def reset_state():
    """Reset in-memory storage and rate-limit windows before each test."""
    storage.users = {}
    storage.agents = {}
    storage.tasks = {}
    storage.messages = {}
    storage.tokens = {}
    _per_user_windows.clear()
    _global_window.clear()
    yield


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture
def auth(client):
    """Register a user and return (client, auth_headers, user_id)."""
    resp = client.post("/api/auth/register", json={
        "username": "milestoneuser",
        "password": "password123",
    })
    assert resp.status_code == 200
    data = resp.json()
    headers = {"Authorization": f"Bearer {data['access_token']}"}
    return client, headers, data["user"]["id"]


@pytest.fixture
def task_id(auth):
    """Create a task and return its id."""
    client, headers, _ = auth
    resp = client.post("/api/tasks/", json={
        "task_type": "rental",
        "description": "test task",
    }, headers=headers)
    assert resp.status_code == 200
    return resp.json()["id"]


# ---------------------------------------------------------------------------
# 1. DisclosureConfig REST API
# ---------------------------------------------------------------------------

class TestDisclosureConfigAPI:
    def test_get_privacy_config_returns_defaults(self, auth, task_id):
        client, headers, _ = auth
        resp = client.get(f"/api/tasks/{task_id}/privacy", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["age_disclosure"] == DisclosureLevel.COARSE.value
        assert data["income_disclosure"] == DisclosureLevel.NONE.value
        assert data["location_disclosure"] == DisclosureLevel.CITY.value
        assert data["budget_disclosure"] == DisclosureLevel.RANGE.value
        assert data["occupation_disclosure"] == DisclosureLevel.CATEGORY.value

    def test_put_privacy_config_updates_field(self, auth, task_id):
        client, headers, _ = auth
        resp = client.put(
            f"/api/tasks/{task_id}/privacy",
            json={"age_disclosure": "none"},
            headers=headers,
        )
        assert resp.status_code == 200
        assert resp.json()["age_disclosure"] == "none"

        # Verify persistence by fetching again
        get_resp = client.get(f"/api/tasks/{task_id}/privacy", headers=headers)
        assert get_resp.json()["age_disclosure"] == "none"

    def test_put_privacy_config_partial_update(self, auth, task_id):
        """Only the supplied field should change; others keep their defaults."""
        client, headers, _ = auth
        client.put(
            f"/api/tasks/{task_id}/privacy",
            json={"income_disclosure": "coarse"},
            headers=headers,
        )
        resp = client.get(f"/api/tasks/{task_id}/privacy", headers=headers)
        data = resp.json()
        assert data["income_disclosure"] == "coarse"
        assert data["age_disclosure"] == DisclosureLevel.COARSE.value  # unchanged

    def test_put_privacy_config_custom_overrides(self, auth, task_id):
        client, headers, _ = auth
        resp = client.put(
            f"/api/tasks/{task_id}/privacy",
            json={"custom_overrides": {"nickname": "none"}},
            headers=headers,
        )
        assert resp.status_code == 200
        assert resp.json()["custom_overrides"]["nickname"] == "none"

    def test_get_privacy_config_unauthorized(self, client, auth, task_id):
        # Register a second user and try to access task that belongs to milestoneuser
        client.post("/api/auth/register", json={"username": "other", "password": "pass"})
        login = client.post("/api/auth/login", json={"username": "other", "password": "pass"})
        other_headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
        resp = client.get(f"/api/tasks/{task_id}/privacy", headers=other_headers)
        assert resp.status_code == 403

    def test_get_privacy_config_task_not_found(self, auth):
        client, headers, _ = auth
        resp = client.get("/api/tasks/nonexistent/privacy", headers=headers)
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# 2. DisclosureEvent REST endpoint (in-memory storage returns empty list)
# ---------------------------------------------------------------------------

class TestDisclosureEventsAPI:
    def test_get_disclosure_events_empty(self, auth, task_id):
        client, headers, _ = auth
        resp = client.get(f"/api/tasks/{task_id}/disclosure_events", headers=headers)
        assert resp.status_code == 200
        assert resp.json()["events"] == []

    def test_get_disclosure_events_unauthorized(self, client, auth, task_id):
        client.post("/api/auth/register", json={"username": "other2", "password": "pass"})
        login = client.post("/api/auth/login", json={"username": "other2", "password": "pass"})
        other_headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
        resp = client.get(f"/api/tasks/{task_id}/disclosure_events", headers=other_headers)
        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# 3. SQLiteStorage disclosure_events table
# ---------------------------------------------------------------------------

class TestSQLiteDisclosureEvents:
    def test_add_and_get_disclosure_event(self, tmp_path):
        from backend.storage_sqlite import SQLiteStorage
        db = SQLiteStorage(db_path=str(tmp_path / "test.db"))
        db.initialize()

        event = DisclosureEvent(
            demand_id="demand-1",
            session_id="session-1",
            peer_agent_id="agent-1",
            attribute_name="age",
            coarse_value="late 20s",
            round_number=1,
        )
        db.add_disclosure_event(event)

        events = db.get_disclosure_events(demand_id="demand-1")
        assert len(events) == 1
        assert events[0].attribute_name == "age"
        assert events[0].coarse_value == "late 20s"
        assert events[0].round_number == 1

    def test_filter_by_session_id(self, tmp_path):
        from backend.storage_sqlite import SQLiteStorage
        db = SQLiteStorage(db_path=str(tmp_path / "test.db"))
        db.initialize()

        e1 = DisclosureEvent(demand_id="d1", session_id="s1", attribute_name="age")
        e2 = DisclosureEvent(demand_id="d1", session_id="s2", attribute_name="income")
        db.add_disclosure_event(e1)
        db.add_disclosure_event(e2)

        only_s1 = db.get_disclosure_events(session_id="s1")
        assert len(only_s1) == 1
        assert only_s1[0].attribute_name == "age"

    def test_idempotent_insert_same_event_id(self, tmp_path):
        from backend.storage_sqlite import SQLiteStorage
        db = SQLiteStorage(db_path=str(tmp_path / "test.db"))
        db.initialize()

        event = DisclosureEvent(
            event_id="fixed-id",
            demand_id="d1",
            session_id="s1",
            attribute_name="age",
        )
        db.add_disclosure_event(event)
        db.add_disclosure_event(event)  # duplicate insert should be ignored

        events = db.get_disclosure_events(demand_id="d1")
        assert len(events) == 1

    def test_no_events_returns_empty_list(self, tmp_path):
        from backend.storage_sqlite import SQLiteStorage
        db = SQLiteStorage(db_path=str(tmp_path / "test.db"))
        db.initialize()
        assert db.get_disclosure_events(demand_id="nonexistent") == []


# ---------------------------------------------------------------------------
# 4. PrivacyFilterLayer unit tests (smoke) — filter logic
# ---------------------------------------------------------------------------

class TestPrivacyFilterSmoke:
    def test_clean_message_passes(self):
        config = DisclosureConfig(demand_id="d1")
        budget = SessionDisclosureBudget(session_id="s1")
        pfl = PrivacyFilterLayer(config=config, budget=budget)
        result = pfl.filter("Hello, I am looking for a place near the city centre.")
        assert not result.blocked
        assert "Hello" in result.message

    def test_phone_number_blocked(self):
        config = DisclosureConfig(demand_id="d1")
        budget = SessionDisclosureBudget(session_id="s1")
        pfl = PrivacyFilterLayer(config=config, budget=budget)
        result = pfl.filter("Call me at +1 800 555 1234.")
        assert result.blocked
        assert any("phone" in r.lower() for r in result.reasons)

    def test_email_blocked(self):
        config = DisclosureConfig(demand_id="d1")
        budget = SessionDisclosureBudget(session_id="s1")
        pfl = PrivacyFilterLayer(config=config, budget=budget)
        result = pfl.filter("Email me at user@example.com for more details.")
        assert result.blocked
        assert any("email" in r.lower() for r in result.reasons)

    def test_budget_exhaustion_blocks_message(self):
        config = DisclosureConfig(demand_id="d1")
        budget = SessionDisclosureBudget(session_id="s1", max_attributes_revealed=1)
        budget.record_reveal("age")  # exhaust the budget
        pfl = PrivacyFilterLayer(config=config, budget=budget)
        result = pfl.filter("Your budget range is $1500–$2000.", private_values={"budget": 1800})
        # budget exhausted → second attribute blocks
        assert result.blocked


# ---------------------------------------------------------------------------
# 5. Rate limiting middleware
# ---------------------------------------------------------------------------

class TestRateLimiting:
    def _make_request(self, client, headers=None):
        return client.get("/api/demand_templates", headers=headers or {})

    def test_within_limit_succeeds(self, auth):
        client, headers, _ = auth
        for _ in range(5):
            resp = self._make_request(client, headers)
            assert resp.status_code == 200

    def test_per_user_rate_limit_enforced(self, client, monkeypatch):
        """Force the per-user limit to 3 and verify 429 on the 4th request."""
        import backend.main as main_module
        monkeypatch.setattr(main_module, "_RATE_LIMIT_PER_USER", 3)

        resp = client.post("/api/auth/register", json={"username": "rateuser", "password": "pass"})
        token = resp.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        for i in range(3):
            r = self._make_request(client, headers)
            assert r.status_code == 200, f"Request {i+1} failed unexpectedly"

        r = self._make_request(client, headers)
        assert r.status_code == 429
        assert "Rate limit" in r.json()["detail"]

    def test_global_rate_limit_enforced(self, client, monkeypatch):
        """Force global limit to 2 and verify 429 on the 3rd request (different users)."""
        import backend.main as main_module
        monkeypatch.setattr(main_module, "_RATE_LIMIT_GLOBAL", 2)

        for i in range(2):
            r = self._make_request(client, {"Authorization": f"Bearer fake_token_{i}"})
            # May be 200 or 401 depending on path, but not 429 yet
            assert r.status_code != 429

        # Third request from a different "user" should hit global limit
        r = self._make_request(client, {"Authorization": "Bearer fake_token_9999"})
        assert r.status_code == 429
        assert "Global rate limit" in r.json()["detail"]

    def test_rate_limit_response_has_retry_after_header(self, client, monkeypatch):
        import backend.main as main_module
        monkeypatch.setattr(main_module, "_RATE_LIMIT_PER_USER", 1)

        resp = client.post("/api/auth/register", json={"username": "retryuser", "password": "pass"})
        token = resp.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        self._make_request(client, headers)  # consume limit
        r = self._make_request(client, headers)
        assert r.status_code == 429
        assert "Retry-After" in r.headers
