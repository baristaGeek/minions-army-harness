"""Integration test examples."""

import pytest
from fastapi.testclient import TestClient

from minions_army.infrastructure.api.fastapi_app import app


class TestAPIIntegration:
    """Integration tests for API endpoints."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        return TestClient(app)

    def test_health_endpoint_returns_healthy(self, client):
        """Test that health endpoint returns healthy status."""
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"

    def test_api_root_returns_welcome_message(self, client):
        """Test that API root returns welcome message."""
        response = client.get("/api/v1/")
        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        assert "Minions Army" in data["message"]
