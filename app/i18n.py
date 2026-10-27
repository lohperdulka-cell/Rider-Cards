"""Translation layer.

The RU/EN catalogue lives in :mod:`app.i18n_catalog` as plain Python so the UI never
depends on compiled ``.mo`` files. ``scripts/build_i18n.py`` exports the same catalogue
to ``.po``/``.mo`` for external translators, and any compiled catalogue found on disk is
merged on top so translations can be updated without a code change.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Any

from app.config import LOCALES_DIR, settings
from app.i18n_en import EN
from app.i18n_ru import RU

DEFAULT_LOCALE = settings.default_locale
SUPPORTED_LOCALES = settings.locales

CATALOG: dict[str, dict[str, str]] = {"ru": RU, "en": EN}
FALLBACK = CATALOG


@lru_cache(maxsize=8)
def _catalog(locale: str) -> dict[str, str]:
    data: dict[str, str] = dict(CATALOG.get(DEFAULT_LOCALE, {}))
    data.update(CATALOG.get(locale, {}))
    mo_path = LOCALES_DIR / locale / "LC_MESSAGES" / "messages.mo"
    if mo_path.exists():
        try:
            from babel.support import Translations

            with mo_path.open("rb") as fh:
                translations = Translations(fp=fh)
            for key in list(data.keys()):
                message = translations.gettext(key)
                if message:
                    data[key] = message
        except Exception:  # pragma: no cover - a corrupt .mo must not break the app
            pass
    return data


def normalize_locale(value: str | None) -> str:
    if value and value in SUPPORTED_LOCALES:
        return value
    return DEFAULT_LOCALE


def gettext_for(locale: str):
    catalog = _catalog(normalize_locale(locale))

    def _(message: str, **kwargs: Any) -> str:
        template = catalog.get(message, message)
        if kwargs:
            try:
                return template.format(**kwargs)
            except (KeyError, IndexError):
                return template
        return template

    return _


def translate(locale: str, key: str, **kwargs: Any) -> str:
    return gettext_for(locale)(key, **kwargs)


LOCALE_LABELS = {"ru": "RU", "en": "EN"}
