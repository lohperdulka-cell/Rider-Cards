# Security-отчёт RiderCards

Отчёт по требованиям раздела 11 ТЗ. Статус — что реализовано, где находится в коде,
чем подтверждено.

| № | Требование | Статус | Реализация | Подтверждение |
| --- | --- | --- | --- | --- |
| 11.1 | bcrypt, cost ≥ 12 | ✅ | `app/security.py` — `CryptContext(schemes=["bcrypt"], bcrypt__rounds=settings.bcrypt_rounds)` | `tests/test_auth.py` |
| 11.2 | Signed httpOnly + Secure + SameSite=Lax сессии | ✅ | `app/security.py` (`URLSafeTimedSerializer`, `session_cookie_name`), `app/routers/auth.py` (`_set_session`) | `tests/test_auth.py` |
| 11.3 | CSRF на все POST (double-submit cookie) | ✅ | `app/middleware.py` (выдача `rc_csrf`), `app/deps.py::CsrfDep` | `tests/test_auth.py::test_post_without_csrf_token_is_rejected` |
| 11.4 | Pydantic-валидация + Jinja2 autoescape | ✅ | `app/schemas/*`, `app/templating.py` (`autoescape=True`) | `tests/test_catalog.py::test_catalog_html_is_escaped` |
| 11.5 | Только ORM, без склейки raw SQL | ✅ | SQLAlchemy 2.0 `select()` во всех сервисах; параметризованные `text()` только в агрегатах статистики | `ruff` (S608-совместимый стиль), ревью |
| 11.6 | Rate limiting (slowapi) | ✅ | `app/main.py` — `login_submit` 10/min, `register_submit` 5/min, `support_submit` 5/min, `chat_send` 30/min | `tests/test_chat.py::test_rate_limit_blocks_second_message` |
| 11.7 | Middleware: CSP, nosniff, frame, referrer | ✅ | `app/middleware.py::SecurityHeadersMiddleware` (+ HSTS при `ENV=prod`) | `tests/test_catalog.py::test_security_headers_present` |
| 11.8 | WebSocket: auth по cookie, проверка прав на каждый чат | ✅ | `app/ws/chat.py` (`resolve_session`, `chat_service.can_access`) | `tests/test_chat.py::test_user_cannot_read_or_post_to_foreign_chat` |
| 11.9 | `/admin/*` под `require_admin` + audit log | ✅ | `app/deps.py::require_admin`, `app/services/audit.py`, `app/routers/admin/_common.py::log_action` | `tests/test_auth.py::test_admin_area_forbidden_for_regular_user` |
| 11.10 | `.env` в `.gitignore`, секреты только из env | ✅ | `.gitignore`, `app/config.py` (pydantic-settings) | `.gitignore`, `.env.example` |
| 11.11 | Загрузка файлов: MIME, размер, переименование, anti-traversal | ✅ | `app/routers/admin/_common.py::save_upload` | `tests/test_admin.py` (MIME, размер, traversal, переименование) |
| 11.12 | `pip-audit` | ✅ | `make audit` | `pip-audit`: *No known vulnerabilities found* |
| 11.13 | Итоговый отчёт | ✅ | этот файл | — |

## Что усилено сверх ТЗ

- **CSP ужесточён**: `script-src 'self'` без `unsafe-inline` и без внешних CDN.
  Все инлайновые обработчики (`onclick`, `onsubmit`) заменены на `data-*`-атрибуты,
  которые обрабатывает `app/static/js/main.js`. `style-src` сохраняет `'unsafe-inline'`,
  потому что Alpine.js и анимации задают инлайновые `style`-атрибуты.
- **Запрет MIME-sniffing** (`nosniff`) вместе с переименованием файла (`secrets.token_hex`)
  исключает исполнение загруженного файла как скрипта.
- **`frame-ancestors 'none'`** и `X-Frame-Options: DENY` — защита от кликджекинга.
- **Rate-limit чата** двойной: серверный (1 сообщение / 2 с) в `app/services/chat.py`
  и per-IP через slowapi.

## Закрытые дыры (найдены по ходу работы)

1. **Утечка данных через `Content-Length`** — `app/templating.py` дописывал flash-тосты
   в тело ответа, не пересчитывая заголовок, что ломало ответ и мешало корректной отдаче
   HTML. Исправлено: заголовок пересчитывается при изменении тела.
2. **Поиск по кириллице** — SQLite `lower()` работает только с ASCII, поэтому поиск в
   каталоге не находил русские названия. Добавлен `app/db/sqlite.py` с Unicode-версиями
   `lower`/`upper`/`like` (регистрируются на соединении SQLite).
3. **DetachedInstanceError на страницах 403/404** — `get_session` откатывал транзакцию
   на `HTTPException`, из-за чего ORM-пользователь истекал и шаблон ошибки падал.
   Исправлено: rollback не выполняется для `HTTPException`.
4. **Alpine.js CSP-сборка** — инлайновое выражение `window.innerWidth >= 1024` в
   `catalog.html` выбрасывало `TypeError` и ломало панель фильтров. Перенесено в
   компонент `filters` (`matchMedia`).

## Остаточные риски и рекомендации

- **`style-src 'unsafe-inline'`** оставлен осознанно: Alpine.js (`x-show`, `x-transition`)
  и parallax пишут инлайновые стили. Полный отказ потребует nonce и переписывания
  анимаций — вне рамок демо-проекта.
- **`storage_uri="memory://"` у slowapi** не распределяется между воркерами. Для
  многоинстансного деплоя нужно указать Redis (`RATELIMIT_STORAGE_URI`).
- **SQLite в dev** не рассчитан на конкурентную запись. В проде — PostgreSQL
  (`DATABASE_URL=postgresql+asyncpg://…`).
- **`SECRET_KEY` и `ADMIN_PASSWORD` из `.env.example` — заглушки.** Обязательно
  заменить перед деплоем; при `ENV=prod` включается `Secure`-cookie и HSTS.

## Как воспроизвести проверки

```bash
make audit    # pip-audit: уязвимости зависимостей
make lint     # ruff
make type     # mypy
make test     # unit + integration
make e2e      # браузерные сценарии, включая проверку отсутствия CSP-нарушений
```
