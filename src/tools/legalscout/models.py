"""Модели данных LegalScout — юридическая информация об организациях."""

from __future__ import annotations

from src.core.models import ScrapedEntity


class LegalEntity(ScrapedEntity):
    """Юридическая информация об организации.

    Наследует от ScrapedEntity: source, source_url, scraped_at.
    """

    name: str                              # полное наименование юрлица
    short_name: str | None = None
    inn: str                               # ИНН (уникальный идентификатор)
    ogrn: str | None = None
    registration_date: str | None = None
    address: str | None = None
    director: str | None = None
    founders: list[str] = []
    status: str | None = None             # "действующее", "ликвидировано"
    main_activity: str | None = None      # основной ОКВЭД и описание
    authorized_capital: int | None = None
    employee_count: str | None = None     # диапазон (например "до 15 человек")
