"""Модели данных JobScout — вакансии с job-платформ."""

from __future__ import annotations

from src.core.models import ScrapedEntity


class Vacancy(ScrapedEntity):
    """Вакансия, собранная с job-платформы.

    Наследует от ScrapedEntity: source, source_url, scraped_at.
    Все поля (кроме title) опциональны — степень заполнения
    зависит от источника.
    """

    title: str
    company_name: str | None = None
    company_url: str | None = None
    salary_from: int | None = None
    salary_to: int | None = None
    salary_currency: str | None = None    # RUR, USD, EUR
    city: str | None = None
    address: str | None = None
    description: str | None = None        # обязанности / описание
    requirements: str | None = None       # требования
    published_at: str | None = None       # ISO-дата публикации
    experience: str | None = None         # "Нет опыта", "1–3 года" и т.п.
    employment: str | None = None         # "Полная занятость", "Частичная"
    schedule: str | None = None           # "Полный день", "Гибкий график"
