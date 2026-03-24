"""Скрапер Яндекс.Карт — DOM-парсинг карточек организаций + автоскролл."""

from __future__ import annotations

import logging
import re
from typing import AsyncIterator
from urllib.parse import quote

from playwright.async_api import BrowserContext, Page

from src.core.anti_detect import (
    detect_captcha,
    random_delay,
    wait_for_captcha_solve,
)
from src.core.config import ScrapingConfig
from src.core.models import Contacts, GeoPoint
from src.tools.orgscout.models import Organization

logger = logging.getLogger(__name__)

BASE_URL = "https://yandex.ru/maps/"

# CSS-селекторы Яндекс.Карт.
# При изменении DOM обновляйте только эту секцию.

# Ждём появления хотя бы одного снипета организации в сайдбаре
_SEL_RESULTS_LIST = ".search-business-snippet-view"
# Ссылки на карточки организаций (все на странице, дедупликация по Set)
_SEL_RESULT_LINK = "a[href*='/maps/org/']"

# Селекторы страницы карточки организации
_SEL_NAME = "h1.orgpage-header-view__header, [itemprop='name']"
_SEL_CATEGORY = "[class*='orgpage-header-view__categories'] a, [class*='business-rubric-view']"
_SEL_ADDRESS = ".business-contacts-view__address, [class*='orgpage-contacts__address']"
_SEL_PHONE = "a[href^='tel:']"
_SEL_WEBSITE = ".business-contacts-view__link[href^='http'], a[class*='business-url-view']"
_SEL_RATING = ".business-header-rating-view, .business-rating-badge-view__rating"
_SEL_REVIEWS_COUNT = ".business-rating-amount-view, [class*='business-reviews-badge-view__count']"
_SEL_HOURS = ".business-card-working-status-view__text, [class*='orgpage-schedule-view']"
_SEL_BOOKING_YCLIENTS = "a[href*='yclients.com']"
_SEL_BOOKING_DIKIDI = "a[href*='dikidi.net']"

# Максимальное число итераций скролла при обходе списка
_MAX_SCROLL_ATTEMPTS = 50


