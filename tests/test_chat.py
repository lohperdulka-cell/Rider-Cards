"""Order chat: access control, rate limit, read tracking and admin status push."""

from __future__ import annotations

import re

from tests.conftest import ADMIN_EMAIL, ADMIN_PASSWORD, csrf_token, login, register


async def _create_order(client) -> tuple[str, str]:
    """Create an order for the logged-in user, returning (order_path, chat_id)."""
    catalog = await client.get("/catalog")
    await client.post(
        "/cart/add",
        data={"csrf_token": csrf_token(catalog.text), "product_id": "1", "qty": "1"},
        headers={"X-Requested-With": "fetch"},
    )
    page = await client.get("/checkout")
    created = await client.post(
        "/checkout",
        data={
            "csrf_token": csrf_token(page.text),
            "contact": "buyer@example.dev",
            "address": "Москва, Тестовая 1",
            "note": "",
        },
    )
    assert created.status_code == 303
    order_path = created.headers["location"]

    chats = await client.get("/chats")
    chat_id = re.search(r'href="/chats/(\d+)"', chats.text).group(1)
    return order_path, chat_id


async def test_order_creation_posts_system_message(client):
    await login(client)
    _, chat_id = await _create_order(client)

    thread = await client.get(f"/chats/{chat_id}")
    assert "Заказ #" in thread.text
    assert "Ожидает оплаты" in thread.text


async def test_user_message_appears_in_polling_feed(client):
    await login(client)
    _, chat_id = await _create_order(client)

    thread = await client.get(f"/chats/{chat_id}")
    sent = await client.post(
        f"/chats/{chat_id}/messages",
        data={"csrf_token": csrf_token(thread.text), "text": "Здравствуйте, когда отправка?"},
        headers={"X-Requested-With": "fetch"},
    )
    assert sent.status_code == 200
    assert sent.json()["ok"] is True

    feed = await client.get(f"/chats/{chat_id}/messages")
    assert feed.status_code == 200
    texts = [item["text"] for item in feed.json()["messages"]]
    assert "Здравствуйте, когда отправка?" in texts


async def test_rate_limit_blocks_second_message(client):
    await login(client)
    _, chat_id = await _create_order(client)

    thread = await client.get(f"/chats/{chat_id}")
    token = csrf_token(thread.text)
    first = await client.post(
        f"/chats/{chat_id}/messages",
        data={"csrf_token": token, "text": "Первое"},
        headers={"X-Requested-With": "fetch"},
    )
    second = await client.post(
        f"/chats/{chat_id}/messages",
        data={"csrf_token": token, "text": "Второе"},
        headers={"X-Requested-With": "fetch"},
    )
    assert first.status_code == 200
    assert second.status_code == 429


async def test_user_cannot_read_or_post_to_foreign_chat(client):
    await login(client)
    _, chat_id = await _create_order(client)

    page = await client.get("/profile")
    await client.post("/logout", data={"csrf_token": csrf_token(page.text)})
    await register(client, "spy@example.dev")

    assert (await client.get(f"/chats/{chat_id}")).status_code == 403
    assert (await client.get(f"/chats/{chat_id}/messages")).status_code == 403

    thread = await client.get(f"/chats/{chat_id}", follow_redirects=True)
    token = csrf_token(thread.text)
    posted = await client.post(
        f"/chats/{chat_id}/messages",
        data={"csrf_token": token, "text": "взлом"},
        headers={"X-Requested-With": "fetch"},
    )
    assert posted.status_code == 403


async def test_admin_status_change_writes_system_message_and_unblocks_chat(client):
    await login(client)
    order_path, chat_id = await _create_order(client)
    order_id = order_path.rsplit("/", 1)[-1]
    page = await client.get("/profile")
    await client.post("/logout", data={"csrf_token": csrf_token(page.text)})

    await login(client, ADMIN_EMAIL, ADMIN_PASSWORD)
    detail = await client.get(f"/admin/orders/{order_id}")
    assert detail.status_code == 200

    changed = await client.post(
        f"/admin/orders/{order_id}/status",
        data={"csrf_token": csrf_token(detail.text), "status": "shipped"},
    )
    assert changed.status_code == 303

    thread = await client.get(f"/admin/chats/{chat_id}")
    assert thread.status_code == 200
    assert "Отправлен" in thread.text


async def test_admin_can_reply_and_user_sees_it(client):
    await login(client)
    order_path, chat_id = await _create_order(client)

    page = await client.get("/profile")
    await client.post("/logout", data={"csrf_token": csrf_token(page.text)})

    await login(client, ADMIN_EMAIL, ADMIN_PASSWORD)
    thread = await client.get(f"/admin/chats/{chat_id}")
    reply = await client.post(
        f"/chats/{chat_id}/messages",
        data={"csrf_token": csrf_token(thread.text), "text": "Здравствуйте! Отправим сегодня."},
        headers={"X-Requested-With": "fetch"},
    )
    assert reply.status_code == 200
    assert reply.json()["ok"] is True

    await client.post("/logout", data={"csrf_token": csrf_token((await client.get("/admin")).text)})
    await login(client)
    feed = await client.get(f"/chats/{chat_id}/messages")
    texts = [item["text"] for item in feed.json()["messages"]]
    assert "Здравствуйте! Отправим сегодня." in texts


async def test_chat_messages_endpoint_requires_auth(client):
    assert (await client.get("/chats/1/messages")).status_code == 401


async def test_closed_chat_rejects_new_messages(client):
    await login(client)
    order_path, chat_id = await _create_order(client)
    order_id = order_path.rsplit("/", 1)[-1]
    page = await client.get("/profile")
    await client.post("/logout", data={"csrf_token": csrf_token(page.text)})

    await login(client, ADMIN_EMAIL, ADMIN_PASSWORD)
    detail = await client.get(f"/admin/orders/{order_id}")
    await client.post(
        f"/admin/chats/{chat_id}/close",
        data={"csrf_token": csrf_token(detail.text)},
    )
    assert (await client.get(f"/admin/chats/{chat_id}")).status_code == 200
