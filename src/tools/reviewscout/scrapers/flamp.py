"""Скрапер Flamp — парсинг отзывов с flamp.ru (Playwright, SPA)."""

from __future__ import annotations

import logging
import re
from typing import Any

from playwright.async_api import BrowserContext

from src.core.anti_detect import detect_captcha, random_delay, wait_for_captcha_solve
from src.core.config import ScrapingConfig
from src.tools.reviewscout.models import Review, ReviewSummary

logger = logging.getLogger(__name__)

# Максимальное число прокруток при сборе отзывов
_MAX_SCROLL_ATTEMPTS = 30

# CSS-селекторы Flamp.
# Flamp использует семантичные CSS-классы — выбраны наиболее устойчивые варианты.
_SEL_ORG_NAME = (
    "h1.company-card__name, "
    "h1[class*='company-name'], "
    "[itemprop='name']"
)
_SEL_ORG_RATING = (
    "[class*='rating__value'], "
    "[itemprop='ratingValue'], "
    "[class*='company-rating']"
)
_SEL_ORG_REVIEWS_COUNT = (
    "[class*='reviews-count'], "
    "[itemprop='reviewCount'], "
    "[class*='rating__count']"
)
_SEL_REVIEWS_LIST = (
    "[class*='reviews-list'], "
    "ul[class*='review'], "
    "[class*='company-reviews']"
)
_SEL_REVIEW_ITEM = (
    "[class*='review-item'], "
    "[itemprop='review'], "
    "[class*='firm-review']"
)
_SEL_REVIEW_AUTHOR = (
    "[class*='review-author-name'], "
    "[itemprop='author'] [itemprop='name'], "
    "[class*='reviewer__name']"
)
_SEL_REVIEW_RATING = (
    "[class*='review-rating__value'], "
    "[itemprop='ratingValue'], "
    "[class*='stars-rating__value']"
)
_SEL_REVIEW_STARS_FULL = (
    "[class*='star_full'], "
    "[class*='star--full'], "
    "i[class*='icon-star'][class*='full']"
)
_SEL_REVIEW_TEXT = (
    "[class*='review-text'], "
    "[itemprop='reviewBody'], "
    "[class*='review__body']"
)
_SEL_REVIEW_DATE = (
    "time[itemprop='datePublished'], "
    "[class*='review-date'], "
    "time[datetime]"
)
_SEL_LOAD_MORE = (
    "[class*='load-more'], "
    "button[class*='reviews-more'], "
    "a[class*='more-reviews']"
)


def parse_flamp_rating(text: str) -> float | None:
    """Извлечь рейтинг из текста элемента Flamp.

    Примеры::

        "4.5"       → 4.5
        "4,5"       → 4.5
        "10" (из 10) → None (вне диапазона 1–5)

    Returns:
        Число от 1 до 5 или None.
    """
    if not text:
        return None
    normalized = text.replace(",", ".")
    m = re.search(r"(\d+(?:\.\d+)?)", normalized)
    if m:
        try:
            val = float(m.group(1))
            # Flamp использует шкалу 1–10 или 1–5
            if 1.0 <= val <= 5.0:
                return val
            if 1.0 <= val <= 10.0:
                # Конвертируем из шкалы 10 в шкалу 5
                return round(val / 2, 1)
        except ValueError:
            pass
    return None


