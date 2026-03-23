"""Скрапер Rusprofile (rusprofile.ru) — юрданные через Playwright (SPA).

Алгоритм:
1. Открыть страницу поиска с query (название или ИНН).
2. Дождаться результатов.
3. Парсить карточки результатов со страницы поиска.
4. Опционально переходить на страницу конкретной компании для полных данных.
"""

from __future__ import annotations

import logging
import re
from typing import Any

from playwright.async_api import BrowserContext

from src.core.anti_detect import detect_captcha, random_delay, wait_for_captcha_solve
from src.core.config import ScrapingConfig
from src.tools.legalscout.models import LegalEntity

logger = logging.getLogger(__name__)

_RUSPROFILE_BASE = "https://www.rusprofile.ru"
_SEARCH_URL = f"{_RUSPROFILE_BASE}/search"

# Максимальное число попыток скролла/ожидания при поиске
_MAX_WAIT_ATTEMPTS = 3

# CSS-селекторы страницы поиска rusprofile.ru
_SEL_RESULTS_LIST = (
    ".company-list, "
    "[class*='search-results'], "
    ".companies-list"
)
_SEL_RESULT_ITEM = (
    ".company-item, "
    "[class*='company-item'], "
    ".search-result-item"
)
_SEL_RESULT_NAME = (
    ".company-item__name, "
    "[class*='company-name'], "
    ".company-item__title a, "
    "h3.company-item__name"
)
_SEL_RESULT_LINK = (
    ".company-item__name a, "
    ".company-item__link, "
    "[class*='company-item'] a[href*='/id/']"
)
_SEL_RESULT_INN = (
    ".company-item__info .requisites__item:contains('ИНН'), "
    "[class*='company-inn'], "
    ".requisite-inn"
)
_SEL_RESULT_STATUS = (
    ".company-item__status, "
    "[class*='company-status'], "
    ".company-state"
)

# CSS-селекторы страницы конкретной компании
_SEL_COMPANY_NAME = (
    "h1.company-header__name, "
    ".company-name h1, "
    "[class*='company-header'] h1"
)
_SEL_COMPANY_INN = (
    "[data-field='inn'], "
    ".requisites__value--inn, "
    "dd.company-info__value--inn"
)
_SEL_COMPANY_OGRN = (
    "[data-field='ogrn'], "
    ".requisites__value--ogrn"
)
_SEL_COMPANY_ADDRESS = (
    "[data-field='address'], "
    ".company-address__value, "
    "[class*='company-address'] span"
)
_SEL_COMPANY_DIRECTOR = (
    "[class*='company-director'] .company-info__value, "
    "[data-field='director'], "
    ".company-director__name"
)
_SEL_COMPANY_STATUS = (
    ".company-status__text, "
    "[class*='company-status'] span, "
    ".status-badge"
)
_SEL_COMPANY_ACTIVITY = (
    ".company-activity__main .company-info__value, "
    "[data-field='okved'], "
    ".okved-main__name"
)
_SEL_COMPANY_CAPITAL = (
    "[data-field='authorized_capital'], "
    ".company-capital__value"
)
_SEL_COMPANY_EMPLOYEES = (
    "[data-field='employees'], "
    ".company-employees__value"
)
_SEL_COMPANY_REGDATE = (
    "[data-field='registration_date'], "
    ".company-regdate__value"
)


def parse_inn_text(text: str) -> str:
    """Извлечь ИНН из текстовой строки."""
    m = re.search(r"\b(\d{10,12})\b", text)
    return m.group(1) if m else ""


def parse_capital_text(text: str) -> int | None:
    """Извлечь сумму уставного капитала из текста (в рублях)."""
    clean = re.sub(r"[^\d]", "", text)
    return int(clean) if clean else None


