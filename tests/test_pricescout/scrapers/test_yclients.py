"""Тесты скрапера YCLIENTS."""

import pytest

from src.tools.pricescout.scrapers.yclients import YclientsScraper, parse_price_text
from unittest.mock import AsyncMock, MagicMock, patch


# ─── parse_price_text ─────────────────────────────────────────────────────────


def test_parse_price_exact():
    """Точная цена → price=X, price_from=None, price_to=None."""
    assert parse_price_text("800 ₽") == (800, None, None)
    assert parse_price_text("1500₽") == (1500, None, None)
    assert parse_price_text("2 000 руб") == (2000, None, None)


def test_parse_price_range():
    """Диапазон цен → price=None, price_from=X, price_to=Y."""
    price, pf, pt = parse_price_text("1 500 - 2 000 ₽")
    assert price is None
    assert pf == 1500
    assert pt == 2000


def test_parse_price_from():
    """Цена «от» → price_from=X, price_to=None."""
    price, pf, pt = parse_price_text("от 1 500 ₽")
    assert price is None
    assert pf == 1500
    assert pt is None


def test_parse_price_to():
    """Цена «до» → price_to=X, price_from=None."""
    price, pf, pt = parse_price_text("до 2 000 ₽")
    assert price is None
    assert pf is None
    assert pt == 2000


def test_parse_price_free():
    """Бесплатно → price=0."""
    price, pf, pt = parse_price_text("бесплатно")
    assert price == 0
    assert pf is None
    assert pt is None


def test_parse_price_contract():
    """По договорённости → все None."""
    assert parse_price_text("по договорённости") == (None, None, None)
    assert parse_price_text("договорная") == (None, None, None)


def test_parse_price_empty():
    """Пустая строка → все None."""
    assert parse_price_text("") == (None, None, None)
    assert parse_price_text("   ") == (None, None, None)


def test_parse_price_no_numbers():
    """Текст без чисел → все None."""
    assert parse_price_text("цена уточняйте") == (None, None, None)


def test_parse_price_non_breaking_space():
    """Неразрывный пробел в числах обрабатывается корректно."""
    price, _, _ = parse_price_text("1\xa0500\xa0₽")
    assert price == 1500


# ─── YclientsScraper ──────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_yclients_fetch_returns_price_list():
    """YclientsScraper.fetch возвращает PriceList."""
    mock_page = AsyncMock()
    mock_page.goto = AsyncMock()
    mock_page.wait_for_selector = AsyncMock(side_effect=Exception("not found"))
    mock_page.query_selector_all = AsyncMock(return_value=[])
    mock_page.close = AsyncMock()

    mock_context = AsyncMock()
    mock_context.new_page = AsyncMock(return_value=mock_page)

    with patch("src.tools.pricescout.scrapers.yclients.detect_captcha", return_value=False), \
         patch("src.tools.pricescout.scrapers.yclients.random_delay", new=AsyncMock()):
        scraper = YclientsScraper(mock_context)
        result = await scraper.fetch("https://yclients.com/company/123/", "Студия")

    assert result is not None
    assert result.source == "yclients"
    assert result.org_name == "Студия"
    assert result.fetched_from == "https://yclients.com/company/123/"
    assert result.services == []


@pytest.mark.asyncio
async def test_yclients_fetch_returns_none_on_exception():
    """YclientsScraper.fetch возвращает None при ошибке."""
    mock_context = AsyncMock()
    mock_context.new_page = AsyncMock(side_effect=Exception("browser error"))

    with patch("src.tools.pricescout.scrapers.yclients.detect_captcha", return_value=False), \
         patch("src.tools.pricescout.scrapers.yclients.random_delay", new=AsyncMock()):
        scraper = YclientsScraper(mock_context)
        result = await scraper.fetch("https://yclients.com/company/123/")

    assert result is None


@pytest.mark.asyncio
async def test_yclients_fetch_with_services():
    """YclientsScraper.fetch возвращает услуги из DOM."""
    # Мокируем категорию с одной услугой
    mock_name_el = AsyncMock()
    mock_name_el.inner_text = AsyncMock(return_value="Маникюр без покрытия")

    mock_price_el = AsyncMock()
    mock_price_el.inner_text = AsyncMock(return_value="800 ₽")

    mock_item_el = AsyncMock()
    mock_item_el.query_selector = AsyncMock(side_effect=_make_item_query_selector(
        mock_name_el, mock_price_el, None
    ))
    mock_item_el.inner_text = AsyncMock(return_value="Маникюр без покрытия\n800 ₽")

    mock_title_el = AsyncMock()
    mock_title_el.inner_text = AsyncMock(return_value="Маникюр")

    mock_cat_el = AsyncMock()
    mock_cat_el.query_selector = AsyncMock(return_value=mock_title_el)
    mock_cat_el.query_selector_all = AsyncMock(return_value=[mock_item_el])

    mock_page = AsyncMock()
    mock_page.goto = AsyncMock()
    mock_page.wait_for_selector = AsyncMock()
    mock_page.close = AsyncMock()
    # query_selector_all: первый вызов для категорий → [mock_cat_el], остальные → []
    call_count = {"n": 0}

    async def mock_qsa(selector):
        if call_count["n"] == 0:
            call_count["n"] += 1
            return [mock_cat_el]
        return []

    mock_page.query_selector_all = mock_qsa

    mock_context = AsyncMock()
    mock_context.new_page = AsyncMock(return_value=mock_page)

    with patch("src.tools.pricescout.scrapers.yclients.detect_captcha", return_value=False), \
         patch("src.tools.pricescout.scrapers.yclients.random_delay", new=AsyncMock()):
        scraper = YclientsScraper(mock_context)
        result = await scraper.fetch("https://yclients.com/company/123/", "Студия")

    assert result is not None
    assert len(result.services) == 1
    assert result.services[0].name == "Маникюр без покрытия"
    assert result.services[0].price == 800
    assert result.services[0].category == "Маникюр"


def _make_item_query_selector(name_el, price_el, duration_el):
    """Вспомогательная функция для мокирования query_selector элемента услуги."""
    _name_selectors = {
        ".service_title", ".service_name", ".services-item__title",
    }

    async def _qsel(selector):
        if any(name_sel in selector for name_sel in ("title", "name")):
            return name_el
        if "price" in selector:
            return price_el
        if "duration" in selector:
            return duration_el
        return None

    return _qsel
