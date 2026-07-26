"""Pytest configuration and fixtures."""

import os

import pytest

os.environ["DEBUG"] = "false"
# The config singleton validates database.url at import time. Provide a default
# so the suite runs without external setup; real envs (CI, Docker) still win.
os.environ.setdefault(
    "DATABASE_URL", "postgresql+asyncpg://user:password@localhost:5432/minions_army"
)


@pytest.fixture
def app():
    """Create application for testing."""
    from minions_army.infrastructure.api.fastapi_app import app as web_app

    return web_app


@pytest.fixture
async def client(app):
    """Create test client."""
    from fastapi.testclient import TestClient

    return TestClient(app)
