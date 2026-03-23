"""Скрапер YCLIENTS — извлечение прайса из виджета записи (Playwright, SPA)."""

from __future__ import annotations

import logging
import re
from typing import Any

from playwright.async_api import BrowserContext

from src.core.anti_detect import detect_captcha, random_delay, wait_for_captcha_solve
from src.core.config import ScrapingConfig
from src.tools.pricescout.models import PriceList, ServicePrice

logger = logging.getLogger(__name__)

# CSS-селекторы виджета YCLIENTS.
# Указаны несколько вариантов на случай изменений в DOM/версиях виджета.
# Приоритет: первый совпавший — используется.
_SERVICES_CONTAINER_SELECTORS = [
    ".service_categories_list",           # новый виджет (n.yclients.com)
    ".services-list",                      # старый виджет (w.yclients.com)
    "#services-list",
    "[class*='service-category']",
    "[class*='services-list']",
]

_CATEGORY_SELECTORS = [
    ".service_category",
    ".services-category",
    "[class*='service-category']",
    "[class*='serviceCategory']",
]

_CATEGORY_TITLE_SELECTORS = [
    ".service_category_title",
    ".services-category__title",
    "h2[class*='title']",
    "h3[class*='title']",
    "[class*='category-title']",
    "[class*='categoryTitle']",
]

_ITEM_SELECTORS = [
    ".service_item",
    ".services-item",
    "[class*='service-item']",
    "[class*='serviceItem']",
    "li[class*='service']",
]

_ITEM_NAME_SELECTORS = [
    ".service_title",
    ".service_name",
    ".services-item__title",
    "[class*='service-title']",
    "[class*='serviceName']",
    "[class*='service-name']",
]

_ITEM_PRICE_SELECTORS = [
    ".service_price",
    ".services-item__price",
    "[class*='service-price']",
    "[class*='servicePrice']",
    "[class*='price']",
]

_ITEM_DURATION_SELECTORS = [
    ".service_duration",
    ".services-item__duration",
    "[class*='service-duration']",
    "[class*='serviceDuration']",
    "[class*='duration']",
]


def parse_price_text(text: str) -> tuple[int | None, int | None, int | None]:
    """Распарсить текст цены в числовые поля (price, price_from, price_to).

    Примеры::

        "800 ₽"              → (800,  None, None)
        "от 1 500 ₽"         → (None, 1500, None)
        "1 500 – 2 000 ₽"    → (None, 1500, 2000)
        "до 2 000 ₽"         → (None, None, 2000)
        "бесплатно"          → (0,    None, None)
        "по договорённости"  → (None, None, None)

    Returns:
        Тройка (price, price_from, price_to).
    """
    cleaned = text.strip()
    if not cleaned:
        return None, None, None

    lower = cleaned.lower()

    # Договорная цена / нет информации
    if any(kw in lower for kw in ("договор", "уточняйте", "звоните", "—", "нет цен")):
        return None, None, None

    if "бесплатно" in lower:
        return 0, None, None

    # Убираем неразрывные пробелы и нормализуем тире
    normalized = cleaned.replace("\xa0", " ").replace("−", "-").replace("–", "-").replace("—", "-")

    # Извлекаем числа (с пробелами как разделители тысяч)
    nums = re.findall(r"\d[\d\s]{0,7}\d|\d{3,}", normalized)
    amounts: list[int] = []
    for n in nums:
        try:
            amounts.append(int(n.replace(" ", "")))
        except ValueError:
            pass

    if not amounts:
        return None, None, None

    has_from = "от" in lower
    has_to = "до" in lower

    # Диапазон: два числа или явное "от...до"
    if len(amounts) >= 2:
        return None, amounts[0], amounts[1]

    if has_from and not has_to:
        return None, amounts[0], None

    if has_to and not has_from:
        return None, None, amounts[0]

    # Единственное число — точная цена
    return amounts[0], None, None


class YclientsScraper:
    """Скрапер прайса с YCLIENTS через Playwright.

    Поддерживает виджеты:
    - ``yclients.com/company/{id}/``
    - ``n.yclients.com/company/{id}/``
    - ``w.yclients.com/o/{id}``

    Использование::

        async with BrowserManager(cfg.browser) as manager:
            ctx = await manager.new_context()
            scraper = YclientsScraper(ctx, cfg.scraping)
            price_list = await scraper.fetch("https://yclients.com/company/12345/", "Студия")
    """

    def __init__(
        self,
        context: BrowserContext,
        config: ScrapingConfig | None = None,
    ) -> None:
        self._context = context
        self._config = config or ScrapingConfig()

    async def fetch(self, url: str, org_name: str = "") -> PriceList | None:
        """Получить прайс-лист с YCLIENTS-виджета.

        Args:
            url: URL YCLIENTS-виджета.
            org_name: Название организации (для поля org_name в PriceList).

        Returns:
            Объект PriceList или None при ошибке.
        """
        page = None
        try:
            page = await self._context.new_page()
            logger.debug("YCLIENTS: открываем %s", url)
            await page.goto(url, wait_until="domcontentloaded", timeout=30_000)
            await random_delay(self._config.delay_min, self._config.delay_max)

            if await detect_captcha(page):
                logger.warning("YCLIENTS: обнаружена капча — ожидание ручного решения")
                await wait_for_captcha_solve(page)

            # Ждём появления списка услуг
            container_loaded = False
            for sel in _SERVICES_CONTAINER_SELECTORS:
                try:
                    await page.wait_for_selector(sel, timeout=10_000)
                    container_loaded = True
                    logger.debug("YCLIENTS: контейнер услуг найден по селектору %r", sel)
                    break
                except Exception:
                    continue

            if not container_loaded:
                # Пробуем подождать ещё немного и продолжить без гарантии загрузки
                await random_delay(2.0, 3.0)
                logger.warning("YCLIENTS: контейнер услуг не найден, продолжаем без ожидания")

            services = await self._parse_services(page)

            if not services:
                logger.warning("YCLIENTS: услуги не найдены на %s", url)

            return PriceList(
                source="yclients",
                source_url=url,
                fetched_from=url,
                org_name=org_name,
                services=services,
            )

        except Exception as exc:
            logger.error("YCLIENTS: ошибка при загрузке %s: %s", url, exc)
            return None
        finally:
            if page is not None:
                await page.close()

    async def _parse_services(self, page: Any) -> list[ServicePrice]:
        """Разобрать список услуг со страницы YCLIENTS."""
        services: list[ServicePrice] = []

        # Пробуем найти категории
        categories_found = False
        for cat_sel in _CATEGORY_SELECTORS:
            cat_elements = await page.query_selector_all(cat_sel)
            if not cat_elements:
                continue
            categories_found = True
            logger.debug("YCLIENTS: найдено %d категорий по %r", len(cat_elements), cat_sel)

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
                    break  # нашли услуги по первому подошедшему селектору
            break  # нашли категории

        if not categories_found:
            # Пробуем без категорий — просто ищем все item-элементы
            for item_sel in _ITEM_SELECTORS:
                items = await page.query_selector_all(item_sel)
                if not items:
                    continue
                logger.debug("YCLIENTS: найдено %d услуг без категорий по %r", len(items), item_sel)
                for item_el in items:
                    service = await _parse_service_element(item_el, None)
                    if service:
                        services.append(service)
                break

        return services


async def _parse_service_element(item_el: Any, category: str | None) -> ServicePrice | None:
    """Разобрать один элемент услуги YCLIENTS."""
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
            # Последний fallback — весь текст элемента
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
        logger.debug("YCLIENTS: ошибка парсинга услуги: %s", exc)
        return None
