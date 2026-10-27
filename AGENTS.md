# AGENTS.md — RiderCards

Премиальный магазин игральных карт: FastAPI + Jinja2 + HTMX + Alpine.js + Tailwind,
чат по заказу на WebSocket, админ-панель. Python 3.13, `uv` + `Makefile`.

## Команды

```bash
make install        # .venv + зависимости (uv pip install -e ".[dev]")
make dev            # uvicorn --reload на :8000
make test           # pytest (unit + integration), 56 тестов
make e2e            # Playwright, 14 тестов (нужен `make e2e-install`)
make lint           # ruff check
make fmt            # ruff check --fix && ruff format
make type           # mypy app
make audit          # pip-audit
make seed           # демо-каталог + новости + админ
make create-admin   # создать/сбросить админа из .env
make css            # сборка Tailwind (minify)
```

Всегда запускайте через `.venv/bin/python -m …` — системный Python не содержит зависимостей.

## Инварианты (не сломать)

- **`get_session` не делает rollback на `HTTPException`.** Иначе ORM-пользователь истекает
  и страницы 403/404 падают с `DetachedInstanceError`.
- **Flash-инъекция в `app/templating.py` обязана пересчитывать `Content-Length`.** Тело
  растёт после рендера; устаревший заголовок ломает ответ на реальном сервере
  (`RuntimeError: Response content longer than Content-Length`). unit-тесты на httpx этого
  не видят — ловится только e2e/живым сервером.
- **Alpine используется в CSP-сборке** (`alpine-csp.min.js`). Инлайновые выражения сложнее
  обращения к свойству или вызова метода не работают: `x-show="open || window.innerWidth >= 1024"`
  падает с `TypeError`. Логику держите в `app/static/js/alpine-components.js`.
- **CSP: `script-src 'self'` без `unsafe-inline`.** Никаких `onclick=`/`onsubmit=` в шаблонах —
  только `data-*`-атрибуты, обработчики в `app/static/js/main.js`. `style-src` пока допускает
  `unsafe-inline` (Alpine `x-show`/`x-transition` и parallax).
- **SQLite `lower()` — только ASCII.** Поиск по кириллице работает благодаря
  `app/db/sqlite.py` (Unicode `lower`/`upper`/`like`, регистрируются на соединении).
- **`save_upload`** принимает `UploadFile | None`; значения из `FormData` прогоняйте через
  `as_upload()` — иначе mypy падает на `UploadFile | str`.
- **ruff ignore**: `B008` (FastAPI `Depends()` в дефолтах), `SIM105`, `UP042`.

## Структура

- `app/routers/` — публичные (`pages`, `auth`, `catalog`, `product`, `cart`, `checkout`,
  `orders`, `chat`, `wishlist`, `profile`) и `admin/*`.
- `app/services/` — вся бизнес-логика; роутеры тонкие.
- `app/ws/chat.py` — WebSocket-менеджер, права проверяются через `chat_service.can_access`.
- `app/i18n_ru.py` / `app/i18n_en.py` — словари строк (плюс `.po`/`.mo` в `app/i18n/`).

## Тесты

- `tests/conftest.py` — изолированная SQLite-БД, `client` (httpx ASGITransport), фикстура
  сброса rate-limit чата. Хелпер `csrf_token(html)` читает `<meta name="csrf-token">`.
- `tests/e2e/conftest.py` — поднимает реальный uvicorn на свободном порту с temp-БД,
  сидирует данные, отдаёт Playwright-страницу.
- Селекторы в e2e: у залогиненного пользователя в бургер-меню есть скрытая кнопка
  выхода — используйте точные селекторы (`form[action='/checkout'] button[type=submit]`),
  а не `button[type=submit]`.

## Git / CI

- Рабочая ветка: `feat/ridercards-app`. `main` не трогать без явной просьбы.
- CI (`.github/workflows/ci.yml`): ruff, mypy, pytest и отдельный Playwright-job.
