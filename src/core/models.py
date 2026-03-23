"""Базовые Pydantic-модели данных — используются всеми инструментами WebScout."""

from __future__ import annotations

from datetime import datetime, timezone

from pydantic import BaseModel, Field


class Contacts(BaseModel):
    """Контактные данные организации или сущности."""

    phone: list[str] = []
    email: str | None = None
    website: str | None = None
    telegram: str | None = None
    instagram: str | None = None
    vk: str | None = None
    whatsapp: str | None = None


class GeoPoint(BaseModel):
    """Географическая координата."""

    lat: float
    lon: float


class ScrapedEntity(BaseModel):
    """Базовый класс для всех собираемых сущностей.

    Каждый инструмент определяет свою модель, наследуя от ScrapedEntity.
    Общие поля: источник данных, исходный URL, время сбора.
    """

    source: str               # yandex_maps, hh, flamp, egrul, ...
    source_url: str
    scraped_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
