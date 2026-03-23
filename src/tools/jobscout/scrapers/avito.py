"""Скрапер Avito Работа — вакансии через Playwright (SPA, DOM-парсинг)."""

from __future__ import annotations

import logging
import re
from typing import Any
from urllib.parse import quote

from playwright.async_api import BrowserContext

from src.core.anti_detect import detect_captcha, random_delay, wait_for_captcha_solve
from src.core.config import ScrapingConfig
from src.output.naming import slugify
from src.tools.jobscout.models import Vacancy

logger = logging.getLogger(__name__)

_BASE_URL = "https://www.avito.ru"

# Таблица slug-городов Avito (русское название → URL-slug)
_CITY_SLUGS: dict[str, str] = {
    "москва": "moskva",
    "санкт-петербург": "sankt-peterburg",
    "питер": "sankt-peterburg",
    "екатеринбург": "ekaterinburg",
    "новосибирск": "novosibirsk",
    "казань": "kazan",
    "уфа": "ufa",
    "самара": "samara",
    "ростов-на-дону": "rostov-na-donu",
    "краснодар": "krasnodar",
    "омск": "omsk",
    "челябинск": "chelyabinsk",
    "пермь": "perm",
    "красноярск": "krasnoyarsk",
    "воронеж": "voronezh",
    "волгоград": "volgograd",
    "тюмень": "tyumen",
    "барнаул": "barnaul",
    "саратов": "saratov",
    "ижевск": "izhevsk",
    "ульяновск": "ulyanovsk",
    "иркутск": "irkutsk",
    "хабаровск": "khabarovsk",
    "ярославль": "yaroslavl",
    "владивосток": "vladivostok",
    "тольятти": "tolyatti",
    "набережные челны": "naberezhnyye-chelny",
    "кемерово": "kemerovo",
    "оренбург": "orenburg",
    "рязань": "ryazan",
    "пенза": "penza",
    "липецк": "lipetsk",
    "киров": "kirov",
    "чебоксары": "cheboksary",
    "тула": "tula",
    "астрахань": "astrakhan",
    "нижний новгород": "nizhniy_novgorod",
    "сочи": "sochi",
}

# CSS-селекторы листинга вакансий Avito
_ITEM_SELECTOR = "div[data-marker='item']"
_TITLE_LINK_SELECTOR = "a[data-marker='item-title/link']"
_PRICE_SELECTOR = "p[data-marker='item-price']"
_PAGINATION_NEXT = "a[data-marker='pagination-button/nextPage']"


def _get_city_slug(city: str) -> str:
    """Получить URL-slug города для Avito.

    Ищет в таблице известных городов, при отсутствии транслитерирует.
    """
    return _CITY_SLUGS.get(city.lower().strip(), slugify(city))


def _parse_salary(price_text: str) -> tuple[int | None, int | None, str | None]:
    """Разобрать текст зарплаты в числовые поля.

    Примеры:
        "40 000 – 60 000 ₽" → (40000, 60000, "RUR")
        "от 35 000 ₽" → (35000, None, "RUR")
        "до 80 000 ₽" → (None, 80000, "RUR")
        "по договорённости" → (None, None, None)
    """
    text = price_text.strip()

    currency: str | None = None
    if "₽" in text or "руб" in text.lower():
        currency = "RUR"
    elif "$" in text:
        currency = "USD"
    elif "€" in text:
        currency = "EUR"

    # Извлекаем все числа (с пробелами как разделителями тысяч)
    nums = re.findall(r"\d[\d\s]*\d|\d{4,}", text.replace("\xa0", " "))
    amounts: list[int] = []
    for n in nums:
        try:
            amounts.append(int(n.replace(" ", "")))
        except ValueError:
            pass

    if not amounts:
        return None, None, None

    text_lower = text.lower()
    if "до" in text_lower and "от" not in text_lower:
        return None, amounts[0], currency
    if "от" in text_lower and len(amounts) == 1:
        return amounts[0], None, currency
    if len(amounts) >= 2:
        return amounts[0], amounts[1], currency

    return amounts[0], None, currency


