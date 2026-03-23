"""Утилиты для частичного сохранения результатов и режима --append."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from pydantic import BaseModel

logger = logging.getLogger(__name__)


def load_existing(path: Path) -> list[dict[str, Any]]:
    """Загрузить существующий JSON-файл для режима --append.

    Args:
        path: Путь к файлу с предыдущими результатами.

    Returns:
        Список записей из файла, или пустой список если файл не найден/некорректен.
    """
    if not path.exists():
        logger.debug("Файл %s не найден, начинаем с пустого списка.", path)
        return []
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list):
            logger.info("Загружено %d записей из %s для дозапуска.", len(data), path)
            return data
        logger.warning("Файл %s содержит не список — игнорируем.", path)
        return []
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("Ошибка загрузки %s: %s. Начинаем с пустого списка.", path, exc)
        return []


def get_seen_urls(entities: list[dict[str, Any]]) -> set[str]:
    """Извлечь множество source_url из существующих записей.

    Используется для пропуска уже собранных URL при дозапуске (--append).

    Args:
        entities: Список словарей с полем source_url.

    Returns:
        Множество source_url строк.
    """
    return {e["source_url"] for e in entities if e.get("source_url")}


def save_partial(
    entities: list[BaseModel | dict[str, Any]],
    path: Path,
    total: int,
    pretty: bool = True,
) -> None:
    """Сохранить частичные результаты (при прерывании или ошибке).

    Выводит в stdout сообщение о количестве собранных записей.

    Args:
        entities: Список Pydantic-моделей или словарей.
        path: Путь для сохранения.
        total: Ожидаемое общее число записей (для сообщения).
        pretty: Форматировать JSON с отступами.
    """
    path.parent.mkdir(parents=True, exist_ok=True)

    data: list[Any] = []
    for e in entities:
        if isinstance(e, BaseModel):
            data.append(e.model_dump(mode="json"))
        elif isinstance(e, dict):
            data.append(e)
        else:
            data.append(str(e))

    indent = 2 if pretty else None
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=indent)

    print(
        f"\nСобрано {len(data)} из {total}. Результат сохранён в {path}",
        flush=True,
    )
