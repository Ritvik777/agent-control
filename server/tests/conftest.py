import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text, create_engine

from agent_protect_server.main import app as fastapi_app
from agent_protect_server.db import engine, Base
from agent_protect_server.config import db_config
import agent_protect_server.models  # ensure models are imported so tables are registered


@pytest.fixture(scope="session")
def app():
    return fastapi_app


@pytest.fixture(scope="session", autouse=True)
def db_schema() -> None:
    # Ensure test database exists (PostgreSQL)
    if engine.dialect.name == "postgresql":
        admin_url = (
            f"postgresql+{db_config.driver}://{db_config.user}:{db_config.password}@"
            f"{db_config.host}:{db_config.port}/postgres"
        )
        admin_engine = create_engine(admin_url, isolation_level="AUTOCOMMIT")
        with admin_engine.connect() as conn:
            exists = conn.execute(
                text("SELECT 1 FROM pg_database WHERE datname = :name"),
                {"name": db_config.database},
            ).scalar()
            if not exists:
                conn.execute(text(f'CREATE DATABASE "{db_config.database}"'))
        admin_engine.dispose()

    # Recreate tables for tests in the configured database
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
