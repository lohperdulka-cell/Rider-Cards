"""Export the Python translation catalogue to gettext ``.po``/``.mo`` files.

Usage: ``python -m app.scripts.build_i18n``.

The runtime does not require compiled catalogues (``app.i18n`` reads the Python
dictionaries directly), but ``.po`` files are handy for external translators and
``.mo`` files are merged on top of the Python catalogue when present.
"""

from __future__ import annotations

from pathlib import Path

from app.config import LOCALES_DIR
from app.i18n_en import EN
from app.i18n_ru import RU

CATALOGUES = {"ru": RU, "en": EN}

PO_HEADER = """\
msgid ""
msgstr ""
"Project-Id-Version: RiderCards 0.1.0\\n"
"Content-Type: text/plain; charset=UTF-8\\n"
"Content-Transfer-Encoding: 8bit\\n"
"Language: {locale}\\n"
"MIME-Version: 1.0\\n"
"""


def _escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


def write_po(locale: str, catalogue: dict[str, str]) -> Path:
    target_dir = LOCALES_DIR / locale / "LC_MESSAGES"
    target_dir.mkdir(parents=True, exist_ok=True)
    path = target_dir / "messages.po"

    lines = [PO_HEADER.format(locale=locale)]
    for key in sorted(catalogue):
        lines.append(f'msgid "{_escape(key)}"')
        lines.append(f'msgstr "{_escape(catalogue[key])}"')
        lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def write_mo(locale: str, catalogue: dict[str, str]) -> Path:
    """Compile a minimal ``.mo`` binary (big-endian, single plural form).

    The mandatory metadata entry (empty ``msgid``) declares UTF-8, otherwise
    ``gettext`` falls back to ASCII and fails on Cyrillic text.
    """
    import struct

    header = (
        "Project-Id-Version: RiderCards 0.1.0\n"
        "Content-Type: text/plain; charset=UTF-8\n"
        "Content-Transfer-Encoding: 8bit\n"
        f"Language: {locale}\n"
        "MIME-Version: 1.0\n"
    )
    messages: dict[str, str] = {"": header}
    messages.update({key: value for key, value in catalogue.items() if value and key})
    keys = sorted(messages)
    ids = b""
    strs = b""
    entries: list[tuple[int, int, int, int]] = []
    for key in keys:
        msgid = key.encode("utf-8")
        msgstr = messages[key].encode("utf-8")
        entries.append((len(msgid), len(ids), len(msgstr), len(strs)))
        ids += msgid + b"\x00"
        strs += msgstr + b"\x00"

    ids_start = 7 * 4 + len(entries) * 8 * 2
    strs_start = ids_start + len(ids)

    output = struct.pack("Iiiiiii", 0x950412DE, 0, len(entries), 7 * 4, 7 * 4 + len(entries) * 8, 0, 0)
    for msgid_len, msgid_off, _msgstr_len, _msgstr_off in entries:
        output += struct.pack("II", msgid_len, ids_start + msgid_off)
    for _msgid_len, _msgid_off, msgstr_len, msgstr_off in entries:
        output += struct.pack("II", msgstr_len, strs_start + msgstr_off)
    output += ids + strs

    target_dir = LOCALES_DIR / locale / "LC_MESSAGES"
    target_dir.mkdir(parents=True, exist_ok=True)
    path = target_dir / "messages.mo"
    path.write_bytes(output)
    return path


def main() -> None:
    for locale, catalogue in CATALOGUES.items():
        po_path = write_po(locale, catalogue)
        mo_path = write_mo(locale, catalogue)
        print(f"{locale}: {len(catalogue)} entries -> {po_path.name}, {mo_path.name}")


if __name__ == "__main__":
    main()
