"""Модели данных OrgScout — организации с картографических сервисов."""

from __future__ import annotations

from pydantic import Field

from src.core.models import Contacts, GeoPoint, ScrapedEntity


class Organization(ScrapedEntity):
    """Организация, собранная с картографического сервиса.

    Наследует от ScrapedEntity: source, source_url, scraped_at.
    Все поля (кроме name и address) опциональны — степень заполнения
    зависит от источника.
    """

    name: str
    type: str | None = None                 # студия, салон, сеть, клиника
    address: str | list[str] = ""
    geo: GeoPoint | None = None
    contacts: Contacts = Field(default_factory=Contacts)
    working_hours: str | None = None
    rating: float | None = None
    reviews_count: int | None = None
    categories: list[str] = []
    services: list[str] = []
    online_booking: str | None = None       # URL CRM (YCLIENTS, Dikidi...)
    photos: list[str] = []
    notes: str | None = None
