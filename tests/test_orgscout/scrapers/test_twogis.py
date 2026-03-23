"""Тесты для TwoGisScraper (tools/orgscout/scrapers/twogis.py)."""

from unittest.mock import AsyncMock, patch

import pytest

from src.core.config import ScrapingConfig
from src.core.models import GeoPoint
from src.tools.orgscout.scrapers.twogis import (
    TwoGisScraper,
    _CITY_SLUGS,
    get_city_slug,
    parse_api_item,
)


# ─── Фикстуры ─────────────────────────────────────────────────────────────────


@pytest.fixture
def scraping_config():
    return ScrapingConfig(
        delay_min=0.0,
        delay_max=0.0,
        scroll_pause=0.0,
        page_load_timeout=5,
        retry_on_captcha=False,
        captcha_timeout=5,
    )


@pytest.fixture
def mock_context():
    return AsyncMock()


# ─── get_city_slug ─────────────────────────────────────────────────────────────


def test_get_city_slug_known():
    """Возвращает корректный slug для известных городов."""
    assert get_city_slug("Уфа") == "ufa"
    assert get_city_slug("Москва") == "moscow"
    assert get_city_slug("Санкт-Петербург") == "spb"
    assert get_city_slug("Казань") == "kazan"


def test_get_city_slug_case_insensitive():
    """Регистр не важен при поиске slug."""
    assert get_city_slug("УФА") == "ufa"
    assert get_city_slug("уфа") == "ufa"


def test_get_city_slug_unknown():
    """Для неизвестного города возвращает нормализованное название."""
    result = get_city_slug("Урюпинск")
    assert result == "урюпинск"


def test_city_slugs_table_completeness():
    """Таблица slug-городов содержит основные города."""
    expected = {"москва", "санкт-петербург", "казань", "уфа", "екатеринбург"}
    assert expected.issubset(_CITY_SLUGS.keys())


# ─── parse_api_item ────────────────────────────────────────────────────────────


def test_parse_api_item_minimal():
    """parse_api_item парсит минимальный элемент API."""
    item = {
        "id": "12345",
        "name": "Colorstar Nail Studio",
    }
    org = parse_api_item(item)
    assert org is not None
    assert org.name == "Colorstar Nail Studio"
    assert org.source == "twogis"
    assert "12345" in org.source_url


def test_parse_api_item_no_name_returns_none():
    """parse_api_item возвращает None если нет имени."""
    assert parse_api_item({}) is None
    assert parse_api_item({"id": "123"}) is None


def test_parse_api_item_full():
    """parse_api_item парсит полный элемент API."""
    item = {
        "id": "42",
        "name": "Студия маникюра",
        "address": {"name": "ул. Ленина, 1, Уфа"},
        "point": {"lat": 54.735, "lon": 55.958},
        "rubrics": [{"name": "Маникюр"}, {"name": "Педикюр"}],
        "contact_groups": [
            {
                "contacts": [
                    {"type": "phone", "value": "+79991234567"},
                    {"type": "website", "value": "https://example.com"},
                ]
            }
        ],
        "reviews": {"rating": 4.8, "count": 150},
        "links": [{"value": "https://yclients.com/company/123"}],
    }
    org = parse_api_item(item)
    assert org is not None
    assert org.name == "Студия маникюра"
    assert org.address == "ул. Ленина, 1, Уфа"
    assert org.geo is not None
    assert org.geo.lat == pytest.approx(54.735)
    assert org.geo.lon == pytest.approx(55.958)
    assert org.categories == ["Маникюр", "Педикюр"]
    assert "+79991234567" in org.contacts.phone
    assert org.contacts.website == "https://example.com"
    assert org.rating == pytest.approx(4.8)
    assert org.reviews_count == 150
    assert org.online_booking == "https://yclients.com/company/123"


def test_parse_api_item_address_string():
    """parse_api_item обрабатывает address как строку."""
    item = {
        "name": "Студия",
        "address": "ул. Пушкина, 10",
    }
    org = parse_api_item(item)
    assert org is not None
    assert org.address == "ул. Пушкина, 10"


