from onto_platform.config import Settings


def test_chat_settings_have_sensible_defaults():
    s = Settings(database_url="postgresql+asyncpg://x", secret_key="x" * 44)
    assert s.chat_session_orphan_after_s == 1800
    assert s.chat_turn_max_wall_clock_s == 1800
    assert s.chat_sse_heartbeat_s == 15
    assert s.chat_max_concurrent_sessions_per_token == 5


def test_chat_settings_can_be_overridden_via_env(monkeypatch):
    monkeypatch.setenv("ONTO_DATABASE_URL", "postgresql+asyncpg://x")
    monkeypatch.setenv("ONTO_SECRET_KEY", "x" * 44)
    monkeypatch.setenv("ONTO_CHAT_SESSION_ORPHAN_AFTER_S", "60")
    monkeypatch.setenv("ONTO_CHAT_SSE_HEARTBEAT_S", "5")
    s = Settings()
    assert s.chat_session_orphan_after_s == 60
    assert s.chat_sse_heartbeat_s == 5
