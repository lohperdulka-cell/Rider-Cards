"""E2E fixtures: a real uvicorn server plus a Playwright browser.

The server runs in a subprocess against a throwaway SQLite file, so the
end-to-end suite exercises the same code path a deployment would (real HTTP,
real WebSocket, real cookies).
"""

from __future__ import annotations

import os
import socket
import subprocess
import sys
import time
from collections.abc import AsyncIterator, Iterator
from pathlib import Path

import httpx
import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
ADMIN_EMAIL = "admin@ridercards.dev"
ADMIN_PASSWORD = "AdminE2ePassw0rd!"
USER_EMAIL = "e2e-buyer@example.dev"
USER_PASSWORD = "E2eBuyerPassw0rd1"


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


@pytest.fixture(scope="session")
def base_url(tmp_path_factory: pytest.TempPathFactory) -> Iterator[str]:
    workdir = tmp_path_factory.mktemp("e2e")
    env = {
        **os.environ,
        "ENV": "e2e",
        "DEBUG": "false",
        "SECRET_KEY": "e2e-secret-key-0123456789abcdefgh",
        "DATABASE_URL": f"sqlite+aiosqlite:///{workdir / 'e2e.db'}",
        "COOKIE_SECURE": "false",
        "ADMIN_LOGIN": "admin",
        "ADMIN_PASSWORD": ADMIN_PASSWORD,
        "ADMIN_EMAIL": ADMIN_EMAIL,
    }
    port = _free_port()
    log = (workdir / "server.log").open("wb")

    seed = subprocess.run(
        [sys.executable, "-m", "app.scripts.seed"],
        cwd=PROJECT_ROOT,
        env=env,
        capture_output=True,
        text=True,
    )
    if seed.returncode != 0:  # pragma: no cover - environment failure
        pytest.fail(f"seeding failed:\n{seed.stdout}\n{seed.stderr}")

    process = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "app.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
            "--log-level",
            "warning",
        ],
        cwd=PROJECT_ROOT,
        env=env,
        stdout=log,
        stderr=subprocess.STDOUT,
    )

    url = f"http://127.0.0.1:{port}"
    deadline = time.monotonic() + 40
    while time.monotonic() < deadline:
        if process.poll() is not None:
            log.close()
            pytest.fail(f"e2e server exited early:\n{(workdir / 'server.log').read_text()}")
        try:
            if httpx.get(f"{url}/healthz", timeout=1).status_code == 200:
                break
        except httpx.HTTPError:
            time.sleep(0.3)
    else:
        process.terminate()
        log.close()
        pytest.fail("e2e server did not become ready in time")

    yield url

    process.terminate()
    try:
        process.wait(timeout=15)
    except subprocess.TimeoutExpired:  # pragma: no cover - defensive
        process.kill()
    log.close()


@pytest.fixture
async def page(base_url: str) -> AsyncIterator:
    playwright_api = pytest.importorskip("playwright.async_api")
    async with playwright_api.async_playwright() as playwright:
        try:
            browser = await playwright.chromium.launch()
        except Exception as exc:  # pragma: no cover - browser not installed
            pytest.skip(f"chromium unavailable: {exc}")
        context = await browser.new_context(base_url=base_url)
        try:
            yield await context.new_page()
        finally:
            await context.close()
            await browser.close()