class FlampScraper:
    """Скрапер отзывов с Flamp.ru через Playwright.

    Поддерживает URL вида:
    - ``https://ufa.flamp.ru/firm/salon_name-1234567890``
    - ``https://flamp.ru/firm/salon_name-1234567890``

    Использование::

        async with BrowserManager(cfg.browser) as manager:
            ctx = await manager.new_context()
            scraper = FlampScraper(ctx, cfg.scraping)
            summary = await scraper.scrape(
                "https://ufa.flamp.ru/firm/salon-1234567890",
                max_reviews=50,
            )
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
        url: str,
        max_reviews: int | None = None,
    ) -> ReviewSummary | None:
        """Собрать отзывы с Flamp-страницы организации.

        Args:
            url: URL страницы организации на Flamp.
            max_reviews: Лимит отзывов (None = из конфига).

        Returns:
            ReviewSummary или None при ошибке.
        """
        limit = max_reviews or self._config.max_results
        page = None
        try:
            page = await self._context.new_page()
            logger.debug("Flamp: открываем %s", url)
            await page.goto(url, wait_until="domcontentloaded", timeout=30_000)
            await random_delay(self._config.delay_min, self._config.delay_max)

            if await detect_captcha(page):
                logger.warning("Flamp: обнаружена капча — ожидание ручного решения")
                solved = await wait_for_captcha_solve(page, self._config.captcha_timeout)
                if not solved:
                    return None

            # Имя организации
            org_name = await _get_text(page, _SEL_ORG_NAME) or ""

            # Рейтинг
            rating = await _parse_rating(page, _SEL_ORG_RATING)
            reviews_count = await _parse_count(page, _SEL_ORG_REVIEWS_COUNT)

            # Ждём список отзывов
            for sel in (_SEL_REVIEWS_LIST, _SEL_REVIEW_ITEM):
                try:
                    await page.wait_for_selector(sel, timeout=10_000)
                    break
                except Exception:
                    continue

            reviews = await self._collect_reviews(page, limit)

            return ReviewSummary(
                source="flamp",
                source_url=url,
                org_name=org_name,
                rating=rating,
                reviews_count=reviews_count,
                reviews=reviews,
            )

        except Exception as exc:
            logger.error("Flamp: ошибка при загрузке %s: %s", url, exc)
            return None
        finally:
            if page is not None:
                await page.close()

    async def _collect_reviews(self, page: Any, limit: int) -> list[Review]:
        """Собрать отзывы со страницы, подгружая при необходимости."""
        reviews: list[Review] = []
        seen_texts: set[str] = set()

        for _ in range(_MAX_SCROLL_ATTEMPTS):
            items = await page.query_selector_all(_SEL_REVIEW_ITEM)

            new_found = False
            for item_el in items:
                review = await _parse_review_element(item_el)
                if review is None:
                    continue
                key = (review.author or "") + (review.text or "")[:50]
                if key and key not in seen_texts:
                    seen_texts.add(key)
                    reviews.append(review)
                    new_found = True

            if len(reviews) >= limit:
                break

            # Пробуем нажать «Показать ещё»
            try:
                load_more = page.locator(_SEL_LOAD_MORE).first
                if await load_more.is_visible(timeout=2000):
                    await load_more.click()
                    await random_delay(self._config.delay_min, self._config.delay_max)
                    continue
            except Exception:
                pass

            # Скролл для infinite-scroll
            if not new_found:
                break

            await page.evaluate("window.scrollBy(0, 800)")
            await random_delay(self._config.scroll_pause, self._config.scroll_pause + 1.0)

        return reviews[:limit]


async def _parse_review_element(item_el: Any) -> Review | None:
    """Распарсить один элемент отзыва Flamp."""
    try:
        # Автор
        author: str | None = None
        author_el = await item_el.query_selector(_SEL_REVIEW_AUTHOR)
        if author_el:
            author_text = (await author_el.inner_text()).strip()
            if author_text:
                author = author_text

        # Рейтинг
        rating: float | None = None

        # 1. Текстовое значение рейтинга
        rating_el = await item_el.query_selector(_SEL_REVIEW_RATING)
        if rating_el:
            # Пробуем itemprop-контент
            content = await rating_el.get_attribute("content")
            if content:
                rating = parse_flamp_rating(content)
            else:
                rating = parse_flamp_rating((await rating_el.inner_text()).strip())

        # 2. Считаем заполненные звёзды
        if rating is None:
            stars = await item_el.query_selector_all(_SEL_REVIEW_STARS_FULL)
            if stars:
                rating = float(len(stars))

        # Текст отзыва
        text: str | None = None
        text_el = await item_el.query_selector(_SEL_REVIEW_TEXT)
        if text_el:
            raw = (await text_el.inner_text()).strip()
            if raw:
                text = raw

        # Дата
        date: str | None = None
        date_el = await item_el.query_selector(_SEL_REVIEW_DATE)
        if date_el:
            # Атрибут datetime (ISO-формат)
            datetime_attr = await date_el.get_attribute("datetime")
            if datetime_attr:
                date = datetime_attr.strip()
            else:
                content_attr = await date_el.get_attribute("content")
                if content_attr:
                    date = content_attr.strip()
                else:
                    date_text = (await date_el.inner_text()).strip()
                    if date_text:
                        date = date_text

        if not author and not text:
            return None

        return Review(author=author, rating=rating, text=text, date=date, platform="flamp")

    except Exception as exc:
        logger.debug("Flamp: ошибка парсинга отзыва: %s", exc)
        return None


async def _get_text(page: Any, selector: str) -> str | None:
    """Вернуть текст первого видимого элемента по селектору."""
    try:
        el = page.locator(selector).first
        if await el.is_visible(timeout=2000):
            return (await el.inner_text()).strip() or None
    except Exception:
        pass
    return None


async def _parse_rating(page: Any, selector: str) -> float | None:
    """Извлечь рейтинг из элемента страницы."""
    try:
        el = page.locator(selector).first
        if await el.is_visible(timeout=2000):
            content = await el.get_attribute("content")
            text = content or (await el.inner_text()).strip()
            return parse_flamp_rating(text)
    except Exception:
        pass
    return None


async def _parse_count(page: Any, selector: str) -> int | None:
    """Извлечь целое число (число отзывов) из текста элемента."""
    try:
        el = page.locator(selector).first
        if await el.is_visible(timeout=2000):
            content = await el.get_attribute("content")
            text = content or (await el.inner_text()).strip()
            digits = re.sub(r"[^\d]", "", text)
            return int(digits) if digits else None
    except Exception:
        pass
    return None
