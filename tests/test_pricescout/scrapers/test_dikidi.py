"""Тесты скрапера Dikidi."""

import pytest
from unittest.mock import AsyncMock, patch

from src.tools.pricescout.scrapers.dikidi import DikidiScraper


@pytest.mark.asyncio
async def test_dikidi_fetch_returns_price_list():
    """DikidiScraper.fetch возвращает PriceList."""
    mock_page = AsyncMock()
    mock_page.goto = AsyncMock()
    mock_page.wait_for_selector = AsyncMock(side_effect=Exception("not found"))
    mock_page.query_selector_all = AsyncMock(return_value=[])
    mock_page.close = AsyncMock()

    mock_context = AsyncMock()
    mock_context.new_page = AsyncMock(return_value=mock_page)

    with patch("src.tools.pricescout.scrapers.dikidi.detect_captcha", return_value=False), \
         patch("src.tools.pricescout.scrapers.dikidi.random_delay", new=AsyncMock()):
        scraper = DikidiScraper(mock_context)
        result = await scraper.fetch("https://dikidi.net/salon/456", "Студия")

    assert result is not None
    assert result.source == "dikidi"
    assert result.org_name == "Студия"
    assert result.fetched_from == "https://dikidi.net/salon/456"
    assert result.services == []


@pytest.mark.asyncio
async def test_dikidi_fetch_returns_none_on_exception():
    """DikidiScraper.fetch возвращает None при ошибке."""
    mock_context = AsyncMock()
    mock_context.new_page = AsyncMock(side_effect=Exception("browser error"))

    with patch("src.tools.pricescout.scrapers.dikidi.detect_captcha", return_value=False), \
         patch("src.tools.pricescout.scrapers.dikidi.random_delay", new=AsyncMock()):
        scraper = DikidiScraper(mock_context)
        result = await scraper.fetch("https://dikidi.net/salon/456")

    assert result is None


@pytest.mark.asyncio
async def test_dikidi_fetch_empty_org_name():
    """DikidiScraper.fetch работает без указания org_name."""
    mock_page = AsyncMock()
    mock_page.goto = AsyncMock()
    mock_page.wait_for_selector = AsyncMock(side_effect=Exception("not found"))
    mock_page.query_selector_all = AsyncMock(return_value=[])
    mock_page.close = AsyncMock()

    mock_context = AsyncMock()
    mock_context.new_page = AsyncMock(return_value=mock_page)

    with patch("src.tools.pricescout.scrapers.dikidi.detect_captcha", return_value=False), \
         patch("src.tools.pricescout.scrapers.dikidi.random_delay", new=AsyncMock()):
        scraper = DikidiScraper(mock_context)
        result = await scraper.fetch("https://dikidi.net/salon/456")

    assert result is not None
    assert result.org_name == ""


@pytest.mark.asyncio
async def test_dikidi_fetch_captcha_handling():
    """DikidiScraper.fetch обрабатывает капчу."""
    mock_page = AsyncMock()
    mock_page.goto = AsyncMock()
    mock_page.wait_for_selector = AsyncMock(side_effect=Exception("not found"))
    mock_page.query_selector_all = AsyncMock(return_value=[])
    mock_page.close = AsyncMock()

    mock_context = AsyncMock()
    mock_context.new_page = AsyncMock(return_value=mock_page)

    with patch("src.tools.pricescout.scrapers.dikidi.detect_captcha", return_value=True), \
         patch("src.tools.pricescout.scrapers.dikidi.wait_for_captcha_solve", new=AsyncMock()), \
         patch("src.tools.pricescout.scrapers.dikidi.random_delay", new=AsyncMock()):
        scraper = DikidiScraper(mock_context)
        result = await scraper.fetch("https://dikidi.net/salon/456", "Тест")

    # Должен вернуть PriceList (даже пустой) после решения капчи
    assert result is not None
