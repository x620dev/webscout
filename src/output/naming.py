"""Автоименование выходных файлов с транслитерацией кириллицы."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path

# Таблица транслитерации кириллицы в латиницу (упрощённый ГОСТ)
_TRANSLIT: dict[str, str] = {
    "а": "a",  "б": "b",  "в": "v",  "г": "g",  "д": "d",
    "е": "e",  "ё": "yo", "ж": "zh", "з": "z",  "и": "i",
    "й": "y",  "к": "k",  "л": "l",  "м": "m",  "н": "n",
    "о": "o",  "п": "p",  "р": "r",  "с": "s",  "т": "t",
    "у": "u",  "ф": "f",  "х": "kh", "ц": "ts", "ч": "ch",
    "ш": "sh", "щ": "shch","ъ": "",   "ы": "y",  "ь": "",
    "э": "e",  "ю": "yu", "я": "ya",
}

_FMT_DIR = {"json": "json", "csv": "csv", "ai-summary": "ai"}
_FMT_EXT = {"json": ".json", "csv": ".tsv", "ai-summary": ".md"}


def transliterate(text: str) -> str:
    """Транслитерировать кириллицу в латиницу.

    Некириллические символы передаются без изменений.

    Examples:
        >>> transliterate("Уфа")
        'ufa'
        >>> transliterate("маникюр")
        'manikyur'
    """
    result = []
    for char in text.lower():
        result.append(_TRANSLIT.get(char, char))
    return "".join(result)


def slugify(text: str) -> str:
    """Преобразовать строку в безопасный slug для имени файла.

    Транслитерирует кириллицу, заменяет все небуквенные символы на «_».

    Examples:
        >>> slugify("Уфа")
        'ufa'
        >>> slugify("маникюр и педикюр")
        'manikyur_i_pedikyur'
    """
    translit = transliterate(text)
    return re.sub(r"[^\w]", "_", translit).strip("_")


def named_path(name: str, fmt: str = "json") -> Path:
    """Разрешить путь к файлу по имени и формату.

    Директория определяется автоматически:
    - json       → data/json/
    - csv        → data/csv/
    - ai-summary → data/ai/

    Если расширение не указано, добавляется соответствующее формату.

    Examples:
        >>> named_path("result", "json")
        PosixPath('data/json/result.json')
        >>> named_path("result.json", "json")
        PosixPath('data/json/result.json')
        >>> named_path("report", "ai-summary")
        PosixPath('data/ai/report.md')
    """
    dir_name = _FMT_DIR.get(fmt, "json")
    ext = _FMT_EXT.get(fmt, ".json")
    # Используем только имя файла — без директории (на случай если передан полный путь)
    p = Path(Path(name).name)
    if not p.suffix:
        p = p.with_suffix(ext)
    return Path("data") / dir_name / p


def auto_path(
    tool: str,
    city: str,
    query: str,
    fmt: str = "json",
) -> Path:
    """Сгенерировать путь к выходному файлу по стандартному шаблону WebScout.

    Шаблон: ``data/{dir}/{datetime}_{tool}_{city}_{query}{ext}``

    Args:
        tool: Название инструмента (orgscout, jobscout, ...).
        city: Город (транслитерируется).
        query: Поисковый запрос (транслитерируется).
        fmt: Формат вывода: ``json``, ``csv`` или ``ai-summary``.

    Returns:
        Path к файлу вывода.

    Examples:
        >>> auto_path("orgscout", "Уфа", "маникюр")
        PosixPath('data/json/20260323_1430_orgscout_ufa_manikyur.json')
    """
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M")
    city_slug = slugify(city)
    query_slug = slugify(query)

    dir_name = _FMT_DIR.get(fmt, "json")
    ext = _FMT_EXT.get(fmt, ".json")

    filename = f"{ts}_{tool}_{city_slug}_{query_slug}{ext}"
    return Path("data") / dir_name / filename
