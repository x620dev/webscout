"""Тесты скрапера ЕГРЮЛ (nalog.ru)."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.tools.legalscout.scrapers.egrul import (
    EgrulScraper,
    get_region_code,
    parse_egrul_item,
)


# ─── get_region_code ──────────────────────────────────────────────────────────


def test_get_region_code_known_city():
    """Известный город возвращает код региона."""
    assert get_region_code("Уфа") == "02"
    assert get_region_code("уфа") == "02"
    assert get_region_code("Москва") == "77"
    assert get_region_code("Санкт-Петербург") == "78"


def test_get_region_code_unknown_city():
    """Неизвестный город возвращает пустую строку."""
    assert get_region_code("Несуществующий") == ""
    assert get_region_code("") == ""


def test_get_region_code_case_insensitive():
    """Поиск нечувствителен к регистру."""
    assert get_region_code("КАЗАНЬ") == "16"
    assert get_region_code("екатеринбург") == "66"


# ─── parse_egrul_item ─────────────────────────────────────────────────────────


def _make_egrul_row(**kwargs) -> dict:
    """Построить минимальную строку ответа ЕГРЮЛ nalog.ru."""
    base = {
        "n": 'ООО "КОЛОРСТАР"',
        "c": "Уфа",
        "r": "0277",
        "i": "0277123456",
        "g": "1027700000000",
        "k": "1",
        "p": "15.04.2010",
        "a": "Республика Башкортостан, г. Уфа, ул. Ленина, д. 1",
        "o": "86.90",
    }
    base.update(kwargs)
    return base


def test_parse_egrul_item_basic():
    """parse_egrul_item правильно разбирает строку ЕГРЮЛ."""
    row = _make_egrul_row()
    entity = parse_egrul_item(row)

    assert entity.source == "egrul"
    assert entity.name == 'ООО "КОЛОРСТАР"'
    assert entity.inn == "0277123456"
    assert entity.ogrn == "1027700000000"
    assert entity.registration_date == "15.04.2010"
    assert entity.address == "Республика Башкортостан, г. Уфа, ул. Ленина, д. 1"
    assert entity.main_activity == "86.90"


def test_parse_egrul_item_active_status():
    """parse_egrul_item правильно разбирает статус 'действующее'."""
    row = _make_egrul_row(k="1")
    entity = parse_egrul_item(row)
    assert entity.status == "действующее"


def test_parse_egrul_item_liquidated_status():
    """parse_egrul_item правильно разбирает статус 'ликвидировано'."""
    row = _make_egrul_row(k="0")
    entity = parse_egrul_item(row)
    assert entity.status == "ликвидировано"


def test_parse_egrul_item_unknown_status():
    """parse_egrul_item возвращает None при неизвестном статусе."""
    row = _make_egrul_row(k="9")
    entity = parse_egrul_item(row)
    assert entity.status is None


def test_parse_egrul_item_empty_ogrn():
    """parse_egrul_item обрабатывает пустой ОГРН."""
    row = _make_egrul_row(g="")
    entity = parse_egrul_item(row)
    assert entity.ogrn is None


def test_parse_egrul_item_missing_fields():
    """parse_egrul_item работает при минимальном наборе полей."""
    entity = parse_egrul_item({"n": "ООО Тест", "i": "1234567890"})
    assert entity.name == "ООО Тест"
    assert entity.inn == "1234567890"
    assert entity.ogrn is None
    assert entity.address is None
    assert entity.status is None


# ─── EgrulScraper ─────────────────────────────────────────────────────────────


def _make_async_client(token_response: dict, search_response: dict):
    """Создать мок httpx.AsyncClient для двухшагового запроса."""
    # POST ответ (токен)
    post_response = MagicMock()
    post_response.raise_for_status = MagicMock()
    post_response.json = MagicMock(return_value=token_response)

    # GET ответ (результаты)
    get_response = MagicMock()
    get_response.raise_for_status = MagicMock()
    get_response.json = MagicMock(return_value=search_response)

    client = AsyncMock()
    client.post = AsyncMock(return_value=post_response)
    client.get = AsyncMock(return_value=get_response)
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=False)
    return client


@pytest.mark.asyncio
async def test_egrul_scraper_search_basic():
    """EgrulScraper.search возвращает список LegalEntity."""
    token_resp = {"t": "test-token-123"}
    search_resp = {
        "rows": [_make_egrul_row(), _make_egrul_row(i="0277654321", n="ООО Другая")],
        "total": 2,
        "cnt": 2,
    }

    mock_client = _make_async_client(token_resp, search_resp)

    with patch("src.tools.legalscout.scrapers.egrul.httpx.AsyncClient", return_value=mock_client):
        scraper = EgrulScraper()
        results = await scraper.search(name="Колорстар", city="Уфа")

    assert len(results) == 2
    assert results[0].inn == "0277123456"
    assert results[1].inn == "0277654321"


@pytest.mark.asyncio
async def test_egrul_scraper_search_by_inn():
    """EgrulScraper.search ищет по ИНН если задан inn."""
    token_resp = {"t": "tok"}
    search_resp = {"rows": [_make_egrul_row()], "total": 1, "cnt": 1}

    mock_client = _make_async_client(token_resp, search_resp)

    with patch("src.tools.legalscout.scrapers.egrul.httpx.AsyncClient", return_value=mock_client):
        scraper = EgrulScraper()
        results = await scraper.search(inn="0277123456")

    assert len(results) == 1
    # При поиске по ИНН регион не передаётся
    post_call = mock_client.post.call_args
    assert post_call[1]["data"]["region"] == ""


@pytest.mark.asyncio
async def test_egrul_scraper_search_empty():
    """EgrulScraper.search возвращает пустой список при пустом ответе."""
    token_resp = {"t": "tok"}
    search_resp = {"rows": [], "total": 0, "cnt": 0}

    mock_client = _make_async_client(token_resp, search_resp)

    with patch("src.tools.legalscout.scrapers.egrul.httpx.AsyncClient", return_value=mock_client):
        scraper = EgrulScraper()
        results = await scraper.search(name="НесуществующаяКомпания")

    assert results == []


@pytest.mark.asyncio
async def test_egrul_scraper_no_query():
    """EgrulScraper.search возвращает пустой список без запроса."""
    scraper = EgrulScraper()
    results = await scraper.search()
    assert results == []


@pytest.mark.asyncio
async def test_egrul_scraper_token_failure():
    """EgrulScraper.search возвращает пустой список если токен не получен."""
    token_resp = {}  # нет поля "t"
    search_resp = {"rows": [], "total": 0}

    mock_client = _make_async_client(token_resp, search_resp)

    with patch("src.tools.legalscout.scrapers.egrul.httpx.AsyncClient", return_value=mock_client):
        scraper = EgrulScraper()
        results = await scraper.search(name="Тест")

    assert results == []


@pytest.mark.asyncio
async def test_egrul_scraper_http_error():
    """EgrulScraper.search возвращает пустой список при HTTP-ошибке."""
    import httpx

    client = AsyncMock()
    client.post = AsyncMock(side_effect=httpx.RequestError("Ошибка соединения"))
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=False)

    with patch("src.tools.legalscout.scrapers.egrul.httpx.AsyncClient", return_value=client):
        scraper = EgrulScraper()
        results = await scraper.search(name="Тест")

    assert results == []


@pytest.mark.asyncio
async def test_egrul_scraper_respects_max_results():
    """EgrulScraper.search не возвращает больше max_results."""
    token_resp = {"t": "tok"}
    rows = [_make_egrul_row(i=str(i), n=f"ООО {i}") for i in range(10)]
    search_resp = {"rows": rows, "total": 10, "cnt": 10}

    mock_client = _make_async_client(token_resp, search_resp)

    with patch("src.tools.legalscout.scrapers.egrul.httpx.AsyncClient", return_value=mock_client):
        scraper = EgrulScraper()
        results = await scraper.search(name="Тест", max_results=3)

    assert len(results) == 3
