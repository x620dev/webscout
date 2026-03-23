"""Вывод списка сущностей в компактном формате для LLM-контекста (ai-summary)."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import BaseModel

# Поля, которые не выводятся в summary (служебные)
_SKIP_FIELDS = {"scraped_at", "photos", "source_url"}


def format_ai_summary(
    entities: list[BaseModel],
    query: str | None = None,
    city: str | None = None,
    source: str | None = None,
) -> str:
    """Форматировать список сущностей в компактный текст для AI-ассистента.

    Формат максимально плотный (мало токенов) и при этом читаемый —
    пригоден для передачи в контекст LLM без дополнительной обработки.

    Args:
        entities: Список Pydantic-моделей.
        query: Поисковый запрос (для заголовка).
        city: Город (для заголовка).
        source: Источник данных (для заголовка).

    Returns:
        Строка в Markdown-подобном формате.
    """
    lines: list[str] = []

    # Заголовок
    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    src_label = source or (
        getattr(entities[0], "source", "—") if entities else "—"
    )
    query_label = f'"{query}"' if query else "—"
    city_label = f" в {city}" if city else ""
    lines.append(
        f"# Результаты: {query_label}{city_label} | "
        f"Источник: {src_label} | "
        f"Найдено: {len(entities)} | "
        f"{date_str}"
    )
    lines.append("")

    for i, entity in enumerate(entities, 1):
        lines.extend(_format_entity(i, entity))
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def _format_entity(index: int, entity: BaseModel) -> list[str]:
    """Форматировать одну сущность в список строк."""
    lines: list[str] = []
    data = entity.model_dump(mode="json")

    # Заголовок: номер + name/title/source_url
    name = (
        data.get("name")
        or data.get("title")
        or data.get("source_url", f"Запись {index}")
    )
    # Рейтинг и отзывы в заголовке (если есть)
    rating_str = f" ★{data['rating']}" if data.get("rating") is not None else ""
    reviews_str = f" ({data['reviews_count']} отз.)" if data.get("reviews_count") else ""
    lines.append(f"## {index}. {name}{rating_str}{reviews_str}")

    # Остальные поля
    for key, value in data.items():
        if key in _SKIP_FIELDS or key in {"name", "title", "rating", "reviews_count"}:
            continue
        if value is None or value == "" or value == []:
            continue

        if isinstance(value, dict):
            # Вложенный объект — выводим непустые поля в одну строку
            parts = _format_dict_inline(value)
            if parts:
                lines.append(f"{key}: {' | '.join(parts)}")
        elif isinstance(value, list):
            lines.append(f"{key}: {'; '.join(str(v) for v in value)}")
        else:
            lines.append(f"{key}: {value}")

    # Ссылка всегда последней
    source_url = data.get("source_url", "")
    if source_url:
        lines.append(f"→ {source_url}")

    lines.append("---")
    return lines


def _format_dict_inline(d: dict[str, Any]) -> list[str]:
    """Форматировать словарь как список непустых пар ключ: значение."""
    parts = []
    for k, v in d.items():
        if v is None or v == "" or v == []:
            continue
        if isinstance(v, list):
            parts.append(f"{k}: {', '.join(str(x) for x in v)}")
        else:
            parts.append(f"{k}: {v}")
    return parts


def save_ai_summary(
    entities: list[BaseModel],
    path: Path,
    query: str | None = None,
    city: str | None = None,
    source: str | None = None,
) -> None:
    """Сохранить AI-summary в текстовый файл.

    Args:
        entities: Список Pydantic-моделей.
        path: Путь к выходному файлу.
        query: Поисковый запрос.
        city: Город.
        source: Источник данных.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    content = format_ai_summary(entities, query=query, city=city, source=source)
    path.write_text(content, encoding="utf-8")
