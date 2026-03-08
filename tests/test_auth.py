import pytest
from fastapi.testclient import TestClient


class TestAuth:
    """Test authentication endpoints."""
    
    def test_register_success(self, client: TestClient):
        """Test successful user registration."""
        response = client.post("/api/auth/register", json={
            "username": "newuser",
            "password": "password123",
            "email": "newuser@test.com"
        })
        assert response.status_code == 200
        data = response.json()
        assert "user" in data
        assert "access_token" in data
        assert data["user"]["username"] == "newuser"
        assert data["token_type"] == "bearer"
    
    def test_register_duplicate_username(self, client: TestClient):
        """Test registration with duplicate username."""
        # First registration
        client.post("/api/auth/register", json={
            "username": "duplicate",
            "password": "password123",
            "email": "first@test.com"
        })
        
        # Second registration with same username
        response = client.post("/api/auth/register", json={
            "username": "duplicate",
            "password": "password123",
            "email": "second@test.com"
        })
        assert response.status_code == 400
        assert "Username already exists" in response.json()["detail"]
    
    def test_login_success(self, client: TestClient):
        """Test successful login."""
        # Register first
        client.post("/api/auth/register", json={
            "username": "loginuser",
            "password": "password123",
            "email": "login@test.com"
        })
        
        # Login
        response = client.post("/api/auth/login", json={
            "username": "loginuser",
            "password": "password123"
        })
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["user"]["username"] == "loginuser"
    
    def test_login_invalid_credentials(self, client: TestClient):
        """Test login with invalid credentials."""
        response = client.post("/api/auth/login", json={
            "username": "nonexistent",
            "password": "wrongpassword"
        })
        assert response.status_code == 401
        assert "Invalid" in response.json()["detail"]
    
    def test_logout_success(self, client: TestClient, auth_headers: dict):
        """Test successful logout."""
        # Extract token from auth_headers
        token = auth_headers["Authorization"].replace("Bearer ", "")
        
        response = client.post("/api/auth/logout", 
            headers=auth_headers,
            json={"access_token": token}
        )
        assert response.status_code == 200
        assert "Logged out" in response.json()["message"]
        
        # Verify token is revoked
        response = client.get("/api/tasks/", headers=auth_headers)
        assert response.status_code == 401
    
    def test_protected_endpoint_without_token(self, client: TestClient):
        """Test accessing protected endpoint without token."""
        response = client.get("/api/tasks/")
        assert response.status_code == 401
    
    def test_protected_endpoint_with_invalid_token(self, client: TestClient):
        """Test accessing protected endpoint with invalid token."""
        response = client.get("/api/tasks/", headers={
            "Authorization": "Bearer invalid_token"
        })
        assert response.status_code == 401
