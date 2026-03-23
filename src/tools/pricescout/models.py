"""Модели данных PriceScout — прайс-листы с CRM-сервисов."""

from __future__ import annotations

from pydantic import BaseModel

from src.core.models import ScrapedEntity


class ServicePrice(BaseModel):
    """Одна услуга из прайс-листа.

    Если точная цена — заполнен price. Если диапазон — price_from/price_to.
    """

    name: str
    price: int | None = None          # точная цена в рублях
    price_from: int | None = None     # нижняя граница ("от X")
    price_to: int | None = None       # верхняя граница ("до X")
    duration: str | None = None       # "60 мин", "1 ч 30 мин"
    category: str | None = None       # "Маникюр", "Педикюр"


class PriceList(ScrapedEntity):
    """Прайс-лист организации, собранный с CRM-сервиса.

    Наследует от ScrapedEntity: source, source_url, scraped_at.
    """

    org_name: str
    services: list[ServicePrice] = []
    currency: str = "RUB"
    fetched_from: str                 # URL откуда взят прайс
