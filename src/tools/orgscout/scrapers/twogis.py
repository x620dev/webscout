"""Скрапер 2ГИС — перехват API catalog.api.2gis.ru через Playwright."""

from __future__ import annotations

import asyncio
import logging
from typing import Any
from urllib.parse import quote

from playwright.async_api import BrowserContext, Page, Response

from src.core.anti_detect import detect_captcha, random_delay, wait_for_captcha_solve
from src.core.config import ScrapingConfig
from src.core.models import Contacts, GeoPoint
from src.tools.orgscout.models import Organization

logger = logging.getLogger(__name__)

BASE_URL = "https://2gis.ru"
_API_HOST = "catalog.api.2gis.ru"

# Таблица slug-городов 2ГИС (русское название → URL-slug).
# Дополняется по мере необходимости.
_CITY_SLUGS: dict[str, str] = {
    "москва": "moscow",
    "санкт-петербург": "spb",
    "питер": "spb",
    "казань": "kazan",
    "уфа": "ufa",
    "екатеринбург": "ekb",
    "новосибирск": "novosibirsk",
    "краснодар": "krasnodar",
    "ростов-на-дону": "rostov-na-donu",
    "нижний новгород": "n_novgorod",
    "самара": "samara",
    "омск": "omsk",
    "челябинск": "chelyabinsk",
    "воронеж": "voronezh",
    "пермь": "perm",
    "красноярск": "krasnoyarsk",
    "волгоград": "volgograd",
    "тюмень": "tyumen",
    "барнаул": "barnaul",
    "иркутск": "irkutsk",
    "хабаровск": "habarovsk",
    "владивосток": "vladivostok",
    "ижевск": "izhevsk",
    "ярославль": "yaroslavl",
    "тольятти": "togliatti",
    "оренбург": "orenburg",
    "кемерово": "kemerovo",
    "новокузнецк": "novokuznetsk",
    "рязань": "ryazan",
    "астрахань": "astrahan",
    "набережные челны": "naberezhnye_chelny",
    "пенза": "penza",
    "липецк": "lipetsk",
    "киров": "kirov",
    "чебоксары": "cheboksary",
    "тула": "tula",
    "курск": "kursk",
    "брянск": "bryansk",
    "магнитогорск": "magnitogorsk",
    "сочи": "sochi",
    "ставрополь": "stavropol",
}

# Домены CRM-систем для определения online-записи
_BOOKING_DOMAINS = ("yclients.com", "dikidi.net", "usedbook.ru")

# Максимальное число прокруток страницы при сборе результатов
_MAX_SCROLL_ATTEMPTS = 40


def get_city_slug(city: str) -> str:
    """Вернуть URL-slug города для 2ГИС.

    Если город не найден в таблице — возвращает нормализованное название.
    """
    return _CITY_SLUGS.get(city.lower().strip(), city.lower().strip())


