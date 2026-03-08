import pytest
import os
import tempfile
from fastapi.testclient import TestClient

# Unset SSLKEYLOGFILE to avoid permission errors
if "SSLKEYLOGFILE" in os.environ:
    del os.environ["SSLKEYLOGFILE"]

# Set test environment variables before importing app
os.environ["STORAGE_TYPE"] = "in_memory"
os.environ["OPENAI_API_KEY"] = "dummy_key_for_testing"
os.environ["DATABASE_URL"] = ":memory:"

from backend.main import app
from backend.storage import storage


@pytest.fixture
def client():
    """Create a test client with fresh in-memory storage."""
    # Reset storage before each test
    storage.users = {}
    storage.agents = {}
    storage.tasks = {}
    storage.messages = {}
    storage.tokens = {}
    
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def auth_headers(client):
    """Create a user and return auth headers."""
    # Register user
    response = client.post("/api/auth/register", json={
        "username": "testuser",
        "password": "testpass123",
        "email": "test@test.com"
    })
    data = response.json()
    token = data["access_token"]
    
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def test_user(client):
    """Create and return a test user."""
    response = client.post("/api/auth/register", json={
        "username": "testuser",
        "password": "testpass123",
        "email": "test@test.com"
    })
    return response.json()["user"]
