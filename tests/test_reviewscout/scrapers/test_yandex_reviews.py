"""Тесты скрапера Яндекс.Отзывов."""

from unittest.mock import AsyncMock, patch

import pytest

from src.tools.reviewscout.scrapers.yandex_reviews import (
    YandexReviewsScraper,
    _make_reviews_url,
    parse_star_rating,
)


# ─── parse_star_rating ────────────────────────────────────────────────────────


def test_parse_star_rating_integer():
    """Целое число 1–5 → float."""
    assert parse_star_rating("5") == 5.0
    assert parse_star_rating("1") == 1.0
    assert parse_star_rating("3") == 3.0


def test_parse_star_rating_float():
    """Число с запятой или точкой."""
    assert parse_star_rating("4.5") == 4.5
    assert parse_star_rating("4,5") == 4.5


def test_parse_star_rating_with_text():
    """Рейтинг среди текста."""
    assert parse_star_rating("Оценка: 4.5") == 4.5
    assert parse_star_rating("4.2 из 5") == 4.2


def test_parse_star_rating_out_of_range():
    """Числа вне диапазона 1–5 → None."""
    assert parse_star_rating("6") is None
    assert parse_star_rating("10") is None
    assert parse_star_rating("0") is None


def test_parse_star_rating_empty():
    """Пустая строка → None."""
    assert parse_star_rating("") is None
    assert parse_star_rating("   ") is None


def test_parse_star_rating_no_numbers():
    """Текст без чисел → None."""
    assert parse_star_rating("нет оценки") is None


# ─── _make_reviews_url ────────────────────────────────────────────────────────


def test_make_reviews_url_appends_suffix():
    """Добавляет /reviews/ к URL карточки."""
    url = "https://yandex.ru/maps/org/salon/123456789"
    assert _make_reviews_url(url) == "https://yandex.ru/maps/org/salon/123456789/reviews/"


def test_make_reviews_url_trailing_slash():
    """Работает с URL с завершающим слэшем."""
    url = "https://yandex.ru/maps/org/salon/123456789/"
    assert _make_reviews_url(url) == "https://yandex.ru/maps/org/salon/123456789/reviews/"


def test_make_reviews_url_already_has_reviews():
    """Не дублирует /reviews если уже есть."""
    url = "https://yandex.ru/maps/org/salon/123456789/reviews/"
    assert "/reviews" in _make_reviews_url(url)
    assert _make_reviews_url(url).count("/reviews") == 1


# ─── YandexReviewsScraper ────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_yandex_scraper_returns_summary():
    """YandexReviewsScraper.scrape возвращает ReviewSummary."""
    mock_page = AsyncMock()
    mock_page.url = "https://yandex.ru/maps/org/salon/123/reviews/"
    mock_page.goto = AsyncMock()
    mock_page.wait_for_selector = AsyncMock(side_effect=Exception("not found"))
    mock_page.query_selector_all = AsyncMock(return_value=[])
    mock_page.evaluate = AsyncMock()
    mock_page.close = AsyncMock()

    # Мок для locator
    mock_locator = AsyncMock()
    mock_locator.is_visible = AsyncMock(return_value=False)
    mock_locator.first = mock_locator
    mock_page.locator = AsyncMock(return_value=mock_locator)

    mock_context = AsyncMock()
    mock_context.new_page = AsyncMock(return_value=mock_page)

    with patch("src.tools.reviewscout.scrapers.yandex_reviews.detect_captcha", return_value=False), \
         patch("src.tools.reviewscout.scrapers.yandex_reviews.random_delay", new=AsyncMock()):
        scraper = YandexReviewsScraper(mock_context)
        result = await scraper.scrape("https://yandex.ru/maps/org/salon/123456789/")

    assert result is not None
    assert result.source == "yandex"
    assert result.reviews == []


@pytest.mark.asyncio
async def test_yandex_scraper_returns_none_on_exception():
    """YandexReviewsScraper.scrape возвращает None при ошибке."""
    mock_context = AsyncMock()
    mock_context.new_page = AsyncMock(side_effect=Exception("browser crashed"))

    with patch("src.tools.reviewscout.scrapers.yandex_reviews.detect_captcha", return_value=False), \
         patch("src.tools.reviewscout.scrapers.yandex_reviews.random_delay", new=AsyncMock()):
        scraper = YandexReviewsScraper(mock_context)
        result = await scraper.scrape("https://yandex.ru/maps/org/salon/123456789/")

    assert result is None


@pytest.mark.asyncio
async def test_yandex_scraper_collects_reviews():
    """YandexReviewsScraper.scrape собирает отзывы из DOM."""
    # Мок элемента отзыва
    mock_author_el = AsyncMock()
    mock_author_el.inner_text = AsyncMock(return_value="Иван Петров")

    mock_text_el = AsyncMock()
    mock_text_el.inner_text = AsyncMock(return_value="Отличный мастер, всё понравилось!")

    mock_date_el = AsyncMock()
    mock_date_el.get_attribute = AsyncMock(return_value=None)
    mock_date_el.inner_text = AsyncMock(return_value="15 марта 2024")

    mock_rating_el = AsyncMock()
    mock_rating_el.inner_text = AsyncMock(return_value="5")

    async def mock_item_query_selector(selector):
        if "author" in selector or "reviewer" in selector or "user-icon" in selector:
            return mock_author_el
        if "body-text" in selector or "review-text" in selector or "review-body" in selector:
            return mock_text_el
        if "date" in selector:
            return mock_date_el
        if "rating" in selector and "badge" in selector:
            return mock_rating_el
        return None

    mock_item_el = AsyncMock()
    mock_item_el.query_selector = mock_item_query_selector
    mock_item_el.query_selector_all = AsyncMock(return_value=[])

    mock_page = AsyncMock()
    mock_page.url = "https://yandex.ru/maps/org/salon/123/reviews/"
    mock_page.goto = AsyncMock()
    mock_page.wait_for_selector = AsyncMock()
    mock_page.evaluate = AsyncMock()
    mock_page.close = AsyncMock()

    # Первый вызов query_selector_all возвращает один отзыв, последующие — пустые (стоп)
    call_count = {"n": 0}

    async def mock_qsa(selector):
        if call_count["n"] == 0:
            call_count["n"] += 1
            return [mock_item_el]
        return [mock_item_el]  # уже в seen — дубль, стоп

    mock_page.query_selector_all = mock_qsa

    mock_locator = AsyncMock()
    mock_locator.is_visible = AsyncMock(return_value=False)
    mock_locator.first = mock_locator
    mock_page.locator = AsyncMock(return_value=mock_locator)

    mock_context = AsyncMock()
    mock_context.new_page = AsyncMock(return_value=mock_page)

    with patch("src.tools.reviewscout.scrapers.yandex_reviews.detect_captcha", return_value=False), \
         patch("src.tools.reviewscout.scrapers.yandex_reviews.random_delay", new=AsyncMock()):
        scraper = YandexReviewsScraper(mock_context)
        result = await scraper.scrape("https://yandex.ru/maps/org/salon/123456789/", max_reviews=10)

    assert result is not None
    assert len(result.reviews) >= 1
    review = result.reviews[0]
    assert review.author == "Иван Петров"
    assert review.text == "Отличный мастер, всё понравилось!"
    assert review.platform == "yandex"
