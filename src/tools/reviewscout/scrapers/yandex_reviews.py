"""Скрапер отзывов Яндекс.Карт — парсинг отзывов из карточки организации (Playwright)."""

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

# CSS-селекторы панели отзывов Яндекс.Карт.
# Яндекс использует CSS-модули с нестабильными именами — выбраны устойчивые варианты.
_SEL_REVIEWS_TAB = (
    "[class*='business-reviews-tab'], "
    "[class*='tabs-select-view__title'][aria-label*='тзыв'], "
    "a[href*='/reviews/']"
)
_SEL_REVIEWS_LIST = (
    "[class*='business-reviews-view__reviews-container'], "
    "[class*='reviews-list'], "
    "[class*='business-review-feed']"
)
_SEL_REVIEW_ITEM = (
    "[class*='business-review-view__content'], "
    "[class*='review-item__content'], "
    "[class*='business-review-view']"
)
_SEL_REVIEW_AUTHOR = (
    "[class*='business-review-view__author'] span:first-child, "
    "[class*='user-icon__content'], "
    "[class*='reviewer-name']"
)
_SEL_REVIEW_RATING = (
    "[class*='business-rating-badge__rating'], "
    "[class*='review-rating__value']"
)
_SEL_REVIEW_STARS = (
    "[class*='stars__icon_full'], "
    "[class*='star_full'], "
    "[aria-label*='оценка']"
)
_SEL_REVIEW_TEXT = (
    "[class*='business-review-view__body-text'], "
    "[class*='review-text__content'], "
    "[class*='review-body']"
)
_SEL_REVIEW_DATE = (
    "[class*='business-review-view__date'], "
    "[class*='review-date'], "
    "meta[itemprop='datePublished']"
)
_SEL_ORG_RATING = (
    "[class*='business-rating-badge__rating'], "
    "[class*='orgpage-header-view__rating']"
)
_SEL_ORG_REVIEWS_COUNT = (
    "[class*='business-rating-badge__count'], "
    "[class*='orgpage-header-view__count']"
)
_SEL_ORG_NAME = (
    "[class*='orgpage-header-view__name'], "
    "[class*='business-card-title__name']"
)


def parse_star_rating(text: str) -> float | None:
    """Извлечь числовой рейтинг из текста.

    Примеры::

        "4.5"       → 4.5
        "4,5"       → 4.5
        "Оценка: 5" → 5.0

    Returns:
        Число от 1 до 5 или None если не удалось распарсить.
    """
    if not text:
        return None
    normalized = text.replace(",", ".")
    m = re.search(r"(\d+(?:\.\d+)?)", normalized)
    if m:
        try:
            val = float(m.group(1))
            if 1.0 <= val <= 5.0:
                return val
        except ValueError:
            pass
    return None