class YandexMapsScraper:
    """Скрапер организаций из Яндекс.Карт.

    Алгоритм:
    1. Открыть страницу поиска.
    2. Прокрутить список результатов, собирая URL карточек.
    3. Открыть каждую карточку и распарсить данные организации.

    Использование::

        async with BrowserManager(cfg.browser) as manager:
            ctx = await manager.new_context()
            scraper = YandexMapsScraper(ctx, cfg.scraping)
            orgs = await scraper.scrape("маникюр", "Уфа", max_results=50)
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
        max_results: int | None = None,
    ) -> AsyncIterator[Organization]:
        """Собрать организации по запросу (async generator).

        Args:
            query: Поисковый запрос, например «маникюр».
            city: Город, например «Уфа».
            max_results: Лимит результатов (None = из конфига).

        Yields:
            Организации по мере их получения.
        """
        limit = max_results or self._config.max_results
        url = f"{BASE_URL}?text={quote(f'{query} {city}')}"

        page = await self._context.new_page()
        try:
            async for org in self._scrape_search(page, url, limit):
                yield org
        finally:
            await page.close()

    async def fetch(self, org_url: str) -> Organization | None:
        """Получить данные одной организации по URL её карточки.

        Args:
            org_url: URL карточки на Яндекс.Картах.

        Returns:
            Организация или None при ошибке/капче.
        """
        page = await self._context.new_page()
        try:
            await page.goto(
                org_url,
                wait_until="domcontentloaded",
                timeout=self._config.page_load_timeout * 1000,
            )

            # Ждём пока React отрендерит карточку (данные грузятся через API)
            try:
                await page.wait_for_selector(
                    ".business-card-view",
                    timeout=self._config.page_load_timeout * 1000,
                )
            except Exception:
                logger.warning("Карточка не отрендерилась: %s", org_url)
                return None

            await random_delay(self._config.delay_min, self._config.delay_max)

            if await detect_captcha(page):
                if self._config.retry_on_captcha:
                    solved = await wait_for_captcha_solve(page, self._config.captcha_timeout)
                    if not solved:
                        logger.error("Капча не решена: %s", org_url)
                        return None
                else:
                    return None

            return await self._parse_org_card(page, org_url)
        except Exception as exc:
            logger.error("Ошибка при получении карточки %s: %s", org_url, exc)
            return None
        finally:
            await page.close()

    # ─────────────────────────────────────────────────────────────────────────
    # Внутренние методы
    # ─────────────────────────────────────────────────────────────────────────

    async def _scrape_search(
        self, page: Page, url: str, limit: int
    ) -> AsyncIterator[Organization]:
        """Открыть страницу поиска, прокрутить и отдавать организации по одной."""
        logger.info("Яндекс.Карты: открываем %s", url)
        await page.goto(
            url,
            wait_until="domcontentloaded",
            timeout=self._config.page_load_timeout * 1000,
        )
        await random_delay(self._config.delay_min, self._config.delay_max)

        if await detect_captcha(page):
            if self._config.retry_on_captcha:
                solved = await wait_for_captcha_solve(page, self._config.captcha_timeout)
                if not solved:
                    return
            else:
                return

        # Ждём появления списка результатов
        try:
            await page.wait_for_selector(
                _SEL_RESULTS_LIST,
                timeout=self._config.page_load_timeout * 1000,
            )
        except Exception:
            logger.warning("Список результатов не найден. URL: %s", url)
            return

        # Собираем URL карточек организаций
        org_urls = await self._collect_card_urls(page, limit)
        logger.info("Яндекс.Карты: найдено %d ссылок.", len(org_urls))

        # Парсим каждую карточку и отдаём сразу
        for card_url in org_urls:
            org = await self.fetch(card_url)
            if org:
                yield org
            await random_delay(self._config.delay_min, self._config.delay_max)

    async def _collect_card_urls(self, page: Page, limit: int) -> list[str]:
        """Прокрутить список результатов и собрать URL карточек.

        Останавливается если достигнут лимит или нет новых ссылок.
        """
        urls: list[str] = []
        seen: set[str] = set()
        stale_count = 0

        for attempt in range(_MAX_SCROLL_ATTEMPTS):
            links: list[str] = await page.eval_on_selector_all(
                _SEL_RESULT_LINK,
                "els => [...new Set(els.map(el => el.href))].filter(h => h.includes('/maps/org/'))",
            )
            snippet_count = await page.locator(".search-business-snippet-view").count()
            logger.debug("Итерация %d: снипетов=%d, ссылок=%d", attempt, snippet_count, len(links))
            new_found = False
            for link in links:
                # Нормализовать до базового URL организации: /maps/org/slug/id/
                m = re.match(r"(https?://[^/]+/maps/org/[^/]+/\d+/)", link)
                clean = m.group(1) if m else link.split("?")[0]
                if clean not in seen:
                    seen.add(clean)
                    urls.append(clean)
                    new_found = True

            if len(urls) >= limit:
                break

            if not new_found:
                stale_count += 1
                if stale_count >= 5:
                    break
            else:
                stale_count = 0

            # Прокрутить через mouse.wheel над областью сайдбара
            await page.mouse.move(200, 500)
            await page.mouse.wheel(0, 1200)
            await random_delay(self._config.scroll_pause, self._config.scroll_pause + 1.0)

        return urls[:limit]

    async def _parse_org_card(self, page: Page, source_url: str) -> Organization | None:
        """Распарсить карточку организации, открытую в браузере."""
        name = await self._text(page, _SEL_NAME)
        if not name:
            logger.debug("Имя организации не найдено: %s", source_url)
            return None

        categories = await self._texts(page, _SEL_CATEGORY)
        address = await self._text(page, _SEL_ADDRESS) or ""

        phones: list[str] = await page.eval_on_selector_all(
            _SEL_PHONE,
            "els => els.map(el => el.href.replace('tel:', '').trim()).filter(Boolean)",
        )

        website = await self._attr(page, _SEL_WEBSITE, "href")
        rating = await self._parse_rating(page, _SEL_RATING)
        reviews_count = await self._parse_count(page, _SEL_REVIEWS_COUNT)
        working_hours = await self._text(page, _SEL_HOURS)
        geo = _extract_geo_from_url(page.url)

        online_booking: str | None = None
        for sel in (_SEL_BOOKING_YCLIENTS, _SEL_BOOKING_DIKIDI):
            href = await self._attr(page, sel, "href")
            if href:
                online_booking = href
                break

        return Organization(
            source="yandex_maps",
            source_url=source_url,
            name=name.strip(),
            categories=categories,
            address=address.strip(),
            geo=geo,
            contacts=Contacts(phone=phones, website=website),
            rating=rating,
            reviews_count=reviews_count,
            working_hours=working_hours,
            online_booking=online_booking,
        )

    # ─────────────────────────────────────────────────────────────────────────
    # Вспомогательные методы DOM
    # ─────────────────────────────────────────────────────────────────────────

    async def _text(self, page: Page, selector: str) -> str | None:
        """Вернуть текст первого видимого элемента по селектору."""
        try:
            el = page.locator(selector).first
            if await el.is_visible(timeout=2000):
                return (await el.inner_text()).strip() or None
        except Exception:
            pass
        return None

    async def _texts(self, page: Page, selector: str) -> list[str]:
        """Вернуть тексты всех видимых элементов по селектору."""
        try:
            els = page.locator(selector)
            count = await els.count()
            result = []
            for i in range(count):
                el = els.nth(i)
                if await el.is_visible(timeout=1000):
                    text = (await el.inner_text()).strip()
                    if text:
                        result.append(text)
            return result
        except Exception:
            return []

    async def _attr(self, page: Page, selector: str, attr: str) -> str | None:
        """Вернуть атрибут первого видимого элемента по селектору."""
        try:
            el = page.locator(selector).first
            if await el.is_visible(timeout=2000):
                return await el.get_attribute(attr)
        except Exception:
            pass
        return None

    async def _parse_rating(self, page: Page, selector: str) -> float | None:
        """Извлечь число рейтинга из текста элемента."""
        text = await self._text(page, selector)
        if not text:
            return None
        m = re.search(r"(\d+[.,]\d+|\d+)", text.replace(",", "."))
        if m:
            try:
                return float(m.group(1))
            except ValueError:
                pass
        return None

    async def _parse_count(self, page: Page, selector: str) -> int | None:
        """Извлечь целое число (число отзывов) из текста элемента."""
        text = await self._text(page, selector)
        if not text:
            return None
        digits = re.sub(r"[^\d]", "", text)
        return int(digits) if digits else None


def _extract_geo_from_url(url: str) -> GeoPoint | None:
    """Попытаться извлечь координаты из URL Яндекс.Карт.

    Яндекс.Карты кодирует координаты в URL как ``/@lat,lon``.
    """
    m = re.search(r"/@([\d.]+),([\d.]+)", url)
    if m:
        try:
            return GeoPoint(lat=float(m.group(1)), lon=float(m.group(2)))
        except ValueError:
            pass
    return None
