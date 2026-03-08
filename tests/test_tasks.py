import pytest
from fastapi.testclient import TestClient


class TestTasks:
    """Test task management endpoints."""
    
    def test_create_task(self, client: TestClient, auth_headers: dict):
        """Test creating a new task."""
        response = client.post("/api/tasks/", 
            headers=auth_headers,
            json={
                "task_type": "dating",
                "description": "Looking for a partner",
                "requirements": {"age": "25-30", "location": "Beijing"}
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert data["task_type"] == "dating"
        assert data["description"] == "Looking for a partner"
        assert data["status"] == "pending"
        assert "id" in data
        assert "agent_id" in data
    
    def test_get_tasks(self, client: TestClient, auth_headers: dict):
        """Test getting all tasks for user."""
        # Create a task first
        client.post("/api/tasks/",
            headers=auth_headers,
            json={
                "task_type": "rental",
                "description": "Looking for apartment"
            }
        )
        
        # Get tasks
        response = client.get("/api/tasks/", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 1
    
    def test_get_task_by_id(self, client: TestClient, auth_headers: dict):
        """Test getting a specific task."""
        # Create a task
        create_response = client.post("/api/tasks/",
            headers=auth_headers,
            json={
                "task_type": "gaming",
                "description": "Looking for teammates"
            }
        )
        task_id = create_response.json()["id"]
        
        # Get specific task
        response = client.get(f"/api/tasks/{task_id}", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == task_id
        assert data["task_type"] == "gaming"
    
    def test_update_task(self, client: TestClient, auth_headers: dict):
        """Test updating a task."""
        # Create a task
        create_response = client.post("/api/tasks/",
            headers=auth_headers,
            json={
                "task_type": "dating",
                "description": "Original description"
            }
        )
        task_id = create_response.json()["id"]
        
        # Update task
        response = client.put(f"/api/tasks/{task_id}",
            headers=auth_headers,
            json={
                "description": "Updated description",
                "requirements": {"updated": True}
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert data["description"] == "Updated description"
    
    def test_delete_task(self, client: TestClient, auth_headers: dict):
        """Test deleting a task."""
        # Create a task
        create_response = client.post("/api/tasks/",
            headers=auth_headers,
            json={
                "task_type": "rental",
                "description": "To be deleted"
            }
        )
        task_id = create_response.json()["id"]
        
        # Delete task
        response = client.delete(f"/api/tasks/{task_id}", headers=auth_headers)
        assert response.status_code == 200
        
        # Verify deletion
        get_response = client.get(f"/api/tasks/{task_id}", headers=auth_headers)
        assert get_response.status_code == 404
    
    def test_create_task_unauthorized(self, client: TestClient):
        """Test creating task without authentication."""
        response = client.post("/api/tasks/", json={
            "task_type": "dating",
            "description": "Test"
        })
        assert response.status_code == 401
    
    def test_get_other_user_task(self, client: TestClient):
        """Test accessing another user's task."""
        # Create first user and task
        user1_response = client.post("/api/auth/register", json={
            "username": "user1",
            "password": "pass123",
            "email": "user1@test.com"
        })
        user1_token = user1_response.json()["access_token"]
        
        task_response = client.post("/api/tasks/",
            headers={"Authorization": f"Bearer {user1_token}"},
            json={"task_type": "dating", "description": "Private task"}
        )
        task_id = task_response.json()["id"]
        
        # Create second user
        user2_response = client.post("/api/auth/register", json={
            "username": "user2",
            "password": "pass123",
            "email": "user2@test.com"
        })
        user2_token = user2_response.json()["access_token"]
        
        # Try to access user1's task with user2's token
        response = client.get(f"/api/tasks/{task_id}",
            headers={"Authorization": f"Bearer {user2_token}"}
        )
        assert response.status_code == 403
