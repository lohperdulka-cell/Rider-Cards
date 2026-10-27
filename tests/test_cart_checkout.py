"""Cart behaviour and the checkout -> order -> chat flow."""

from __future__ import annotations

from tests.conftest import csrf_token, login


async def _add_to_cart(client, product_id: int, qty: int = 1):
    page = await client.get("/catalog")
    return await client.post(
        "/cart/add",
        data={"csrf_token": csrf_token(page.text), "product_id": str(product_id), "qty": str(qty)},
        headers={"X-Requested-With": "fetch"},
    )


async def test_guest_can_add_to_cart(client):
    response = await _add_to_cart(client, 1, 2)
    assert response.status_code == 200
    assert response.json()["ok"] is True
    assert response.json()["cart_count"] == 2
    assert client.cookies.get("rc_cart")


async def test_cart_page_renders_added_item(client):
    await _add_to_cart(client, 1, 3)
    response = await client.get("/cart")
    assert response.status_code == 200
    assert "Тестовая колода" in response.text


async def test_cart_update_and_remove(client):
    await _add_to_cart(client, 1, 1)
    page = await client.get("/cart")
    token = csrf_token(page.text)

    updated = await client.post(
        "/cart/update",
        data={"csrf_token": token, "product_id": "1", "qty": "5"},
        headers={"HX-Request": "true"},
    )
    assert updated.status_code == 200

    removed = await client.post(
        "/cart/remove",
        data={"csrf_token": token, "product_id": "1"},
        headers={"HX-Request": "true"},
    )
    assert removed.status_code == 200

    cart = await client.get("/cart")
    assert "Тестовая колода" not in cart.text


async def test_cart_add_ignores_unknown_product(client):
    response = await _add_to_cart(client, 999999)
    assert response.status_code == 404
    assert response.json()["ok"] is False


async def test_checkout_requires_login(client):
    await _add_to_cart(client, 1, 1)
    response = await client.get("/checkout")
    assert response.status_code == 303
    assert response.headers["location"].startswith("/login")


async def test_checkout_creates_order_and_chat_with_system_message(client):
    await login(client)
    await _add_to_cart(client, 1, 2)

    page = await client.get("/checkout")
    assert page.status_code == 200
    response = await client.post(
        "/checkout",
        data={
            "csrf_token": csrf_token(page.text),
            "contact": "buyer@example.dev",
            "address": "Москва, ул. Тестовая 1",
            "note": "домофон 5",
        },
    )
    assert response.status_code == 303
    assert "/profile/orders/" in response.headers["location"]
    assert client.cookies.get("rc_cart") is None

    order_page = await client.get(response.headers["location"])
    assert order_page.status_code == 200
    assert "Ожидает оплаты" in order_page.text

    chats = await client.get("/chats")
    assert chats.status_code == 200

    import re

    chat_id = re.search(r'href="/chats/(\d+)"', chats.text)
    assert chat_id, "order chat link missing"

    thread = await client.get(f"/chats/{chat_id.group(1)}")
    assert thread.status_code == 200
    assert "Ожидает оплаты" in thread.text
    assert "1 000" in thread.text or "2000" in thread.text or "2 000" in thread.text


async def test_empty_cart_checkout_redirects_back(client):
    await login(client)
    response = await client.get("/checkout")
    assert response.status_code == 303
    assert response.headers["location"] == "/cart"


async def test_checkout_validation_errors_are_shown(client):
    await login(client)
    await _add_to_cart(client, 1, 1)
    page = await client.get("/checkout")
    response = await client.post(
        "/checkout",
        data={"csrf_token": csrf_token(page.text), "contact": "not-an-email", "address": ""},
    )
    assert response.status_code == 400
    assert "not-an-email" in response.text or "contact" in response.text


async def test_orders_list_shows_created_order(client):
    await login(client)
    await _add_to_cart(client, 1, 1)
    page = await client.get("/checkout")
    created = await client.post(
        "/checkout",
        data={
            "csrf_token": csrf_token(page.text),
            "contact": "buyer@example.dev",
            "address": "Санкт-Петербург, Невский 10",
            "note": "",
        },
    )
    assert created.status_code == 303

    orders = await client.get("/profile/orders")
    assert orders.status_code == 200
    assert "/profile/orders/" in orders.text


async def test_user_cannot_open_someone_elses_order(client):
    await login(client)
    await _add_to_cart(client, 1, 1)
    page = await client.get("/checkout")
    created = await client.post(
        "/checkout",
        data={
            "csrf_token": csrf_token(page.text),
            "contact": "buyer@example.dev",
            "address": "Казань, Баумана 3",
            "note": "",
        },
    )
    order_path = created.headers["location"]

    page = await client.get("/profile")
    await client.post("/logout", data={"csrf_token": csrf_token(page.text)})

    from tests.conftest import register

    await register(client, "intruder@example.dev")
    response = await client.get(order_path)
    assert response.status_code == 404