class TwoGisScraper:
    """Скрапер организаций из 2ГИС.

    Алгоритм:
    1. Открыть страницу поиска 2ГИС.
    2. Перехватить ответы от catalog.api.2gis.ru.
    3. Прокручивать страницу, пока API не вернёт нужное число результатов.
    4. Распарсить JSON из перехваченных ответов → список Organization.

    Использование::

        async with BrowserManager(cfg.browser) as manager:
            ctx = await manager.new_context()
            scraper = TwoGisScraper(ctx, cfg.scraping)
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
    ) -> list[Organization]:
        """Собрать организации из 2ГИС по запросу.

        Args:
            query: Поисковый запрос, например «маникюр».
            city: Город, например «Уфа».
            max_results: Лимит результатов (None = из конфига).

        Returns:
            Список организаций.
        """
        limit = max_results or self._config.max_results
        city_slug = get_city_slug(city)
        url = f"{BASE_URL}/{city_slug}/search/{quote(query)}"

        page = await self._context.new_page()
        try:
            return await self._scrape_search(page, url, limit)
        finally:
            await page.close()

    async def fetch(self, org_url: str) -> Organization | None:
        """Получить данные одной организации по URL карточки.

        Args:
            org_url: URL карточки 2ГИС.

        Returns:
            Организация или None при ошибке.
        """
        items: list[dict] = []
        page = await self._context.new_page()
        try:
            _attach_interceptor(page, items)
            await page.goto(
                org_url,
                wait_until="networkidle",
                timeout=self._config.page_load_timeout * 1000,
            )
            await random_delay(self._config.delay_min, self._config.delay_max)

            if await detect_captcha(page):
                if self._config.retry_on_captcha:
                    solved = await wait_for_captcha_solve(page, self._config.captcha_timeout)
                    if not solved:
                        return None
                else:
                    return None

            # Небольшая пауза чтобы API успел ответить
            await asyncio.sleep(1.5)

            # Пробуем парсить из перехваченного API
            for item in items:
                org = parse_api_item(item, org_url)
                if org:
                    return org

            # Фолбэк на DOM-парсинг
            return await _parse_dom_card(page, org_url)
        except Exception as exc:
            logger.error("Ошибка при получении карточки 2ГИС %s: %s", org_url, exc)
            return None
        finally:
            await page.close()

    # ─────────────────────────────────────────────────────────────────────────
    # Внутренние методы
    # ─────────────────────────────────────────────────────────────────────────

    async def _scrape_search(self, page: Page, url: str, limit: int) -> list[Organization]:
        """Основная логика: открыть поиск 2ГИС, перехватить API, прокрутить."""
        items: list[dict] = []
        _attach_interceptor(page, items)

        logger.info("2ГИС: открываем %s", url)
        await page.goto(
            url,
            wait_until="networkidle",
            timeout=self._config.page_load_timeout * 1000,
        )
        await random_delay(self._config.delay_min, self._config.delay_max)

        if await detect_captcha(page):
            if self._config.retry_on_captcha:
                solved = await wait_for_captcha_solve(page, self._config.captcha_timeout)
                if not solved:
                    return []
            else:
                return []

        # Прокручиваем страницу для загрузки дополнительных результатов
        prev_count = -1
        stale = 0

        for _ in range(_MAX_SCROLL_ATTEMPTS):
            if len(items) >= limit:
                break

            await page.evaluate("window.scrollBy(0, 800)")
            await random_delay(self._config.scroll_pause, self._config.scroll_pause + 1.0)

            if len(items) == prev_count:
                stale += 1
                if stale >= 4:
                    break
            else:
                stale = 0
            prev_count = len(items)

        logger.info("2ГИС: перехвачено %d элементов API.", len(items))

        # Парсим собранные данные, дедуплицируем по URL
        results: list[Organization] = []
        seen: set[str] = set()

        for item in items:
            org = parse_api_item(item)
            if org and org.source_url not in seen:
                seen.add(org.source_url)
                results.append(org)
                if len(results) >= limit:
                    break

        return results


# ─────────────────────────────────────────────────────────────────────────────
# Вспомогательные функции (не методы класса — удобнее тестировать)
# ─────────────────────────────────────────────────────────────────────────────


def _attach_interceptor(page: Page, storage: list[dict]) -> None:
    """Подключить перехват API-ответов 2ГИС к странице Playwright.

    Добавляет обработчик события ``response``: при каждом ответе от
    ``catalog.api.2gis.ru`` извлекает элементы из поля ``result.items``
    и складывает их в ``storage``.
    """
    async def on_response(response: Response) -> None:
        if _API_HOST not in response.url:
            return
        try:
            body: Any = await response.json()
        except Exception:
            return
        if not isinstance(body, dict):
            return

        result = body.get("result", {})
        if isinstance(result, dict):
            items = result.get("items", [])
            if isinstance(items, list):
                storage.extend(items)
        # Некоторые эндпоинты возвращают список напрямую
        elif isinstance(result, list):
            storage.extend(result)

    page.on("response", on_response)


def parse_api_item(item: dict[str, Any], fallback_url: str = BASE_URL) -> Organization | None:
    """Преобразовать элемент API 2ГИС в модель Organization.

    Args:
        item: Словарь — один элемент из ``result.items`` API 2ГИС.
        fallback_url: URL для ``source_url`` если в item нет своего URL.

    Returns:
        Organization или None если невозможно извлечь минимальные данные.
    """
    name: str | None = item.get("name") or item.get("full_name")
    if not name:
        return None

    # URL карточки
    org_id = str(item.get("id", ""))
    source_url: str = item.get("url") or (
        f"{BASE_URL}/firm/{org_id}" if org_id else fallback_url
    )

    # Адрес
    address_raw: Any = item.get("address", {})
    address = ""
    if isinstance(address_raw, dict):
        address = address_raw.get("name") or address_raw.get("full_name") or ""
    elif isinstance(address_raw, str):
        address = address_raw

    # Координаты
    geo: GeoPoint | None = None
    point: Any = item.get("point")
    if isinstance(point, dict):
        lat = point.get("lat")
        lon = point.get("lon")
        if lat is not None and lon is not None:
            try:
                geo = GeoPoint(lat=float(lat), lon=float(lon))
            except (TypeError, ValueError):
                pass

    # Категории / рубрики
    categories: list[str] = []
    rubrics: Any = item.get("rubrics", [])
    if isinstance(rubrics, list):
        categories = [r["name"] for r in rubrics if isinstance(r, dict) and r.get("name")]

    # Контакты
    phones: list[str] = []
    website: str | None = None
    contact_groups: Any = item.get("contact_groups", [])
    if isinstance(contact_groups, list):
        for group in contact_groups:
            if not isinstance(group, dict):
                continue
            for contact in group.get("contacts", []):
                if not isinstance(contact, dict):
                    continue
                ctype = contact.get("type", "")
                value: str = contact.get("value", "")
                if not value:
                    continue
                if ctype == "phone":
                    phones.append(value)
                elif ctype in ("website", "url", "link") and website is None:
                    website = value

    # Рейтинг и число отзывов
    rating: float | None = None
    reviews_count: int | None = None
    reviews_raw: Any = item.get("reviews", {})
    if isinstance(reviews_raw, dict):
        r_val = reviews_raw.get("rating")
        if r_val is not None:
            try:
                rating = float(r_val)
            except (TypeError, ValueError):
                pass
        c_val = reviews_raw.get("count")
        if c_val is not None:
            try:
                reviews_count = int(c_val)
            except (TypeError, ValueError):
                pass

    # Online-запись (CRM)
    online_booking: str | None = None
    links: Any = item.get("links", [])
    if isinstance(links, list):
        for link in links:
            if not isinstance(link, dict):
                continue
            href: str = link.get("value", "") or link.get("url", "")
            if any(domain in href for domain in _BOOKING_DOMAINS):
                online_booking = href
                break

    return Organization(
        source="twogis",
        source_url=source_url,
        name=name.strip(),
        categories=categories,
        address=address.strip(),
        geo=geo,
        contacts=Contacts(phone=phones, website=website),
        rating=rating,
        reviews_count=reviews_count,
        online_booking=online_booking,
    )


async def _parse_dom_card(page: Page, source_url: str) -> Organization | None:
    """Фолбэк: DOM-парсинг карточки 2ГИС (если API не вернул данные).

    Используется при открытии отдельной карточки организации (не поиска).
    """
    try:
        name_sel = "h1[class*='_name'], [class*='orgCard__'] h1, [data-testid='org-name']"
        el = page.locator(name_sel).first
        name = (await el.inner_text()).strip() if await el.is_visible(timeout=3000) else None
        if not name:
            return None

        addr_sel = "[class*='_address'], [data-testid='org-address']"
        addr_el = page.locator(addr_sel).first
        address = (
            (await addr_el.inner_text()).strip()
            if await addr_el.is_visible(timeout=2000)
            else ""
        )

        phones: list[str] = await page.eval_on_selector_all(
            "a[href^='tel:']",
            "els => els.map(el => el.href.replace('tel:', '').trim()).filter(Boolean)",
        )

        return Organization(
            source="twogis",
            source_url=source_url,
            name=name,
            address=address,
            contacts=Contacts(phone=phones),
        )
    except Exception as exc:
        logger.error("DOM-фолбэк 2ГИС не удался %s: %s", source_url, exc)
        return None
