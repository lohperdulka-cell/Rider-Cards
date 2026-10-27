"""End-to-end journey: register, buy a deck, chat with support as admin.

Run with ``make e2e`` (needs ``playwright install chromium``).
"""

from __future__ import annotations

import re

import pytest

from tests.e2e.conftest import ADMIN_EMAIL, ADMIN_PASSWORD, USER_EMAIL, USER_PASSWORD

BUYER_MESSAGE = "Здравствуйте! Подскажите, когда отправка?"
ADMIN_REPLY = "Здравствуйте! Отправим заказ сегодня."


async def _register(page) -> None:
    await page.goto("/register")
    await page.fill("#reg-name", "E2E Buyer")
    await page.fill("#reg-email", USER_EMAIL)
    await page.fill("#reg-password", USER_PASSWORD)
    await page.fill("#reg-password-confirm", USER_PASSWORD)
    await page.click("button[type=submit]")
    await page.wait_for_load_state("load")
    if "/register" in page.url:
        # The account already exists from an earlier run against the same DB.
        await _login(page, USER_EMAIL, USER_PASSWORD)


async def _login(page, email: str, password: str) -> None:
    await page.goto("/login")
    await page.fill("#login-email", email)
    await page.fill("#login-password", password)
    await page.click("button[type=submit]")
    await page.wait_for_url(re.compile(r"/$"))


async def test_register_browse_cart_checkout_and_chat(page):
    await _register(page)
    assert "/profile" not in page.url

    # Catalogue -> product page -> add to cart.
    await page.goto("/catalog")
    await page.wait_for_selector("article, a[href^='/product/']")
    await page.click("a[href^='/product/']")
    await page.wait_for_selector("[data-add-to-cart]")
    async with page.expect_response(
        lambda r: r.url.endswith("/cart/add") and r.request.method == "POST"
    ) as add_response:
        await page.click("[data-add-to-cart] button[type=submit]")
    assert (await add_response.value).status == 200
    await page.wait_for_function(
        "() => (document.querySelector('[data-badge=cart]')?.textContent || '').trim() === '1'",
        timeout=15000,
    )

    # Cart page shows the deck and the checkout link.
    await page.goto("/cart")
    await page.wait_for_selector("a[href='/checkout']")
    assert await page.locator("a[href^='/product/']").first.is_visible()

    # Checkout -> order created, redirected to the order page.
    await page.goto("/checkout")
    await page.fill("#checkout-contact", USER_EMAIL)
    await page.fill("#checkout-address", "Москва, ул. Тестовая, д. 1, кв. 5")
    await page.fill("#checkout-note", "Позвоните перед доставкой")
    await page.click("form[action='/checkout'] button[type=submit]")
    await page.wait_for_url(re.compile(r"/profile/orders/\d+"))
    order_url = page.url
    assert "Ожидает оплаты" in await page.content()

    # The order chat exists and already holds the system message.
    await page.goto("/chats")
    await page.wait_for_selector("a[href^='/chats/']")
    await page.click("a[href^='/chats/']")
    await page.wait_for_selector("[data-chat-form]")
    chat_url = page.url
    assert "Ожидает оплаты" in await page.content()

    # Buyer sends a message and it shows up in the thread.
    await page.fill("[data-chat-input]", BUYER_MESSAGE)
    await page.press("[data-chat-input]", "Enter")
    await page.wait_for_selector(f"text={BUYER_MESSAGE}", timeout=15000)

    # --- Admin side: same browser, new session in a clean context. ---
    context = page.context
    admin_context = await context.browser.new_context(base_url=page.url.split("/chats")[0])
    admin_page = await admin_context.new_page()
    try:
        await _login(admin_page, ADMIN_EMAIL, ADMIN_PASSWORD)
        await admin_page.goto(chat_url)
        await admin_page.wait_for_selector("[data-chat-form]")
        assert BUYER_MESSAGE in await admin_page.content()

        await admin_page.fill("[data-chat-input]", ADMIN_REPLY)
        await admin_page.press("[data-chat-input]", "Enter")
        await admin_page.wait_for_selector(f"text={ADMIN_REPLY}", timeout=15000)
    finally:
        await admin_context.close()

    # Buyer reloads and sees the support answer.
    await page.reload()
    await page.wait_for_selector(f"text={ADMIN_REPLY}", timeout=15000)
    assert re.search(r"/profile/orders/\d+$", order_url), order_url


@pytest.mark.parametrize(
    "path",
    ["/", "/catalog", "/news", "/about", "/faq", "/support", "/cart", "/login", "/register"],
)
async def test_public_pages_render_in_browser(page, path):
    errors: list[str] = []
    page.on("pageerror", lambda exc: errors.append(str(exc)))
    response = await page.goto(path)
    assert response is not None and response.status == 200
    assert await page.title()
    assert errors == [], f"JS errors on {path}: {errors}"


async def test_csp_blocks_no_own_assets(page):
    """The strict CSP must not block the app's own scripts or styles."""
    blocked: list[str] = []
    page.on(
        "console",
        lambda msg: (
            blocked.append(msg.text)
            if msg.type == "error" and ("Content Security Policy" in msg.text or "Refused to" in msg.text)
            else None
        ),
    )
    for path in ("/", "/catalog", "/product/archive-1987", "/admin"):
        await page.goto(path)
    assert blocked == [], f"CSP violations: {blocked}"


async def test_mobile_burger_menu_opens(page):
    await page.set_viewport_size({"width": 390, "height": 844})
    await page.goto("/")
    panel = page.locator("#rc-mobile-menu")
    assert not await panel.is_visible()
    await page.click("#rc-burger")
    await panel.wait_for(state="visible")
    assert await page.locator("#rc-mobile-menu nav").first.is_visible()


async def test_guest_profile_redirects_to_login(page):
    await page.goto("/profile")
    assert "/login" in page.url


async def test_language_switch_flips_copy(page):
    await page.goto("/")
    await page.goto("/?lang=en")
    content = await page.content()
    assert "Catalog" in content or "Shop" in content
