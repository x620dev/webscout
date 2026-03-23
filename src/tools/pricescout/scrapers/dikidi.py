"""Скрапер Dikidi — извлечение прайса из виджета записи (Playwright, SPA)."""

from __future__ import annotations

import logging
from typing import Any

from playwright.async_api import BrowserContext

from src.core.anti_detect import detect_captcha, random_delay, wait_for_captcha_solve
from src.core.config import ScrapingConfig
from src.tools.pricescout.models import PriceList, ServicePrice
from src.tools.pricescout.scrapers.yclients import parse_price_text

logger = logging.getLogger(__name__)

# CSS-селекторы виджета Dikidi.
# Dikidi использует несколько вариантов вёрстки для разных типов страниц.
_SERVICES_CONTAINER_SELECTORS = [
    ".catalog",
    ".services-catalog",
    "[class*='catalog']",
    "[class*='services']",
    ".service-list",
]

_CATEGORY_SELECTORS = [
    ".catalog__group",
    ".service-group",
    "[class*='catalog-group']",
    "[class*='service-group']",
    "[class*='serviceGroup']",
]

_CATEGORY_TITLE_SELECTORS = [
    ".catalog__group-title",
    ".service-group__title",
    "h2[class*='title']",
    "h3[class*='title']",
    "[class*='group-title']",
    "[class*='groupTitle']",
]

_ITEM_SELECTORS = [
    ".catalog__item",
    ".service__item",
    "[class*='catalog-item']",
    "[class*='service-item']",
    "[class*='serviceItem']",
]

_ITEM_NAME_SELECTORS = [
    ".catalog__item-title",
    ".service__info-title",
    ".service__title",
    "[class*='item-title']",
    "[class*='service-title']",
    "[class*='serviceTitle']",
]

_ITEM_PRICE_SELECTORS = [
    ".catalog__item-price",
    ".service__price",
    "[class*='item-price']",
    "[class*='service-price']",
    "[class*='servicePrice']",
    "[class*='price']",
]

_ITEM_DURATION_SELECTORS = [
    ".catalog__item-duration",
    ".service__duration",
    "[class*='item-duration']",
    "[class*='service-duration']",
    "[class*='duration']",
]


class DikidiScraper:
    """Скрапер прайса с Dikidi через Playwright.

    Поддерживает виджеты:
    - ``dikidi.net/salon/{id}``
    - ``dikidi.net/{city}/{slug}``
    - ``dikidi.net/company/{id}``

    Использование::

        async with BrowserManager(cfg.browser) as manager:
            ctx = await manager.new_context()
            scraper = DikidiScraper(ctx, cfg.scraping)
            price_list = await scraper.fetch("https://dikidi.net/salon/12345", "Студия")
    """

    def __init__(
        self,
        context: BrowserContext,
        config: ScrapingConfig | None = None,
    ) -> None:
        self._context = context
        self._config = config or ScrapingConfig()

    async def fetch(self, url: str, org_name: str = "") -> PriceList | None:
        """Получить прайс-лист с Dikidi-виджета.

        Args:
            url: URL Dikidi-виджета.
            org_name: Название организации.

        Returns:
            Объект PriceList или None при ошибке.
        """
        page = None
        try:
            page = await self._context.new_page()
            logger.debug("Dikidi: открываем %s", url)
            await page.goto(url, wait_until="domcontentloaded", timeout=30_000)
            await random_delay(self._config.delay_min, self._config.delay_max)

            if await detect_captcha(page):
                logger.warning("Dikidi: обнаружена капча — ожидание ручного решения")
                await wait_for_captcha_solve(page)

            # Ждём появления списка услуг
            container_loaded = False
            for sel in _SERVICES_CONTAINER_SELECTORS:
                try:
                    await page.wait_for_selector(sel, timeout=10_000)
                    container_loaded = True
                    logger.debug("Dikidi: контейнер услуг найден по селектору %r", sel)
                    break
                except Exception:
                    continue

            if not container_loaded:
                await random_delay(2.0, 3.0)
                logger.warning("Dikidi: контейнер услуг не найден, продолжаем без ожидания")

            services = await self._parse_services(page)

            if not services:
                logger.warning("Dikidi: услуги не найдены на %s", url)

            return PriceList(
                source="dikidi",
                source_url=url,
                fetched_from=url,
                org_name=org_name,
                services=services,
            )

        except Exception as exc:
            logger.error("Dikidi: ошибка при загрузке %s: %s", url, exc)
            return None
        finally:
            if page is not None:
                await page.close()

    async def _parse_services(self, page: Any) -> list[ServicePrice]:
        """Разобрать список услуг со страницы Dikidi."""
        services: list[ServicePrice] = []

        # Пробуем найти категории
        categories_found = False
        for cat_sel in _CATEGORY_SELECTORS:
            cat_elements = await page.query_selector_all(cat_sel)
            if not cat_elements:
                continue
            categories_found = True
            logger.debug("Dikidi: найдено %d категорий по %r", len(cat_elements), cat_sel)

            for cat_el in cat_elements:
                # Название категории
                category_name: str | None = None
                for title_sel in _CATEGORY_TITLE_SELECTORS:
                    title_el = await cat_el.query_selector(title_sel)
                    if title_el:
                        category_name = (await title_el.inner_text()).strip() or None
                        break

                # Услуги внутри категории
                for item_sel in _ITEM_SELECTORS:
                    items = await cat_el.query_selector_all(item_sel)
                    if not items:
                        continue
                    for item_el in items:
                        service = await _parse_service_element(item_el, category_name)
                        if service:
                            services.append(service)
                    break
            break

        if not categories_found:
            for item_sel in _ITEM_SELECTORS:
                items = await page.query_selector_all(item_sel)
                if not items:
                    continue
                logger.debug("Dikidi: найдено %d услуг без категорий по %r", len(items), item_sel)
                for item_el in items:
                    service = await _parse_service_element(item_el, None)
                    if service:
                        services.append(service)
                break

        return services


async def _parse_service_element(item_el: Any, category: str | None) -> ServicePrice | None:
    """Разобрать один элемент услуги Dikidi."""
    try:
        # Название
        name: str | None = None
        for sel in _ITEM_NAME_SELECTORS:
            el = await item_el.query_selector(sel)
            if el:
                name = (await el.inner_text()).strip() or None
                if name:
                    break

        if not name:
            full_text = (await item_el.inner_text()).strip()
            if full_text:
                name = full_text.split("\n")[0].strip() or None

        if not name:
            return None

        # Цена
        price: int | None = None
        price_from: int | None = None
        price_to: int | None = None
        for sel in _ITEM_PRICE_SELECTORS:
            el = await item_el.query_selector(sel)
            if el:
                price_text = (await el.inner_text()).strip()
                if price_text:
                    price, price_from, price_to = parse_price_text(price_text)
                    break

        # Длительность
        duration: str | None = None
        for sel in _ITEM_DURATION_SELECTORS:
            el = await item_el.query_selector(sel)
            if el:
                dur_text = (await el.inner_text()).strip()
                if dur_text:
                    duration = dur_text
                    break

        return ServicePrice(
            name=name,
            price=price,
            price_from=price_from,
            price_to=price_to,
            duration=duration,
            category=category,
        )

    except Exception as exc:
        logger.debug("Dikidi: ошибка парсинга услуги: %s", exc)
        return None
