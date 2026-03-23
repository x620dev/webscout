"""Тесты скрапера Avito Jobs."""

import pytest

from src.tools.jobscout.scrapers.avito import _get_city_slug, _parse_salary


# ─── _get_city_slug ───────────────────────────────────────────────────────────


def test_get_city_slug_known():
    """Известный город возвращает правильный slug."""
    assert _get_city_slug("Уфа") == "ufa"
    assert _get_city_slug("Москва") == "moskva"
    assert _get_city_slug("Санкт-Петербург") == "sankt-peterburg"


def test_get_city_slug_case_insensitive():
    """_get_city_slug нечувствителен к регистру."""
    assert _get_city_slug("КАЗАНЬ") == "kazan"
    assert _get_city_slug("екатеринбург") == "ekaterinburg"


def test_get_city_slug_unknown_falls_back():
    """Неизвестный город → транслитерация через replace."""
    assert _get_city_slug("Неизвестный") == "neizvestnyy"


# ─── _parse_salary ────────────────────────────────────────────────────────────


def test_parse_salary_range():
    """Диапазон зарплат разбирается корректно."""
    lo, hi, cur = _parse_salary("40 000 – 60 000 ₽")
    assert lo == 40_000
    assert hi == 60_000
    assert cur == "RUR"


def test_parse_salary_from():
    """Зарплата «от» разбирается корректно."""
    lo, hi, cur = _parse_salary("от 35 000 ₽")
    assert lo == 35_000
    assert hi is None
    assert cur == "RUR"


def test_parse_salary_up_to():
    """Зарплата «до» разбирается корректно."""
    lo, hi, cur = _parse_salary("до 80 000 ₽")
    assert lo is None
    assert hi == 80_000
    assert cur == "RUR"


def test_parse_salary_negotiable():
    """«По договорённости» → все None."""
    lo, hi, cur = _parse_salary("по договорённости")
    assert lo is None
    assert hi is None
    assert cur is None


def test_parse_salary_usd():
    """Долларовая зарплата определяет валюту USD."""
    lo, hi, cur = _parse_salary("$2000")
    assert cur == "USD"


def test_parse_salary_nbsp():
    """Неразрывные пробелы корректно обрабатываются."""
    lo, hi, cur = _parse_salary("50\xa0000\u2013100\xa0000\u00a0₽")
    assert cur == "RUR"
    assert lo is not None


def test_parse_salary_empty():
    """Пустая строка возвращает None."""
    lo, hi, cur = _parse_salary("")
    assert lo is None
    assert hi is None
    assert cur is None


# ─── AvitoJobScraper (мок Playwright) ─────────────────────────────────────────


@pytest.mark.asyncio
async def test_avito_scraper_no_items(monkeypatch):
    """AvitoJobScraper возвращает пустой список если листинг не загружен."""
    from unittest.mock import AsyncMock, MagicMock

    from src.tools.jobscout.scrapers.avito import AvitoJobScraper

    mock_page = AsyncMock()
    mock_page.goto = AsyncMock()
    mock_page.wait_for_selector = AsyncMock(side_effect=Exception("timeout"))
    mock_page.close = AsyncMock()

    mock_context = AsyncMock()
    mock_context.new_page = AsyncMock(return_value=mock_page)

    # Мокаем detect_captcha и random_delay
    monkeypatch.setattr("src.tools.jobscout.scrapers.avito.detect_captcha", AsyncMock(return_value=False))
    monkeypatch.setattr("src.tools.jobscout.scrapers.avito.random_delay", AsyncMock())

    scraper = AvitoJobScraper(mock_context)
    results = await scraper.scrape("маникюр", "Уфа", max_results=10)

    assert results == []


@pytest.mark.asyncio
async def test_avito_scraper_parses_items(monkeypatch):
    """AvitoJobScraper возвращает Vacancy из найденных элементов."""
    from unittest.mock import AsyncMock, MagicMock, patch

    from src.tools.jobscout.models import Vacancy
    from src.tools.jobscout.scrapers.avito import AvitoJobScraper

    # Мок отдельного элемента листинга
    mock_title_el = AsyncMock()
    mock_title_el.inner_text = AsyncMock(return_value="Мастер маникюра")
    mock_title_el.get_attribute = AsyncMock(return_value="/ufa/vakansii/1234")

    mock_price_el = AsyncMock()
    mock_price_el.inner_text = AsyncMock(return_value="от 40 000 ₽")

    async def mock_query_selector(sel):
        if "item-title" in sel:
            return mock_title_el
        if "item-price" in sel:
            return mock_price_el
        return None

    mock_item = AsyncMock()
    mock_item.query_selector = AsyncMock(side_effect=mock_query_selector)

    mock_page = AsyncMock()
    mock_page.goto = AsyncMock()
    mock_page.wait_for_selector = AsyncMock()
    mock_page.query_selector_all = AsyncMock(return_value=[mock_item])
    mock_page.query_selector = AsyncMock(return_value=None)  # нет кнопки пагинации
    mock_page.close = AsyncMock()

    mock_context = AsyncMock()
    mock_context.new_page = AsyncMock(return_value=mock_page)

    monkeypatch.setattr("src.tools.jobscout.scrapers.avito.detect_captcha", AsyncMock(return_value=False))
    monkeypatch.setattr("src.tools.jobscout.scrapers.avito.random_delay", AsyncMock())

    scraper = AvitoJobScraper(mock_context)
    results = await scraper.scrape("маникюр", "Уфа", max_results=10)

    assert len(results) == 1
    assert results[0].title == "Мастер маникюра"
    assert results[0].salary_from == 40_000
    assert results[0].source == "avito"
    assert "avito.ru" in results[0].source_url
