"""Скрапер ЕГРЮЛ (nalog.ru) — поиск юрлиц по названию или ИНН, HTTP API.

Алгоритм (двухшаговый):
1. POST /  с query+region → получить токен ``t``
2. GET /search.json  с query+region+t → получить строки результатов

Не требует Playwright — работает через httpx напрямую.
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

from src.core.anti_detect import get_random_user_agent
from src.core.config import HttpConfig, ProxyConfig
from src.tools.legalscout.models import LegalEntity

logger = logging.getLogger(__name__)

_EGRUL_BASE = "https://egrul.nalog.ru"
_TOKEN_URL = f"{_EGRUL_BASE}/"
_SEARCH_URL = f"{_EGRUL_BASE}/search.json"

# Маппинг города/региона в код региона nalog.ru (2-значный ОКАТО-код субъекта)
_CITY_TO_REGION: dict[str, str] = {
    "москва": "77",
    "санкт-петербург": "78",
    "питер": "78",
    "уфа": "02",
    "казань": "16",
    "нижний новгород": "52",
    "екатеринбург": "66",
    "новосибирск": "54",
    "самара": "63",
    "омск": "55",
    "челябинск": "74",
    "ростов-на-дону": "61",
    "красноярск": "24",
    "пермь": "59",
    "воронеж": "36",
    "волгоград": "34",
    "краснодар": "23",
    "саратов": "64",
    "тюмень": "72",
    "барнаул": "22",
    "ижевск": "18",
    "ульяновск": "73",
    "иркутск": "38",
    "хабаровск": "27",
    "ярославль": "76",
    "владивосток": "25",
    "тольятти": "63",
    "набережные челны": "16",
    "кемерово": "42",
    "оренбург": "56",
    "рязань": "62",
    "пенза": "58",
    "липецк": "48",
    "киров": "43",
    "чебоксары": "21",
    "тула": "71",
    "астрахань": "30",
    "калуга": "40",
    "брянск": "32",
    "курск": "46",
    "белгород": "31",
    "владимир": "33",
    "тверь": "69",
    "иваново": "37",
    "сочи": "23",
}


def get_region_code(city: str) -> str:
    """Получить код региона nalog.ru по русскому названию города."""
    return _CITY_TO_REGION.get(city.lower().strip(), "")


def parse_egrul_item(item: dict[str, Any]) -> LegalEntity:
    """Распарсить один элемент из ответа ЕГРЮЛ nalog.ru в объект LegalEntity.

    Функция вынесена на уровень модуля для удобства тестирования
    без реальных HTTP-запросов.

    Поля ответа nalog.ru:
    - ``n``  — полное наименование
    - ``c``  — город
    - ``r``  — код региона (4 символа)
    - ``i``  — ИНН
    - ``g``  — ОГРН
    - ``k``  — код статуса: "1" = действующее, "0" = ликвидировано
    - ``p``  — дата регистрации (дд.мм.гггг)
    - ``a``  — юридический адрес
    - ``o``  — основной ОКВЭД (код)
    """
    status_code = str(item.get("k", "")).strip()
    if status_code == "1":
        status = "действующее"
    elif status_code == "0":
        status = "ликвидировано"
    else:
        status = None

    inn = str(item.get("i", "") or item.get("inn", "") or "").strip()
    ogrn = str(item.get("g", "") or "").strip() or None

    return LegalEntity(
        source="egrul",
        source_url=_TOKEN_URL,
        name=str(item.get("n", "") or "").strip(),
        inn=inn,
        ogrn=ogrn,
        registration_date=str(item.get("p", "") or "").strip() or None,
        address=str(item.get("a", "") or "").strip() or None,
        status=status,
        main_activity=str(item.get("o", "") or "").strip() or None,
    )


class EgrulScraper:
    """Скрапер ЕГРЮЛ через публичный HTTP API nalog.ru.

    Не использует Playwright — работает через httpx напрямую.
    Поддерживает поиск по названию компании и по ИНН.

    Использование::

        scraper = EgrulScraper(cfg.http, cfg.proxy)
        entities = await scraper.search(name="ООО Колорстар", city="Уфа")
        entities = await scraper.search(inn="0277123456")
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
        name: str = "",
        inn: str = "",
        city: str = "",
        max_results: int = 10,
    ) -> list[LegalEntity]:
        """Поиск юридических лиц в ЕГРЮЛ.

        Args:
            name: Название организации (частичное или полное).
            inn: ИНН организации (если указан, игнорирует name и city).
            city: Город для фильтрации по региону.
            max_results: Максимальное число возвращаемых записей.

        Returns:
            Список объектов LegalEntity.
        """
        query = inn.strip() if inn.strip() else name.strip()
        if not query:
            logger.warning("ЕГРЮЛ: не указано ни name, ни inn")
            return []

        region = get_region_code(city) if city and not inn else ""

        proxy_url = (
            self._proxy.url
            if self._proxy and self._proxy.enabled and self._proxy.url
            else None
        )
        timeout = self._config.timeout if self._config else 30.0
        headers = {
            "User-Agent": get_random_user_agent(),
            "Accept": "application/json, text/javascript, */*",
            "Accept-Language": "ru-RU,ru;q=0.9",
            "Referer": _EGRUL_BASE,
            "Origin": _EGRUL_BASE,
        }

        try:
            async with httpx.AsyncClient(
                timeout=timeout,
                proxy=proxy_url,
                headers=headers,
                follow_redirects=True,
            ) as client:
                # Шаг 1: получить токен
                token = await self._get_token(client, query, region)
                if token is None:
                    logger.error("ЕГРЮЛ: не удалось получить токен поиска")
                    return []

                # Шаг 2: получить результаты
                return await self._get_results(client, query, region, token, max_results)

        except Exception as exc:
            logger.error("ЕГРЮЛ: ошибка поиска %r: %s", query, exc)
            return []

    async def _get_token(
        self,
        client: httpx.AsyncClient,
        query: str,
        region: str,
    ) -> str | None:
        """POST запрос для получения токена сессии поиска."""
        try:
            response = await client.post(
                _TOKEN_URL,
                data={"query": query, "region": region, "page": "0"},
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            response.raise_for_status()
            data = response.json()
            return data.get("t")
        except Exception as exc:
            logger.debug("ЕГРЮЛ: ошибка получения токена: %s", exc)
            return None

    async def _get_results(
        self,
        client: httpx.AsyncClient,
        query: str,
        region: str,
        token: str,
        max_results: int,
    ) -> list[LegalEntity]:
        """GET запрос для получения результатов поиска."""
        entities: list[LegalEntity] = []
        page = 0

        while len(entities) < max_results:
            try:
                params: dict[str, str] = {
                    "query": query,
                    "region": region,
                    "page": str(page),
                    "t": token,
                }
                response = await client.get(_SEARCH_URL, params=params)
                response.raise_for_status()
                data = response.json()
            except Exception as exc:
                logger.error("ЕГРЮЛ: ошибка запроса страницы %d: %s", page, exc)
                break

            rows = data.get("rows", [])
            if not rows:
                break

            for row in rows:
                entities.append(parse_egrul_item(row))
                if len(entities) >= max_results:
                    break

            total = int(data.get("total", 0) or 0)
            page += 1
            # ЕГРЮЛ отдаёт максимум 20 строк за страницу
            if len(entities) >= total or page * 20 >= total:
                break

        return entities
