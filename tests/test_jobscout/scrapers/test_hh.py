"""Тесты скрапера hh.ru."""

from unittest.mock import AsyncMock, patch

import pytest

from src.tools.jobscout.scrapers.hh import HhScraper, get_area_id, parse_vacancy


# ─── get_area_id ──────────────────────────────────────────────────────────────


def test_get_area_id_known_city():
    """Известный город возвращает числовой ID."""
    assert get_area_id("Уфа") == 99
    assert get_area_id("уфа") == 99
    assert get_area_id("Москва") == 1
    assert get_area_id("Санкт-Петербург") == 2


def test_get_area_id_unknown_city():
    """Неизвестный город возвращает None."""
    assert get_area_id("Несуществующий") is None
    assert get_area_id("") is None


def test_get_area_id_case_insensitive():
    """Поиск нечувствителен к регистру."""
    assert get_area_id("МОСКВА") == 1
    assert get_area_id("казань") == 88


# ─── parse_vacancy ────────────────────────────────────────────────────────────


def _make_hh_item(**kwargs) -> dict:
    """Построить минимальный элемент API hh.ru."""
    base = {
        "id": "12345",
        "name": "Мастер маникюра",
        "alternate_url": "https://hh.ru/vacancy/12345",
        "salary": None,
        "employer": {"name": "Студия Colorstar", "alternate_url": "https://hh.ru/employer/1"},
        "area": {"id": "99", "name": "Уфа"},
        "address": None,
        "snippet": {"responsibility": "Маникюр и педикюр", "requirement": "Опыт от 1 года"},
        "experience": {"id": "between1And3", "name": "1–3 года"},
        "employment": {"id": "full", "name": "Полная занятость"},
        "schedule": {"id": "fullDay", "name": "Полный день"},
        "published_at": "2026-03-01T10:00:00+0000",
    }
    base.update(kwargs)
    return base


def test_parse_vacancy_basic():
    """parse_vacancy правильно разбирает элемент API."""
    item = _make_hh_item()
    v = parse_vacancy(item)

    assert v.source == "hh"
    assert v.source_url == "https://hh.ru/vacancy/12345"
    assert v.title == "Мастер маникюра"
    assert v.company_name == "Студия Colorstar"
    assert v.city == "Уфа"
    assert v.experience == "1–3 года"
    assert v.employment == "Полная занятость"
    assert v.schedule == "Полный день"
    assert v.description == "Маникюр и педикюр"
    assert v.requirements == "Опыт от 1 года"


def test_parse_vacancy_with_salary():
    """parse_vacancy правильно извлекает зарплату."""
    item = _make_hh_item(salary={"from": 40_000, "to": 60_000, "currency": "RUR"})
    v = parse_vacancy(item)

    assert v.salary_from == 40_000
    assert v.salary_to == 60_000
    assert v.salary_currency == "RUR"


def test_parse_vacancy_salary_none():
    """parse_vacancy корректно обрабатывает отсутствие зарплаты."""
    item = _make_hh_item(salary=None)
    v = parse_vacancy(item)

    assert v.salary_from is None
    assert v.salary_to is None
    assert v.salary_currency is None


def test_parse_vacancy_no_employer():
    """parse_vacancy работает при отсутствии employer."""
    item = _make_hh_item(employer=None)
    v = parse_vacancy(item)

    assert v.company_name is None
    assert v.company_url is None


def test_parse_vacancy_with_address():
    """parse_vacancy извлекает адрес из address.raw."""
    item = _make_hh_item(address={"raw": "ул. Ленина, 1, Уфа", "city": "Уфа"})
    v = parse_vacancy(item)

    assert v.address == "ул. Ленина, 1, Уфа"


# ─── HhScraper.search ─────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_hh_scraper_search_basic():
    """HhScraper.search возвращает список Vacancy."""
    api_response = {
        "items": [_make_hh_item(), _make_hh_item(id="67890", name="Администратор")],
        "found": 2,
        "pages": 1,
        "per_page": 100,
        "page": 0,
    }

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.get_json = AsyncMock(return_value=api_response)

    with patch("src.tools.jobscout.scrapers.hh.HttpClient", return_value=mock_client):
        scraper = HhScraper()
        results = await scraper.search("маникюр", "Уфа", max_results=10)

    assert len(results) == 2
    assert results[0].title == "Мастер маникюра"
    assert results[1].title == "Администратор"


@pytest.mark.asyncio
async def test_hh_scraper_search_empty_response():
    """HhScraper.search возвращает пустой список при пустом ответе API."""
    api_response = {"items": [], "found": 0, "pages": 0, "per_page": 100, "page": 0}

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.get_json = AsyncMock(return_value=api_response)

    with patch("src.tools.jobscout.scrapers.hh.HttpClient", return_value=mock_client):
        scraper = HhScraper()
        results = await scraper.search("несуществующий запрос", "Уфа")

    assert results == []


@pytest.mark.asyncio
async def test_hh_scraper_search_pagination():
    """HhScraper.search пагинирует при нескольких страницах."""
    page0 = {
        "items": [_make_hh_item(id=str(i), name=f"Вакансия {i}") for i in range(3)],
        "found": 5,
        "pages": 2,
        "per_page": 3,
        "page": 0,
    }
    page1 = {
        "items": [_make_hh_item(id=str(i + 3), name=f"Вакансия {i + 3}") for i in range(2)],
        "found": 5,
        "pages": 2,
        "per_page": 3,
        "page": 1,
    }

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.get_json = AsyncMock(side_effect=[page0, page1])

    with patch("src.tools.jobscout.scrapers.hh.HttpClient", return_value=mock_client):
        scraper = HhScraper()
        results = await scraper.search("маникюр", "Уфа", max_results=10)

    assert len(results) == 5


@pytest.mark.asyncio
async def test_hh_scraper_search_respects_max_results():
    """HhScraper.search не возвращает больше max_results."""
    items = [_make_hh_item(id=str(i)) for i in range(10)]
    api_response = {"items": items, "found": 10, "pages": 1, "per_page": 100, "page": 0}

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.get_json = AsyncMock(return_value=api_response)

    with patch("src.tools.jobscout.scrapers.hh.HttpClient", return_value=mock_client):
        scraper = HhScraper()
        results = await scraper.search("маникюр", "Уфа", max_results=5)

    assert len(results) == 5


@pytest.mark.asyncio
async def test_hh_scraper_search_unknown_city():
    """HhScraper.search работает при неизвестном городе (без area-фильтра)."""
    api_response = {"items": [_make_hh_item()], "found": 1, "pages": 1, "per_page": 100, "page": 0}

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.get_json = AsyncMock(return_value=api_response)

    with patch("src.tools.jobscout.scrapers.hh.HttpClient", return_value=mock_client):
        scraper = HhScraper()
        results = await scraper.search("маникюр", "НеизвестныйГород")

    assert len(results) == 1
    # Запрос выполнен без параметра area
    call_params = mock_client.get_json.call_args[1]["params"]
    assert "area" not in call_params


@pytest.mark.asyncio
async def test_hh_scraper_search_api_error():
    """HhScraper.search возвращает пустой список при ошибке API."""
    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.get_json = AsyncMock(side_effect=Exception("Connection error"))

    with patch("src.tools.jobscout.scrapers.hh.HttpClient", return_value=mock_client):
        scraper = HhScraper()
        results = await scraper.search("маникюр", "Уфа")

    assert results == []
