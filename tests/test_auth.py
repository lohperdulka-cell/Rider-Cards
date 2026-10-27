"""Authentication, session and CSRF behaviour."""

from __future__ import annotations

import pytest

from tests.conftest import (
    ADMIN_EMAIL,
    ADMIN_PASSWORD,
    USER_EMAIL,
    csrf_token,
    login,
    register,
)


async def test_register_login_logout_cycle(client):
    response = await register(client, "cycle@example.dev")
    assert response.status_code == 303
    assert client.cookies.get("rc_session")

    page = await client.get("/profile")
    assert page.status_code == 200
    assert "cycle@example.dev" in page.text

    token = csrf_token(page.text)
    logout = await client.post("/logout", data={"csrf_token": token})
    assert logout.status_code == 303
    assert (await client.get("/profile")).status_code == 303


async def test_duplicate_email_rejected(client):
    first = await register(client, "dup@example.dev")
    assert first.status_code == 303

    page = await client.get("/profile")
    await client.post("/logout", data={"csrf_token": csrf_token(page.text)})

    response = await register(client, "dup@example.dev")
    assert response.status_code == 400
    assert (await client.get("/profile")).status_code == 303


async def test_password_mismatch_rejected(client):
    page = await client.get("/register")
    response = await client.post(
        "/register",
        data={
            "csrf_token": csrf_token(page.text),
            "name": "Mismatch",
            "email": "mismatch@example.dev",
            "password": "Passw0rd123",
            "password_confirm": "Different123",
            "next": "/",
        },
    )
    assert response.status_code == 400


async def test_login_with_wrong_password_fails(client):
    response = await login(client, USER_EMAIL, "definitely-wrong")
    assert response.status_code == 400
    assert not client.cookies.get("rc_session")


async def test_admin_can_log_in_and_reaches_dashboard(client):
    response = await login(client, ADMIN_EMAIL, ADMIN_PASSWORD)
    assert response.status_code == 303
    assert (await client.get("/admin")).status_code == 200


@pytest.mark.parametrize("path", ["/admin", "/admin/orders", "/admin/products", "/admin/users"])
async def test_admin_area_forbidden_for_regular_user(client, path):
    await login(client)
    assert (await client.get(path)).status_code == 403


async def test_admin_area_requires_session(client):
    response = await client.get("/admin", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"].startswith("/login")

    api = await client.get("/admin", headers={"accept": "application/json"})
    assert api.status_code == 401


async def test_post_without_csrf_token_is_rejected(client):
    response = await client.post("/cart/add", data={"product_id": "1", "qty": "1"})
    assert response.status_code == 403


async def test_profile_redirects_to_login_without_session(client):
    response = await client.get("/profile", headers={"accept": "text/html"}, follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"].startswith("/login")

    api = await client.get("/profile", headers={"accept": "application/json"})
    assert api.status_code == 401
