"""JSON-вывод списка Pydantic-сущностей."""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel


def save_json(
    entities: list[BaseModel],
    path: Path,
    pretty: bool = True,
) -> None:
    """Сохранить список Pydantic-моделей в JSON-файл.

    Args:
        entities: Список сущностей для сохранения (любые Pydantic BaseModel).
        path: Путь к выходному файлу.
        pretty: Форматировать JSON с отступами (по умолчанию True).
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    data = [e.model_dump(mode="json") for e in entities]
    indent = 2 if pretty else None
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=indent)
