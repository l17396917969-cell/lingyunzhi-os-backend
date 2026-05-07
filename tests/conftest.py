import os
import subprocess
import pytest
from testcontainers.postgres import PostgresContainer


@pytest.fixture(scope="session")
def postgres_container():
    with PostgresContainer("postgres:16-alpine") as pg:
        yield pg


@pytest.fixture(scope="session")
def postgres_url(postgres_container):
    raw = postgres_container.get_connection_url()
    # testcontainers may return postgresql+psycopg2://... or postgresql://...
    # Normalise to postgresql+asyncpg://...
    import re
    url = re.sub(r"^postgresql(?:\+\w+)?://", "postgresql+asyncpg://", raw)
    env = os.environ.copy()
    env["ONTO_DATABASE_URL"] = url
    env["ONTO_SECRET_KEY"] = "0" * 44
    subprocess.run(["uv", "run", "alembic", "upgrade", "head"], check=True, env=env)
    return url
