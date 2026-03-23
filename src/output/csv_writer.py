"""CSV-вывод списка Pydantic-сущностей (разделитель — табуляция)."""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

from pydantic import BaseModel

# Разделитель для multi-value полей
_MULTI_SEP = "; "


def _flatten(d: dict[str, Any], prefix: str = "", sep: str = "_") -> dict[str, str]:
    """Рекурсивно развернуть вложенные словари в плоскую структуру.

    Вложенные dict разворачиваются (contacts.phone → contacts_phone).
    Списки объединяются через «; ».
    None заменяется пустой строкой.
    """
    result: dict[str, str] = {}
    for key, value in d.items():
        full_key = f"{prefix}{sep}{key}" if prefix else key
        if isinstance(value, dict):
            result.update(_flatten(value, full_key, sep))
        elif isinstance(value, list):
            result[full_key] = _MULTI_SEP.join(str(v) for v in value)
        elif value is None:
            result[full_key] = ""
        else:
            result[full_key] = str(value)
    return result


def save_csv(
    entities: list[BaseModel],
    path: Path,
    fieldnames: list[str] | None = None,
) -> None:
    """Сохранить список сущностей в TSV-файл (разделитель — табуляция).

    Вложенные модели (contacts, geo и т.п.) разворачиваются в плоскую структуру:
    поле `contacts.phone` становится столбцом `contacts_phone`.
    Multi-value поля (списки) объединяются через «; ».

    Args:
        entities: Список Pydantic-моделей для сохранения.
        path: Путь к выходному файлу (обычно *.tsv).
        fieldnames: Порядок столбцов. Если None — определяется из первой записи.
    """
    if not entities:
        return

    rows = [_flatten(e.model_dump(mode="json")) for e in entities]

    if fieldnames is None:
        fieldnames = list(rows[0].keys())

    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f, fieldnames=fieldnames, delimiter="\t", extrasaction="ignore"
        )
        writer.writeheader()
        writer.writerows(rows)
