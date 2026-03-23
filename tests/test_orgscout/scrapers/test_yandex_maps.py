"""Тесты для YandexMapsScraper (tools/orgscout/scrapers/yandex_maps.py)."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.core.config import ScrapingConfig
from src.core.models import GeoPoint
from src.tools.orgscout.scrapers.yandex_maps import (
    YandexMapsScraper,
    _extract_geo_from_url,
)


# ─── Вспомогательные фикстуры ─────────────────────────────────────────────────


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
    ctx = AsyncMock()
    return ctx


# ─── _extract_geo_from_url ─────────────────────────────────────────────────────


def test_extract_geo_from_url_valid():
    """Корректно извлекает координаты из URL Яндекс.Карт."""
    url = "https://yandex.ru/maps/org/colorstar/1/?ll=55.958&z=16/@54.735152,55.958736"
    result = _extract_geo_from_url(url)
    assert result is not None
    assert isinstance(result, GeoPoint)
    assert result.lat == pytest.approx(54.735152)
    assert result.lon == pytest.approx(55.958736)


def test_extract_geo_from_url_no_coords():
    """Возвращает None если координат нет в URL."""
    url = "https://yandex.ru/maps/org/test/1/"
    assert _extract_geo_from_url(url) is None


def test_extract_geo_from_url_malformed():
    """Не бросает исключение при некорректном URL."""
    assert _extract_geo_from_url("not-a-url") is None
    assert _extract_geo_from_url("") is None


# ─── YandexMapsScraper.__init__ ───────────────────────────────────────────────


def test_scraper_init_default_config(mock_context):
    """Скрапер инициализируется с дефолтным конфигом."""
    scraper = YandexMapsScraper(mock_context)
    assert scraper._config is not None
    assert isinstance(scraper._config, ScrapingConfig)


def test_scraper_init_custom_config(mock_context, scraping_config):
    """Скрапер принимает пользовательский конфиг."""
    scraper = YandexMapsScraper(mock_context, scraping_config)
    assert scraper._config.delay_min == 0.0


# ─── _parse_org_card ──────────────────────────────────────────────────────────


async def test_parse_org_card_returns_organization(mock_context, scraping_config):
    """_parse_org_card возвращает Organization с именем."""
    scraper = YandexMapsScraper(mock_context, scraping_config)

    mock_page = AsyncMock()
    mock_page.url = "https://yandex.ru/maps/org/colorstar/1/@54.7,55.9"
    mock_page.eval_on_selector_all = AsyncMock(return_value=["+79991234567"])

    # Мокаем _text и _texts
    async def fake_text(page, selector):
        if "name" in selector or "header" in selector:
            return "Colorstar"
        if "address" in selector:
            return "ул. Ленина, 1"
        if "hours" in selector or "schedule" in selector:
            return "Пн–Пт 9:00–20:00"
        return None

    async def fake_texts(page, selector):
        if "categor" in selector:
            return ["Маникюр", "Педикюр"]
        return []

    async def fake_attr(page, selector, attr):
        if "website" in selector or "link" in selector.lower():
            return "https://example.com"
        if "yclients" in selector:
            return "https://yclients.com/company/123"
        return None

    async def fake_rating(page, selector):
        return 4.8

    async def fake_count(page, selector):
        return 120

    scraper._text = fake_text
    scraper._texts = fake_texts
    scraper._attr = fake_attr
    scraper._parse_rating = fake_rating
    scraper._parse_count = fake_count

    org = await scraper._parse_org_card(mock_page, "https://yandex.ru/maps/org/colorstar/1/")
    assert org is not None
    assert org.name == "Colorstar"
    assert org.address == "ул. Ленина, 1"
    assert org.source == "yandex_maps"


async def test_parse_org_card_no_name_returns_none(mock_context, scraping_config):
    """_parse_org_card возвращает None если имя не найдено."""
    scraper = YandexMapsScraper(mock_context, scraping_config)
    mock_page = AsyncMock()
    mock_page.url = "https://yandex.ru/maps/org/1/"

    async def no_name(page, selector):
        return None

    async def empty_list(page, selector):
        return []

    async def no_attr(page, selector, attr):
        return None

    async def no_rating(page, selector):
        return None

    async def no_count(page, selector):
        return None

    scraper._text = no_name
    scraper._texts = empty_list
    scraper._attr = no_attr
    scraper._parse_rating = no_rating
    scraper._parse_count = no_count

    result = await scraper._parse_org_card(mock_page, "https://yandex.ru/maps/org/1/")
    assert result is None


# ─── fetch (интеграция с _parse_org_card) ────────────────────────────────────


async def test_fetch_captcha_no_retry(mock_context, scraping_config):
    """fetch возвращает None при капче если retry_on_captcha=False."""
    scraping_config.retry_on_captcha = False
    scraper = YandexMapsScraper(mock_context, scraping_config)

    mock_page = AsyncMock()
    mock_context.new_page = AsyncMock(return_value=mock_page)
    mock_page.goto = AsyncMock()
    mock_page.close = AsyncMock()

    with patch("src.tools.orgscout.scrapers.yandex_maps.detect_captcha", return_value=True), \
         patch("src.tools.orgscout.scrapers.yandex_maps.random_delay"):
        result = await scraper.fetch("https://yandex.ru/maps/org/test/1/")

    assert result is None


async def test_fetch_exception_returns_none(mock_context, scraping_config):
    """fetch возвращает None при исключении (не бросает)."""
    scraper = YandexMapsScraper(mock_context, scraping_config)

    mock_page = AsyncMock()
    mock_context.new_page = AsyncMock(return_value=mock_page)
    mock_page.goto = AsyncMock(side_effect=Exception("Network error"))
    mock_page.close = AsyncMock()

    with patch("src.tools.orgscout.scrapers.yandex_maps.random_delay"):
        result = await scraper.fetch("https://yandex.ru/maps/org/test/1/")

    assert result is None


# ─── _collect_card_urls ───────────────────────────────────────────────────────


async def test_collect_card_urls_limit(mock_context, scraping_config):
    """_collect_card_urls не превышает лимит."""
    scraper = YandexMapsScraper(mock_context, scraping_config)

    mock_page = AsyncMock()
    # Возвращаем 10 ссылок сразу, потом ничего нового
    call_count = 0

    async def fake_eval(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return [f"https://yandex.ru/maps/org/item{i}/" for i in range(10)]
        return [f"https://yandex.ru/maps/org/item{i}/" for i in range(10)]

    mock_page.eval_on_selector_all = fake_eval
    mock_page.eval_on_selector = AsyncMock()

    with patch("src.tools.orgscout.scrapers.yandex_maps.random_delay"):
        urls = await scraper._collect_card_urls(mock_page, limit=5)

    assert len(urls) <= 5


async def test_collect_card_urls_deduplicates(mock_context, scraping_config):
    """_collect_card_urls не возвращает дубликаты."""
    scraper = YandexMapsScraper(mock_context, scraping_config)

    mock_page = AsyncMock()
    call_count = 0

    async def fake_eval(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if "eval_on_selector_all" in str(args):
            return ["https://yandex.ru/maps/org/item1/", "https://yandex.ru/maps/org/item1/"]
        return None

    mock_page.eval_on_selector_all = AsyncMock(
        return_value=["https://yandex.ru/maps/org/item1/", "https://yandex.ru/maps/org/item1/"]
    )
    mock_page.eval_on_selector = AsyncMock()

    with patch("src.tools.orgscout.scrapers.yandex_maps.random_delay"):
        urls = await scraper._collect_card_urls(mock_page, limit=50)

    assert len(urls) == len(set(urls))
