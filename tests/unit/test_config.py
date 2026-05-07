import os
import pytest
from onto_platform.config import Settings


def test_settings_loads_from_env(monkeypatch):
    monkeypatch.setenv("ONTO_DATABASE_URL", "postgresql+asyncpg://u:p@h/db")
    monkeypatch.setenv("ONTO_SECRET_KEY", "0" * 44)
    s = Settings()
    assert str(s.database_url) == "postgresql+asyncpg://u:p@h/db"
    assert s.bind_port == 8080  # default
    assert s.query_default_max_rows == 1000  # default


def test_settings_requires_secret_key(monkeypatch):
    monkeypatch.setenv("ONTO_DATABASE_URL", "postgresql+asyncpg://u:p@h/db")
    monkeypatch.delenv("ONTO_SECRET_KEY", raising=False)
    with pytest.raises(ValueError):
        Settings()