class RusprofileScraper:
    """Скрапер Rusprofile через Playwright.

    Алгоритм поиска:
    1. Открыть rusprofile.ru/search?query=<name>
    2. Распарсить карточки результатов
    3. Для первого результата перейти на его страницу и получить полные данные

    Использование::

        async with BrowserManager(cfg.browser) as manager:
            ctx = await manager.new_context()
            scraper = RusprofileScraper(ctx, cfg.scraping)
            entities = await scraper.search("Колорстар", "Уфа")
    """

    def __init__(
        self,
        context: BrowserContext,
        config: ScrapingConfig | None = None,
    ) -> None:
        self._context = context
        self._config = config or ScrapingConfig()

    async def search(
        self,
        name: str = "",
        inn: str = "",
        max_results: int = 5,
        fetch_details: bool = False,
    ) -> list[LegalEntity]:
        """Поиск юридических лиц на Rusprofile.

        Args:
            name: Название организации.
            inn: ИНН (если указан, приоритет над name).
            max_results: Максимальное число результатов.
            fetch_details: Переходить ли на страницу компании для полных данных.

        Returns:
            Список объектов LegalEntity.
        """
        query = inn.strip() if inn.strip() else name.strip()
        if not query:
            logger.warning("Rusprofile: не указано ни name, ни inn")
            return []

        page = None
        try:
            page = await self._context.new_page()
            search_url = f"{_SEARCH_URL}?query={query}"
            logger.debug("Rusprofile: открываем %s", search_url)

            await page.goto(
                search_url,
                wait_until="domcontentloaded",
                timeout=self._config.page_load_timeout * 1000,
            )
            await random_delay(self._config.delay_min, self._config.delay_max)

            if await detect_captcha(page):
                logger.warning("Rusprofile: обнаружена капча — ожидание ручного решения")
                solved = await wait_for_captcha_solve(page, self._config.captcha_timeout)
                if not solved:
                    return []

            # Ждём загрузки результатов
            for _ in range(_MAX_WAIT_ATTEMPTS):
                try:
                    await page.wait_for_selector(
                        _SEL_RESULTS_LIST + ", " + _SEL_RESULT_ITEM,
                        timeout=8_000,
                    )
                    break
                except Exception:
                    await random_delay(1.0, 2.0)

            entities = await self._parse_search_results(page, max_results)

            # Для первого результата — дополнительный детальный запрос
            if fetch_details and entities:
                first_url = await self._get_first_result_url(page)
                if first_url:
                    detail = await self._fetch_company_detail(first_url, entities[0])
                    if detail:
                        entities[0] = detail

            return entities

        except Exception as exc:
            logger.error("Rusprofile: ошибка поиска %r: %s", query, exc)
            return []
        finally:
            if page is not None:
                await page.close()

    async def _parse_search_results(
        self,
        page: Any,
        max_results: int,
    ) -> list[LegalEntity]:
        """Распарсить карточки результатов со страницы поиска."""
        entities: list[LegalEntity] = []

        items = await page.query_selector_all(_SEL_RESULT_ITEM)
        for item_el in items[:max_results]:
            entity = await _parse_search_item(item_el, page.url)
            if entity is not None:
                entities.append(entity)

        return entities

    async def _get_first_result_url(self, page: Any) -> str | None:
        """Получить URL первой карточки результатов."""
        try:
            link_el = await page.query_selector(_SEL_RESULT_LINK)
            if link_el:
                href = await link_el.get_attribute("href")
                if href:
                    return href if href.startswith("http") else f"{_RUSPROFILE_BASE}{href}"
        except Exception:
            pass
        return None

    async def _fetch_company_detail(
        self,
        url: str,
        base_entity: LegalEntity,
    ) -> LegalEntity | None:
        """Перейти на страницу компании и получить полные данные."""
        detail_page = None
        try:
            detail_page = await self._context.new_page()
            await detail_page.goto(
                url,
                wait_until="domcontentloaded",
                timeout=self._config.page_load_timeout * 1000,
            )
            await random_delay(self._config.delay_min, self._config.delay_max)

            async def get_text(sel: str) -> str | None:
                try:
                    el = detail_page.locator(sel).first
                    if await el.is_visible(timeout=2000):
                        return (await el.inner_text()).strip() or None
                except Exception:
                    pass
                return None

            name = await get_text(_SEL_COMPANY_NAME) or base_entity.name
            inn_text = await get_text(_SEL_COMPANY_INN) or ""
            inn = parse_inn_text(inn_text) or base_entity.inn
            ogrn_text = await get_text(_SEL_COMPANY_OGRN) or ""
            ogrn = re.sub(r"[^\d]", "", ogrn_text) or base_entity.ogrn
            address = await get_text(_SEL_COMPANY_ADDRESS) or base_entity.address
            director = await get_text(_SEL_COMPANY_DIRECTOR)
            status_text = await get_text(_SEL_COMPANY_STATUS) or base_entity.status
            activity = await get_text(_SEL_COMPANY_ACTIVITY) or base_entity.main_activity
            capital_text = await get_text(_SEL_COMPANY_CAPITAL) or ""
            capital = parse_capital_text(capital_text)
            employees = await get_text(_SEL_COMPANY_EMPLOYEES)
            regdate = await get_text(_SEL_COMPANY_REGDATE) or base_entity.registration_date

            return LegalEntity(
                source="rusprofile",
                source_url=url,
                name=name,
                inn=inn,
                ogrn=ogrn or None,
                registration_date=regdate,
                address=address,
                director=director,
                status=status_text,
                main_activity=activity,
                authorized_capital=capital,
                employee_count=employees,
            )

        except Exception as exc:
            logger.error("Rusprofile: ошибка загрузки карточки %s: %s", url, exc)
            return None
        finally:
            if detail_page is not None:
                await detail_page.close()


async def _parse_search_item(item_el: Any, page_url: str) -> LegalEntity | None:
    """Распарсить один элемент результатов поиска Rusprofile."""
    try:
        # Название
        name: str = ""
        for sel in (_SEL_RESULT_NAME,):
            el = await item_el.query_selector(sel)
            if el:
                text = (await el.inner_text()).strip()
                if text:
                    name = text
                    break

        if not name:
            return None

        # URL карточки
        source_url = page_url
        link_el = await item_el.query_selector("a[href]")
        if link_el:
            href = await link_el.get_attribute("href") or ""
            if href:
                source_url = href if href.startswith("http") else f"{_RUSPROFILE_BASE}{href}"

        # ИНН — ищем в тексте карточки (строка вида "ИНН 1234567890")
        full_text = await item_el.inner_text()
        inn = parse_inn_text(full_text)

        # ОГРН — 13-значное число
        ogrn: str | None = None
        m = re.search(r"\b(\d{13})\b", full_text)
        if m:
            ogrn = m.group(1)

        # Статус
        status: str | None = None
        status_el = await item_el.query_selector(_SEL_RESULT_STATUS)
        if status_el:
            status_text = (await status_el.inner_text()).strip().lower()
            if "ликвид" in status_text or "закрыт" in status_text:
                status = "ликвидировано"
            elif "действу" in status_text or "активн" in status_text:
                status = "действующее"
            else:
                status = status_text or None

        return LegalEntity(
            source="rusprofile",
            source_url=source_url,
            name=name,
            inn=inn,
            ogrn=ogrn,
            status=status,
        )

    except Exception as exc:
        logger.debug("Rusprofile: ошибка парсинга карточки: %s", exc)
        return None