def test_parse_api_item_address_empty():
    """parse_api_item обрабатывает отсутствующий address."""
    item = {"name": "Студия"}
    org = parse_api_item(item)
    assert org is not None
    assert org.address == ""


def test_parse_api_item_invalid_geo():
    """parse_api_item не падает при некорректных координатах."""
    item = {
        "name": "Студия",
        "point": {"lat": "invalid", "lon": None},
    }
    org = parse_api_item(item)
    assert org is not None
    assert org.geo is None


def test_parse_api_item_dikidi_booking():
    """parse_api_item определяет Dikidi в поле online_booking."""
    item = {
        "name": "Студия",
        "links": [{"value": "https://dikidi.net/salon/456"}],
    }
    org = parse_api_item(item)
    assert org is not None
    assert org.online_booking == "https://dikidi.net/salon/456"


def test_parse_api_item_multiple_phones():
    """parse_api_item собирает несколько телефонов."""
    item = {
        "name": "Студия",
        "contact_groups": [
            {
                "contacts": [
                    {"type": "phone", "value": "+79991111111"},
                    {"type": "phone", "value": "+79992222222"},
                ]
            }
        ],
    }
    org = parse_api_item(item)
    assert org is not None
    assert len(org.contacts.phone) == 2


def test_parse_api_item_rating_zero():
    """parse_api_item обрабатывает нулевой рейтинг."""
    item = {
        "name": "Студия",
        "reviews": {"rating": 0, "count": 0},
    }
    org = parse_api_item(item)
    assert org is not None
    assert org.rating == pytest.approx(0.0)
    assert org.reviews_count == 0


def test_parse_api_item_custom_url():
    """parse_api_item использует кастомный URL если указан."""
    item = {
        "name": "Студия",
        "url": "https://2gis.ru/firm/special",
    }
    org = parse_api_item(item)
    assert org is not None
    assert org.source_url == "https://2gis.ru/firm/special"


# ─── TwoGisScraper.__init__ ───────────────────────────────────────────────────


def test_scraper_init_default_config(mock_context):
    """Скрапер инициализируется с дефолтным конфигом."""
    scraper = TwoGisScraper(mock_context)
    assert isinstance(scraper._config, ScrapingConfig)


def test_scraper_init_custom_config(mock_context, scraping_config):
    """Скрапер принимает кастомный конфиг."""
    scraper = TwoGisScraper(mock_context, scraping_config)
    assert scraper._config.delay_min == 0.0


# ─── fetch ────────────────────────────────────────────────────────────────────


async def test_fetch_captcha_no_retry(mock_context, scraping_config):
    """fetch возвращает None при капче если retry_on_captcha=False."""
    scraper = TwoGisScraper(mock_context, scraping_config)

    mock_page = AsyncMock()
    mock_context.new_page = AsyncMock(return_value=mock_page)
    mock_page.goto = AsyncMock()
    mock_page.close = AsyncMock()

    with patch("src.tools.orgscout.scrapers.twogis.detect_captcha", return_value=True), \
         patch("src.tools.orgscout.scrapers.twogis.random_delay"), \
         patch("src.tools.orgscout.scrapers.twogis._attach_interceptor"):
        result = await scraper.fetch("https://2gis.ru/firm/123")

    assert result is None


async def test_fetch_exception_returns_none(mock_context, scraping_config):
    """fetch не бросает исключение при ошибке сети."""
    scraper = TwoGisScraper(mock_context, scraping_config)

    mock_page = AsyncMock()
    mock_context.new_page = AsyncMock(return_value=mock_page)
    mock_page.goto = AsyncMock(side_effect=Exception("Connection refused"))
    mock_page.close = AsyncMock()

    with patch("src.tools.orgscout.scrapers.twogis.random_delay"), \
         patch("src.tools.orgscout.scrapers.twogis._attach_interceptor"):
        result = await scraper.fetch("https://2gis.ru/firm/123")

    assert result is None
