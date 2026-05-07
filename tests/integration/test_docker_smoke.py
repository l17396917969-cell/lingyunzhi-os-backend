"""Docker compose smoke test — requires Docker to be available.

Gated behind pytest.mark.e2e; skipped automatically when Docker is not present.
"""
from __future__ import annotations

import os
import subprocess
import time

import httpx
import pytest

pytestmark = pytest.mark.e2e


def _have_docker() -> bool:
    return subprocess.run(["docker", "info"], capture_output=True).returncode == 0


@pytest.mark.skipif(not _have_docker(), reason="Docker not available")
def test_compose_up_and_healthy(tmp_path: os.PathLike[str]) -> None:
    env_file = str(tmp_path) + "/.env"
    with open(env_file, "w") as f:
        f.write("ONTO_SECRET_KEY=" + ("a" * 44) + "\n")
    cwd = os.path.join(os.path.dirname(__file__), "..", "..", "docker")
    subprocess.run(
        ["docker", "compose", "--env-file", env_file, "up", "-d", "--build"],
        cwd=cwd,
        check=True,
    )
    try:
        deadline = time.time() + 60
        ok = False
        while time.time() < deadline:
            try:
                r = httpx.get("http://127.0.0.1:8080/healthz", timeout=2.0)
                if r.status_code == 200:
                    ok = True
                    break
            except Exception:
                pass
            time.sleep(2)
        assert ok, "app did not become healthy in 60s"
    finally:
        subprocess.run(["docker", "compose", "down", "-v"], cwd=cwd, check=False)
