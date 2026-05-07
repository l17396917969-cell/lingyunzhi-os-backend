# tests/integration/test_static_serving.py
import pathlib

import pytest
from httpx import ASGITransport, AsyncClient

from onto_platform.app import create_app

pytestmark = pytest.mark.asyncio


@pytest.fixture
def ui_dist_dir(tmp_path: pathlib.Path) -> pathlib.Path:
    """Create a minimal SPA dist directory with an index.html."""
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "index.html").write_text(
        "<!doctype html><html><body>SPA</body></html>", encoding="utf-8"
    )
    return dist


async def test_ui_dist_served_at_root(
    postgres_url: str, monkeypatch: pytest.MonkeyPatch, ui_dist_dir: pathlib.Path
) -> None:
    """GET / returns the SPA index.html when ONTO_UI_DIST_PATH is set."""
    monkeypatch.setenv("ONTO_DATABASE_URL", postgres_url)
    monkeypatch.setenv("ONTO_SECRET_KEY", "0" * 44)
    monkeypatch.setenv("ONTO_UI_DIST_PATH", str(ui_dist_dir))

    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r = await c.get("/")

    assert r.status_code == 200
    assert "SPA" in r.text


async def test_unknown_path_serves_index_html(
    postgres_url: str, monkeypatch: pytest.MonkeyPatch, ui_dist_dir: pathlib.Path
) -> None:
    """GET /some/spa/route returns the SPA index.html (html=True fallback)."""
    monkeypatch.setenv("ONTO_DATABASE_URL", postgres_url)
    monkeypatch.setenv("ONTO_SECRET_KEY", "0" * 44)
    monkeypatch.setenv("ONTO_UI_DIST_PATH", str(ui_dist_dir))

    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r = await c.get("/some/spa/route")

    assert r.status_code == 200
    assert "SPA" in r.text
