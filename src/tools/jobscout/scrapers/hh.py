"""Скрапер hh.ru — публичный REST API v1, без Playwright."""

from __future__ import annotations

import logging
from typing import Any

from src.core.config import HttpConfig, ProxyConfig
from src.core.http_client import HttpClient
from src.tools.jobscout.models import Vacancy

logger = logging.getLogger(__name__)

_VACANCIES_URL = "https://api.hh.ru/vacancies"

# Маппинг русских названий городов в ID регионов hh.ru
_HH_AREAS: dict[str, int] = {
    "москва": 1,
    "санкт-петербург": 2,
    "питер": 2,
    "екатеринбург": 3,
    "новосибирск": 4,
    "нижний новгород": 66,
    "казань": 88,
    "уфа": 99,
    "самара": 78,
    "ростов-на-дону": 76,
    "краснодар": 53,
    "омск": 68,
    "челябинск": 104,
    "пермь": 72,
    "красноярск": 54,
    "воронеж": 26,
    "волгоград": 24,
    "тюмень": 1438,
    "барнаул": 1279,
    "саратов": 80,
    "ижевск": 40,
    "ульяновск": 98,
    "иркутск": 38,
    "хабаровск": 1985,
    "ярославль": 112,
    "владивосток": 22,
    "тольятти": 95,
    "набережные челны": 63,
    "кемерово": 46,
    "оренбург": 70,
    "рязань": 77,
    "пенза": 73,
    "липецк": 57,
    "киров": 48,
    "чебоксары": 21,
    "тула": 96,
    "астрахань": 5,
    "калуга": 45,
    "брянск": 15,
    "курск": 55,
    "белгород": 12,
    "владимир": 23,
    "тверь": 93,
    "иваново": 37,
    "сочи": 1057,
}

# Максимально разрешённое число результатов за один запрос
_HH_MAX_PER_PAGE = 100


def get_area_id(city: str) -> int | None:
    """Получить ID региона hh.ru по русскому названию города."""
    return _HH_AREAS.get(city.lower().strip())


def parse_vacancy(item: dict[str, Any]) -> Vacancy:
    """Распарсить один элемент из ответа API hh.ru в объект Vacancy.

    Функция вынесена на уровень модуля для удобства тестирования
    без реальных HTTP-запросов.
    """
    salary = item.get("salary") or {}
    employer = item.get("employer") or {}
    area = item.get("area") or {}
    address_data = item.get("address") or {}
    snippet = item.get("snippet") or {}
    experience = item.get("experience") or {}
    employment = item.get("employment") or {}
    schedule = item.get("schedule") or {}

    return Vacancy(
        source="hh",
        source_url=item.get("alternate_url", ""),
        title=item.get("name", ""),
        company_name=employer.get("name"),
        company_url=employer.get("alternate_url") or employer.get("url"),
        salary_from=salary.get("from"),
        salary_to=salary.get("to"),
        salary_currency=salary.get("currency"),
        city=area.get("name"),
        address=address_data.get("raw") or address_data.get("city"),
        description=snippet.get("responsibility"),
        requirements=snippet.get("requirement"),
        published_at=item.get("published_at"),
        experience=experience.get("name"),
        employment=employment.get("name"),
        schedule=schedule.get("name"),
    )


class HhScraper:
    """Скрапер вакансий с hh.ru через публичный REST API.

    Не использует Playwright — работает через httpx.
    Поддерживает пагинацию и rate limiting.

    Использование:
        scraper = HhScraper(cfg.http, cfg.proxy)
        vacancies = await scraper.search("мастер маникюра", "Уфа", max_results=50)
    """

    def __init__(
        self,
        config: HttpConfig | None = None,
        proxy: ProxyConfig | None = None,
    ) -> None:
        self._config = config
        self._proxy = proxy

    async def search(
        self,
        query: str,
        city: str,
        max_results: int = 50,
    ) -> list[Vacancy]:
        """Поиск вакансий на hh.ru.

        Args:
            query: Поисковый запрос (название вакансии или компании).
            city: Название города на русском языке.
            max_results: Максимальное число возвращаемых вакансий.

        Returns:
            Список объектов Vacancy.
        """
        area_id = get_area_id(city)
        if area_id is None:
            logger.warning("Неизвестный город: %r, поиск без фильтра по региону", city)

        vacancies: list[Vacancy] = []
        page = 0

        async with HttpClient(self._config, self._proxy) as client:
            while len(vacancies) < max_results:
                per_page = min(_HH_MAX_PER_PAGE, max_results - len(vacancies))
                params: dict[str, Any] = {
                    "text": query,
                    "per_page": per_page,
                    "page": page,
                }
                if area_id is not None:
                    params["area"] = area_id

                logger.debug("hh.ru API: page=%d, query=%r, area=%s", page, query, area_id)

                try:
                    data = await client.get_json(_VACANCIES_URL, params=params)
                except Exception as exc:
                    logger.error("Ошибка запроса hh.ru: %s", exc)
                    break

                items = data.get("items", [])
                if not items:
                    break

                for item in items:
                    vacancies.append(parse_vacancy(item))
                    if len(vacancies) >= max_results:
                        break

                total_pages = data.get("pages", 1)
                page += 1
                if page >= total_pages:
                    break

        return vacancies