class YandexReviewsScraper:
    """Скрапер отзывов из карточки организации на Яндекс.Картах.

    Алгоритм:
    1. Открыть карточку организации.
    2. Кликнуть на вкладку «Отзывы» (или перейти по /<id>/reviews/).
    3. Дождаться загрузки списка, прокрутить для подгрузки.
    4. Распарсить каждый отзыв.

    Использование::

        async with BrowserManager(cfg.browser) as manager:
            ctx = await manager.new_context()
            scraper = YandexReviewsScraper(ctx, cfg.scraping)
            summary = await scraper.scrape(
                "https://yandex.ru/maps/org/salon/123456789/",
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
        org_url: str,
        max_reviews: int | None = None,
    ) -> ReviewSummary | None:
        """Собрать отзывы организации с Яндекс.Карт.

        Args:
            org_url: URL карточки организации на Яндекс.Картах.
            max_reviews: Лимит отзывов (None = из конфига).

        Returns:
            ReviewSummary или None при ошибке.
        """
        limit = max_reviews or self._config.max_results
        page = None
        try:
            page = await self._context.new_page()
            logger.debug("Яндекс.Отзывы: открываем %s", org_url)
            await page.goto(
                org_url,
                wait_until="domcontentloaded",
                timeout=self._config.page_load_timeout * 1000,
            )
            await random_delay(self._config.delay_min, self._config.delay_max)

            if await detect_captcha(page):
                logger.warning("Яндекс.Отзывы: обнаружена капча — ожидание ручного решения")
                solved = await wait_for_captcha_solve(page, self._config.captcha_timeout)
                if not solved:
                    return None

            # Имя организации
            org_name = await _get_text(page, _SEL_ORG_NAME) or ""

            # Общий рейтинг
            rating = await _parse_rating(page, _SEL_ORG_RATING)
            reviews_count = await _parse_count(page, _SEL_ORG_REVIEWS_COUNT)

            # Переходим на вкладку отзывов
            reviews_url = _make_reviews_url(org_url)
            if page.url != reviews_url:
                try:
                    # Сначала пробуем кликнуть по вкладке
                    tab = page.locator(_SEL_REVIEWS_TAB).first
                    if await tab.is_visible(timeout=3000):
                        await tab.click()
                        await random_delay(1.0, 2.0)
                    else:
                        await page.goto(
                            reviews_url,
                            wait_until="domcontentloaded",
                            timeout=self._config.page_load_timeout * 1000,
                        )
                        await random_delay(self._config.delay_min, self._config.delay_max)
                except Exception:
                    await page.goto(
                        reviews_url,
                        wait_until="domcontentloaded",
                        timeout=self._config.page_load_timeout * 1000,
                    )
                    await random_delay(self._config.delay_min, self._config.delay_max)

            # Ждём появления отзывов
            for sel in (_SEL_REVIEWS_LIST, _SEL_REVIEW_ITEM):
                try:
                    await page.wait_for_selector(sel, timeout=10_000)
                    break
                except Exception:
                    continue

            reviews = await self._collect_reviews(page, limit)

            return ReviewSummary(
                source="yandex",
                source_url=reviews_url,
                org_name=org_name,
                rating=rating,
                reviews_count=reviews_count,
                reviews=reviews,
            )

        except Exception as exc:
            logger.error("Яндекс.Отзывы: ошибка при загрузке %s: %s", org_url, exc)
            return None
        finally:
            if page is not None:
                await page.close()

    async def _collect_reviews(self, page: Any, limit: int) -> list[Review]:
        """Прокрутить страницу отзывов и собрать их."""
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

            if not new_found and len(items) > 0:
                break

            # Прокрутка для подгрузки следующих отзывов
            try:
                await page.eval_on_selector(
                    _SEL_REVIEWS_LIST,
                    "el => el.scrollBy(0, 800)",
                )
            except Exception:
                await page.evaluate("window.scrollBy(0, 800)")

            await random_delay(self._config.scroll_pause, self._config.scroll_pause + 1.0)

        return reviews[:limit]


async def _parse_review_element(item_el: Any) -> Review | None:
    """Распарсить один элемент отзыва."""
    try:
        # Автор
        author: str | None = None
        for sel in (_SEL_REVIEW_AUTHOR,):
            el = await item_el.query_selector(sel)
            if el:
                text = (await el.inner_text()).strip()
                if text:
                    author = text
                    break

        # Рейтинг — пробуем несколько подходов
        rating: float | None = None

        # 1. Текст элемента с рейтингом
        rating_el = await item_el.query_selector(_SEL_REVIEW_RATING)
        if rating_el:
            rating_text = (await rating_el.inner_text()).strip()
            rating = parse_star_rating(rating_text)

        # 2. Считаем заполненные звёзды
        if rating is None:
            stars = await item_el.query_selector_all(_SEL_REVIEW_STARS)
            if stars:
                rating = float(len(stars))

        # 3. Атрибут aria-label с числом
        if rating is None:
            for sel in ("[aria-label*='оценка'], [aria-label*='rating']",):
                el = await item_el.query_selector(sel)
                if el:
                    label = await el.get_attribute("aria-label") or ""
                    rating = parse_star_rating(label)
                    if rating is not None:
                        break

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
            # Сначала пробуем атрибут content (для meta-тегов)
            content = await date_el.get_attribute("content")
            if content:
                date = content.strip()
            else:
                date_text = (await date_el.inner_text()).strip()
                if date_text:
                    date = date_text

        # Нужен хоть какой-то контент
        if not author and not text:
            return None

        return Review(author=author, rating=rating, text=text, date=date, platform="yandex")

    except Exception as exc:
        logger.debug("Яндекс.Отзывы: ошибка парсинга элемента: %s", exc)
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
    """Извлечь рейтинг из текста элемента."""
    text = await _get_text(page, selector)
    return parse_star_rating(text or "")


async def _parse_count(page: Any, selector: str) -> int | None:
    """Извлечь целое число (число отзывов) из текста элемента."""
    text = await _get_text(page, selector)
    if not text:
        return None
    digits = re.sub(r"[^\d]", "", text)
    return int(digits) if digits else None


def _make_reviews_url(org_url: str) -> str:
    """Построить URL страницы отзывов из URL карточки организации.

    Яндекс.Карты: добавляем ``reviews/`` к пути карточки.
    """
    url = org_url.rstrip("/")
    if "/reviews" not in url:
        url = url + "/reviews/"
    return url
