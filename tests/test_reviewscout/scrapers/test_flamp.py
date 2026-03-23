"""Тесты скрапера Flamp."""

from unittest.mock import AsyncMock, patch

import pytest

from src.tools.reviewscout.scrapers.flamp import FlampScraper, parse_flamp_rating


# ─── parse_flamp_rating ───────────────────────────────────────────────────────


def test_parse_flamp_rating_standard():
    """Оценка в шкале 1–5."""
    assert parse_flamp_rating("4.5") == 4.5
    assert parse_flamp_rating("5") == 5.0
    assert parse_flamp_rating("1") == 1.0


def test_parse_flamp_rating_comma():
    """Запятая как разделитель дробной части."""
    assert parse_flamp_rating("4,5") == 4.5


def test_parse_flamp_rating_scale10():
    """Оценка в шкале 1–10 конвертируется в 1–5."""
    assert parse_flamp_rating("10") == 5.0
    assert parse_flamp_rating("8") == 4.0


def test_parse_flamp_rating_empty():
    """Пустая строка → None."""
    assert parse_flamp_rating("") is None


def test_parse_flamp_rating_no_numbers():
    """Текст без чисел → None."""
    assert parse_flamp_rating("нет оценки") is None


def test_parse_flamp_rating_out_of_range():
    """Число вне диапазона 1–10 → None."""
    assert parse_flamp_rating("0.5") is None
    assert parse_flamp_rating("11") is None


# ─── FlampScraper ─────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_flamp_scraper_returns_summary():
    """FlampScraper.scrape возвращает ReviewSummary."""
    mock_page = AsyncMock()
    mock_page.goto = AsyncMock()
    mock_page.wait_for_selector = AsyncMock(side_effect=Exception("not found"))
    mock_page.query_selector_all = AsyncMock(return_value=[])
    mock_page.evaluate = AsyncMock()
    mock_page.close = AsyncMock()

    mock_locator = AsyncMock()
    mock_locator.is_visible = AsyncMock(return_value=False)
    mock_locator.first = mock_locator
    mock_page.locator = AsyncMock(return_value=mock_locator)

    mock_context = AsyncMock()
    mock_context.new_page = AsyncMock(return_value=mock_page)

    with patch("src.tools.reviewscout.scrapers.flamp.detect_captcha", return_value=False), \
         patch("src.tools.reviewscout.scrapers.flamp.random_delay", new=AsyncMock()):
        scraper = FlampScraper(mock_context)
        result = await scraper.scrape("https://ufa.flamp.ru/firm/salon-123")

    assert result is not None
    assert result.source == "flamp"
    assert result.reviews == []


@pytest.mark.asyncio
async def test_flamp_scraper_returns_none_on_exception():
    """FlampScraper.scrape возвращает None при ошибке браузера."""
    mock_context = AsyncMock()
    mock_context.new_page = AsyncMock(side_effect=Exception("browser error"))

    with patch("src.tools.reviewscout.scrapers.flamp.detect_captcha", return_value=False), \
         patch("src.tools.reviewscout.scrapers.flamp.random_delay", new=AsyncMock()):
        scraper = FlampScraper(mock_context)
        result = await scraper.scrape("https://ufa.flamp.ru/firm/salon-123")

    assert result is None


@pytest.mark.asyncio
async def test_flamp_scraper_collects_reviews():
    """FlampScraper.scrape собирает отзывы из DOM."""
    mock_author_el = AsyncMock()
    mock_author_el.inner_text = AsyncMock(return_value="Анна Смирнова")

    mock_text_el = AsyncMock()
    mock_text_el.inner_text = AsyncMock(return_value="Замечательный салон!")

    mock_date_el = AsyncMock()
    mock_date_el.get_attribute = AsyncMock(side_effect=lambda attr: "2024-02-10" if attr == "datetime" else None)
    mock_date_el.inner_text = AsyncMock(return_value="10 февраля 2024")

    mock_rating_el = AsyncMock()
    mock_rating_el.get_attribute = AsyncMock(return_value="4.5")
    mock_rating_el.inner_text = AsyncMock(return_value="4.5")

    async def mock_item_query_selector(selector):
        if "author-name" in selector or "reviewer" in selector or "author" in selector:
            return mock_author_el
        if "review-text" in selector or "reviewBody" in selector or "review__body" in selector:
            return mock_text_el
        if "date" in selector or "datePublished" in selector:
            return mock_date_el
        if "rating" in selector or "ratingValue" in selector:
            return mock_rating_el
        return None

    mock_item_el = AsyncMock()
    mock_item_el.query_selector = mock_item_query_selector
    mock_item_el.query_selector_all = AsyncMock(return_value=[])

    call_count = {"n": 0}

    async def mock_qsa(selector):
        if call_count["n"] == 0:
            call_count["n"] += 1
            return [mock_item_el]
        return [mock_item_el]

    mock_page = AsyncMock()
    mock_page.goto = AsyncMock()
    mock_page.wait_for_selector = AsyncMock()
    mock_page.query_selector_all = mock_qsa
    mock_page.evaluate = AsyncMock()
    mock_page.close = AsyncMock()

    mock_locator = AsyncMock()
    mock_locator.is_visible = AsyncMock(return_value=False)
    mock_locator.first = mock_locator
    mock_page.locator = AsyncMock(return_value=mock_locator)

    mock_context = AsyncMock()
    mock_context.new_page = AsyncMock(return_value=mock_page)

    with patch("src.tools.reviewscout.scrapers.flamp.detect_captcha", return_value=False), \
         patch("src.tools.reviewscout.scrapers.flamp.random_delay", new=AsyncMock()):
        scraper = FlampScraper(mock_context)
        result = await scraper.scrape("https://ufa.flamp.ru/firm/salon-123", max_reviews=10)

    assert result is not None
    assert len(result.reviews) >= 1
    review = result.reviews[0]
    assert review.author == "Анна Смирнова"
    assert review.text == "Замечательный салон!"
    assert review.date == "2024-02-10"
    assert review.platform == "flamp"
