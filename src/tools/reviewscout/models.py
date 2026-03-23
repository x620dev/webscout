"""Модели данных ReviewScout — отзывы об организациях."""

from __future__ import annotations

from pydantic import BaseModel

from src.core.models import ScrapedEntity


class Review(BaseModel):
    """Один отзыв об организации."""

    author: str | None = None
    rating: float | None = None       # оценка 1–5
    text: str | None = None
    date: str | None = None           # строка или ISO-дата
    platform: str | None = None       # "yandex", "flamp"


class ReviewSummary(ScrapedEntity):
    """Сводка отзывов организации с одной платформы.

    Наследует от ScrapedEntity: source, source_url, scraped_at.
    """

    org_name: str
    rating: float | None = None       # средний рейтинг
    reviews_count: int | None = None  # общее число отзывов на платформе
    reviews: list[Review] = []        # собранные отзывы (может быть меньше reviews_count)
