import pytest
import os
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient

os.environ["SECRET_KEY"] = "test-secret"
os.environ["MP_ACCESS_TOKEN"] = "test-token"

patcher = patch("app.db.database.init_db", new_callable=AsyncMock)
patcher.start()

@pytest.fixture
def app():
    from app.main import app
    return app

@pytest.fixture
def client(app):
    with TestClient(app) as client:
        yield client
