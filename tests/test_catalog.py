"""Catalogue browsing, filters and product pages."""

from __future__ import annotations

import pytest


@pytest.mark.parametrize(
    "path",
    [
        "/",
        "/catalog",
        "/news",
        "/about",
        "/faq",
        "/support",
        "/cart",
        "/login",
        "/register",
        "/robots.txt",
        "/sitemap.xml",
    ],
)
async def test_public_pages_return_200(client, path):
    response = await client.get(path)
    assert response.status_code == 200
    assert response.content


async def test_unknown_page_returns_custom_404(client):
    response = await client.get("/definitely-missing")
    assert response.status_code == 404


async def test_catalog_lists_seeded_products(client):
    response = await client.get("/catalog")
    assert "test-deck" in response.text
    assert "cheap-deck" in response.text


async def test_catalog_price_filter_excludes_expensive_deck(client):
    response = await client.get("/catalog", params={"max_price": "600"})
    assert response.status_code == 200
    assert "cheap-deck" in response.text
    assert "test-deck" not in response.text


async def test_catalog_search_matches_name(client):
    response = await client.get("/catalog", params={"q": "Тестовая"})
    assert response.status_code == 200
    assert "test-deck" in response.text


async def test_product_page_shows_price_and_stock(client):
    response = await client.get("/product/test-deck")
    assert response.status_code == 200
    assert "1 000" in response.text or "1000" in response.text


async def test_out_of_stock_product_is_marked(client):
    response = await client.get("/product/cheap-deck")
    assert response.status_code == 200
    assert "out-of-stock" in response.text or "Нет в наличии" in response.text


async def test_missing_product_returns_404(client):
    assert (await client.get("/product/does-not-exist")).status_code == 404


async def test_catalog_html_is_escaped(client):
    response = await client.get("/catalog", params={"q": "<script>alert(1)</script>"})
    assert response.status_code == 200
    assert "<script>alert(1)</script>" not in response.text


async def test_security_headers_present(client):
    response = await client.get("/")
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
    csp = response.headers["Content-Security-Policy"]
    assert "default-src 'self'" in csp
    # Inline scripts are not allowed: every script is served from /static.
    assert "script-src 'self';" in csp
    assert "unsafe-inline" not in csp.split("style-src")[0]
    assert response.headers["Referrer-Policy"] == "strict-origin-when-cross-origin"


async def test_language_switch_changes_copy(client):
    ru = await client.get("/", params={"lang": "ru"})
    en = await client.get("/", params={"lang": "en"})
    assert ru.status_code == en.status_code == 200
    assert ru.text != en.text
    assert "Catalog" in en.text or "Shop" in en.text