class AvitoJobScraper:
    """Скрапер вакансий Avito через Playwright (SPA, DOM-парсинг).

    Использование:
        async with BrowserManager(cfg.browser) as manager:
            ctx = await manager.new_context()
            scraper = AvitoJobScraper(ctx, cfg.scraping)
            vacancies = await scraper.scrape("мастер маникюра", "Уфа", max_results=50)
    """

    def __init__(
        self,
        context: BrowserContext,
        config: ScrapingConfig | None = None,
    ) -> None:
        self._context = context
        self._config = config or ScrapingConfig()

    async def scrape(
        self,
        query: str,
        city: str,
        max_results: int = 50,
    ) -> list[Vacancy]:
        """Поиск вакансий на Avito.

        Args:
            query: Поисковый запрос.
            city: Название города на русском языке.
            max_results: Максимальное число вакансий.

        Returns:
            Список объектов Vacancy.
        """
        city_slug = _get_city_slug(city)
        url = f"{_BASE_URL}/{city_slug}/vakansii?q={quote(query)}"

        page = await self._context.new_page()
        vacancies: list[Vacancy] = []

        try:
            logger.debug("Avito Jobs: %s", url)
            await page.goto(url, wait_until="domcontentloaded", timeout=30_000)
            await random_delay(self._config)

            if await detect_captcha(page):
                logger.warning("Avito: обнаружена капча — ожидание ручного решения")
                await wait_for_captcha_solve(page)

            # Ждём появления карточек
            try:
                await page.wait_for_selector(_ITEM_SELECTOR, timeout=15_000)
            except Exception:
                logger.warning("Avito Jobs: листинг не загружен для %s", url)
                return vacancies

            while len(vacancies) < max_results:
                items = await page.query_selector_all(_ITEM_SELECTOR)
                logger.debug("Avito Jobs: найдено %d элементов", len(items))

                for item_el in items:
                    if len(vacancies) >= max_results:
                        break
                    vacancy = await self._parse_item(item_el, city)
                    if vacancy:
                        vacancies.append(vacancy)

                # Переход на следующую страницу
                next_btn = await page.query_selector(_PAGINATION_NEXT)
                if not next_btn or len(vacancies) >= max_results:
                    break

                await next_btn.click()
                await random_delay(self._config)
                try:
                    await page.wait_for_selector(_ITEM_SELECTOR, timeout=15_000)
                except Exception:
                    break

        finally:
            await page.close()

        return vacancies

    async def _parse_item(self, item_el: Any, city: str) -> Vacancy | None:
        """Распарсить одну карточку вакансии Avito."""
        try:
            # Заголовок и URL
            title_el = await item_el.query_selector(_TITLE_LINK_SELECTOR)
            if not title_el:
                return None

            title = (await title_el.inner_text()).strip()
            if not title:
                return None

            href = await title_el.get_attribute("href")
            source_url = (
                f"{_BASE_URL}{href}"
                if href and href.startswith("/")
                else (href or "")
            )

            # Зарплата
            salary_from = salary_to = None
            salary_currency = None
            price_el = await item_el.query_selector(_PRICE_SELECTOR)
            if price_el:
                price_text = (await price_el.inner_text()).strip()
                salary_from, salary_to, salary_currency = _parse_salary(price_text)

            # Название компании (несколько fallback-селекторов)
            company_name: str | None = None
            for sel in [
                "p[data-marker='item-address'] span",
                "p.iva-item-geo span",
                "span[data-marker='item-location']",
            ]:
                el = await item_el.query_selector(sel)
                if el:
                    text = (await el.inner_text()).strip()
                    if text:
                        company_name = text
                        break

            # Сниппет описания
            description: str | None = None
            desc_el = await item_el.query_selector(
                "p[data-marker='item-description/description']"
            )
            if desc_el:
                description = (await desc_el.inner_text()).strip() or None

            return Vacancy(
                source="avito",
                source_url=source_url,
                title=title,
                company_name=company_name,
                salary_from=salary_from,
                salary_to=salary_to,
                salary_currency=salary_currency,
                city=city,
                description=description,
            )

        except Exception as exc:
            logger.debug("Avito Jobs: ошибка парсинга элемента: %s", exc)
            return None
