import pytest
import os
import asyncio
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient

os.environ["SECRET_KEY"] = "test-secret"
os.environ["MP_ACCESS_TOKEN"] = "test-token"
os.environ["TESTING"] = "1"

use_real_db = os.getenv("TESTING_WITH_REAL_DB") in ("1", "true", "True")

if not use_real_db:
    patcher = patch("app.db.database.init_db", new_callable=AsyncMock)
    patcher.start()
else:
    if "DATABASE_URL" not in os.environ:
        os.environ["DATABASE_URL"] = "postgresql://postgres:mypassword123@localhost:5432/mldb"

@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for each test case."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

@pytest.fixture(scope="session", autouse=True)
def db_setup(event_loop):
    if use_real_db:
        from app.db.database import init_db
        event_loop.run_until_complete(init_db())

@pytest.fixture(autouse=True)
async def clean_database():
    if use_real_db:
        from app.db.database import get_db
        async with get_db() as db:
            await db.execute("TRUNCATE TABLE users, quota_usage, payments CASCADE;")
        yield
        async with get_db() as db:
            await db.execute("TRUNCATE TABLE users, quota_usage, payments CASCADE;")
    else:
        yield

@pytest.fixture
def app():
    from app.main import app
    return app

@pytest.fixture
def client(app):
    with TestClient(app) as client:
        yield client
