import pytest
import os
from fastapi.testclient import TestClient

# Mock environment variables before importing app
os.environ["SECRET_KEY"] = "test-secret"
os.environ["MP_ACCESS_TOKEN"] = "test-token"

@pytest.fixture
def app():
    from app.main import app
    return app

@pytest.fixture
def client(app):
    with TestClient(app) as client:
        yield client
