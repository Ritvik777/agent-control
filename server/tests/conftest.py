import pytest
from fastapi.testclient import TestClient

from agent_protect_server.main import app as fastapi_app


@pytest.fixture(scope="session")
def app():
    return fastapi_app


@pytest.fixture()
def client(app: object) -> TestClient:
    return TestClient(app, raise_server_exceptions=False)
