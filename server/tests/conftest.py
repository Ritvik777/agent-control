import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from agent_protect_server.main import app as fastapi_app
from agent_protect_server.db import engine, Base
import agent_protect_server.models  # ensure models are imported so tables are registered


@pytest.fixture(scope="session")
def app():
    return fastapi_app


@pytest.fixture(scope="session", autouse=True)
def db_schema() -> None:
    # Recreate schema for tests
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield


@pytest.fixture()
def client(app: object) -> TestClient:
    return TestClient(app, raise_server_exceptions=True)


@pytest.fixture(autouse=True)
def clean_db():
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM agents"))
    yield
