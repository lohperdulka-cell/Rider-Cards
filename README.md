# RiderCards

Премиальный интернет-магазин игральных карт: коллекционные, дизайнерские, классические
колоды и карты для фокусов. Полностью серверный рендеринг на FastAPI + Jinja2, HTMX,
Alpine.js и Tailwind CSS, с чатом поддержки по каждому заказу и админ-панелью.

> Работает на Python 3.11+ (проверено на 3.13). RU/EN i18n, тёмная тема, адаптив.

---

## Возможности

**Витрина**
- Главная с hero-анимациями (parallax, mesh-градиенты, SVG-паттерн мастей), фичерингом, преимуществами и слайдером новостей.
- Каталог: фильтры (категория, цена, бренд, редкость, наличие), сортировка, поиск, пагинация.
- Карточка товара: галерея, характеристики, похожие колоды, добавление в корзину и избранное.
- Новости (список + страница), «О магазине», FAQ-аккордеон, форма поддержки, кастомная 404.
- Корзина на сервере с HTMX-обновлениями, checkout с валидацией и созданием заказа.

**Профиль и заказы**
- Редактирование данных, история заказов со статусами, избранное, обращения в поддержку, список чатов.
- Статусы заказа: `pending`, `paid`, `processing`, `shipped`, `delivered`, `cancelled`.

**Чат по заказу (realtime)**
- Чат 1:1 создаётся автоматически вместе с заказом и сразу получает системное сообщение.
- WebSocket `/ws/chat/{chat_id}` с проверкой прав + fallback на HTMX-поллинг (3 с).
- Инфоблок статуса, индикаторы непрочитанных в хедере (покупатель) и в сайдбаре (админ).
- Смена статуса админом автоматически пишет системное сообщение в чат.
- Rate-limit: 1 сообщение в 2 секунды, лимит длины 2000 символов.

**Админ-панель `/admin`**
- KPI-карточки, график заказов и выручки по дням (Chart.js), последние заказы, открытые чаты, регистрации.
- Заказы: фильтры, смена статуса, экспорт CSV. Товары: CRUD, soft delete, bulk вкл/выкл, загрузка изображений.
- Новости: CRUD, публикация/черновик, slug, обложка. Категории, пользователи (бан, выдача прав), чаты, настройки.
- Audit log всех действий администратора.

**Дополнительно (сверх ТЗ)**
- Wishlist (избранное) с индикатором в хедере.
- Cookie-баннер с сохранением согласия в `localStorage`.
- Тосты (flash-сообщения) и skeleton-загрузка.
- SEO: `sitemap.xml`, `robots.txt`, meta/OG-теги, JSON-LD `Product`.
- Health-check `/healthz`, i18n RU/EN через Babel.

---

## Стек

| Слой | Технологии |
| --- | --- |
| Backend | FastAPI, Uvicorn, Pydantic v2, SQLAlchemy 2.0 (async), Alembic |
| БД | SQLite (dev) → PostgreSQL через `DATABASE_URL` |
| Фронтенд | Jinja2, HTMX, Alpine.js (CSP-сборка), Tailwind CSS (CLI) |
| Realtime | нативные WebSocket FastAPI + HTMX-поллинг |
| Auth | `itsdangerous` (signed httpOnly cookie) + `passlib[bcrypt]` |
| i18n | Babel / gettext (`.mo`), RU + EN |
| Защита | slowapi, CSP/security-заголовки, CSRF double-submit |
| Тесты | pytest, pytest-asyncio, httpx, Playwright (e2e) |
| Качество | ruff, mypy, pip-audit |

---

## Быстрый старт

```bash
# 1. Зависимости и виртуальное окружение (нужен uv: https://astral.sh/uv)
make venv
make install

# 2. Конфигурация
cp .env.example .env
# отредактируйте SECRET_KEY, ADMIN_PASSWORD и ADMIN_EMAIL

# 3. Схема БД + демо-данные + админ
make migrate        # alembic upgrade head
make seed           # категории, товары, новости, админ
# либо, если миграции не нужны: make create-admin

# 4. Запуск
make dev            # http://localhost:8000
```

Проверка: `http://localhost:8000/healthz` → `{"status": "ok"}`.

### Дефолтный администратор

Админ создаётся автоматически при первом запуске из переменных окружения
(`ADMIN_EMAIL`, `ADMIN_PASSWORD`), а также командой:

```bash
make create-admin   # идемпотентно: создаёт или сбрасывает пароль
```

Вход: `/login` → email из `ADMIN_EMAIL`, пароль из `ADMIN_PASSWORD`.
**Смените `ADMIN_PASSWORD` и `SECRET_KEY` перед любым деплоем.**

---

## Команды

```bash
make help           # список всех целей
make dev            # dev-сервер с autoreload на :8000
make migrate        # alembic upgrade head
make migration m="add wishlist"   # автогенерация миграции
make seed           # демо-каталог + новости + админ
make create-admin   # создать/сбросить админа из .env
make test           # pytest (unit + integration)
make e2e-install    # скачать Chromium для Playwright
make e2e            # Playwright-сценарий покупки и чата
make lint           # ruff check
make fmt            # ruff check --fix && ruff format
make type           # mypy
make audit          # pip-audit
make css            # сборка Tailwind (minify)
make css-watch      # сборка Tailwind в watch-режиме
make check          # lint + type + test
```

---

## Структура

```
app/
├── main.py            # фабрика приложения, middleware, роутеры
├── config.py          # настройки из окружения (pydantic-settings)
├── deps.py            # зависимости FastAPI: сессия, пользователь, CSRF, i18n
├── middleware.py      # security-заголовки, локаль, CSRF-cookie, логирование
├── security.py        # сессии (itsdangerous), хеши паролей, CSRF-токены
├── flash.py           # flash-сообщения в cookie (base64url)
├── templating.py      # Jinja2-окружение, фильтры, общий контекст
├── db/                # engine, session, base, sqlite (Unicode lower/like)
├── models/            # user, product, category, news, order, chat, wishlist, support, audit
├── schemas/           # Pydantic-схемы ввода/вывода
├── routers/           # публичные страницы, auth, профиль, корзина, checkout, chat, admin/*
├── services/          # бизнес-логика: auth, products, orders, chat, news, stats
├── ws/                # менеджер WebSocket-подключений чата
├── scripts/           # seed, create_admin, build_i18n
├── templates/         # base, partials, pages, admin/, chat/
├── static/            # css, js, img, uploads, vendor (htmx/alpine/chart/motion)
└── i18n/              # ru/, en/ (.po + .mo)
alembic/               # миграции
tests/                 # unit/integration + tests/e2e (Playwright)
```

---

## Переменные окружения

| Переменная | Назначение | По умолчанию |
| --- | --- | --- |
| `ENV` | окружение (`dev`/`prod`), влияет на Secure-cookie и HSTS | `dev` |
| `DEBUG` | включает `/api/docs` и подробные логи | `true` |
| `SECRET_KEY` | ключ подписи сессий (≥ 16 символов) | dev-заглушка |
| `DATABASE_URL` | строка подключения SQLAlchemy | SQLite в `data/` |
| `COOKIE_SECURE` | `Secure`-флаг сессионной cookie (в проде — `true`) | `false` |
| `ADMIN_LOGIN` / `ADMIN_PASSWORD` / `ADMIN_EMAIL` | дефолтный админ | см. `.env.example` |
| `DEFAULT_LOCALE` / `SUPPORTED_LOCALES` | язык по умолчанию и список | `ru` / `ru,en` |
| `CURRENCY`, `SUPPORT_EMAIL` | валюта и контакт поддержки | `RUB`, `support@…` |
| `MAX_UPLOAD_SIZE`, `ALLOWED_IMAGE_TYPES` | лимиты загрузки изображений | 5 МБ, jpeg/png/webp/gif |

---

## i18n

Строки живут в `app/i18n/<locale>/LC_MESSAGES/messages.po`, компилируются в `.mo`:

```bash
.venv/bin/python -m app.scripts.build_i18n
```

Шаблоны используют `{{ t('key') }}`. Язык выбирается по `?lang=`, cookie `rc_lang`,
профилю пользователя или значению по умолчанию.

---

## Тестирование

```bash
make test    # auth, каталог, корзина/checkout, чат, доступы, CSRF, заголовки
make e2e     # покупка + чат с админом, рендер страниц, бургер, i18n
```

Покрыто: регистрация/логин/логаут, дубликаты email, CSRF на POST, 403 для `/admin` без роли,
автосоздание чата с системным сообщением, rate-limit чата, запрет доступа к чужому чату,
системное сообщение при смене статуса, ответ админа, поиск по кириллице, security-заголовки.

---

## Безопасность

Кратко: bcrypt (cost 12), подписанные httpOnly-cookie, CSRF double-submit, ORM-only запросы,
slowapi rate-limit на `/login`, `/register` и чат, CSP и hardening-заголовки, проверка MIME и
размера загрузок, audit log, `/admin/*` под `require_admin`.
Полный отчёт — в [SECURITY.md](SECURITY.md).

---

## Лицензия

Демонстрационный проект. Изображения и товары — вымышленные.
