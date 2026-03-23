"""Тесты MCP-сервера (src/mcp_server.py).

Тесты проверяют логику функций-инструментов напрямую,
минуя MCP-транспорт и внешние зависимости.
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Пропустить все тесты если mcp не установлен
pytestmark = pytest.mark.skipif(
    pytest.importorskip("mcp", reason="mcp не установлен") is None,
    reason="mcp не установлен",
)


def _skip_if_no_mcp() -> None:
    """Бросить Skip если mcp недоступен."""
    try:
        import mcp  # noqa: F401
    except ImportError:
        pytest.skip("mcp не установлен")


# ─── Вспомогательные фикстуры ─────────────────────────────────────────────────


def make_org(**kwargs) -> MagicMock:
    """Создать мок организации с методом model_dump."""
    org = MagicMock()
    data = {
        "source": "yandex-maps",
        "source_url": "https://yandex.ru/maps/org/test/1/",
        "name": "Салон Ромашка",
        "address": "г. Уфа, ул. Ленина, д. 1",
        "rating": 4.8,
    }
    data.update(kwargs)
    org.model_dump = MagicMock(return_value=data)
    return org


def make_vacancy(**kwargs) -> MagicMock:
    vacancy = MagicMock()
    data = {"title": "Мастер маникюра", "company": "Ромашка", "source": "hh"}
    data.update(kwargs)
    vacancy.model_dump = MagicMock(return_value=data)
    return vacancy


def make_legal(**kwargs) -> MagicMock:
    entity = MagicMock()
    data = {"name": 'ООО "РОМАШКА"', "inn": "0277123456", "source": "egrul"}
    data.update(kwargs)
    entity.model_dump = MagicMock(return_value=data)
    return entity


# ─── _to_json ─────────────────────────────────────────────────────────────────


def test_to_json_with_pydantic_models():
    """_to_json сериализует список Pydantic-моделей."""
    _skip_if_no_mcp()

    from src.mcp_server import _to_json

    items = [make_org(), make_org(name="Студия Роза")]
    result = _to_json(items)
    data = json.loads(result)
    assert len(data) == 2
    assert data[0]["name"] == "Салон Ромашка"
    assert data[1]["name"] == "Студия Роза"


def test_to_json_empty():
    """_to_json возвращает пустой массив для пустого списка."""
    _skip_if_no_mcp()

    from src.mcp_server import _to_json

    result = _to_json([])
    assert json.loads(result) == []


# ─── scrape_organizations ─────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_scrape_organizations_yandex():
    """scrape_organizations с source=yandex-maps возвращает JSON-массив."""
    _skip_if_no_mcp()

    from src.mcp_server import scrape_organizations

    orgs = [make_org(), make_org(name="Салон Лилия")]
    mock_scraper = AsyncMock()
    mock_scraper.scrape = AsyncMock(return_value=orgs)
    mock_ctx = AsyncMock()

    with (
        patch("src.mcp_server.load_config", return_value=MagicMock()),
        patch("src.mcp_server.BrowserManager") as mock_bm,
        patch("src.tools.orgscout.scrapers.yandex_maps.YandexMapsScraper", return_value=mock_scraper),
    ):
        mock_bm.return_value.__aenter__ = AsyncMock(return_value=MagicMock(
            new_context=AsyncMock(return_value=mock_ctx)
        ))
        mock_bm.return_value.__aexit__ = AsyncMock(return_value=None)

        result = await scrape_organizations("маникюр", "Уфа", source="yandex-maps", max_results=10)

    data = json.loads(result)
    assert isinstance(data, list)


@pytest.mark.asyncio
async def test_scrape_organizations_unknown_source():
    """scrape_organizations с неизвестным source использует yandex-maps по умолчанию."""
    _skip_if_no_mcp()

    from src.mcp_server import scrape_organizations

    orgs = [make_org()]
    mock_scraper = AsyncMock()
    mock_scraper.scrape = AsyncMock(return_value=orgs)
    mock_ctx = AsyncMock()

    with (
        patch("src.mcp_server.load_config", return_value=MagicMock()),
        patch("src.mcp_server.BrowserManager") as mock_bm,
        patch("src.tools.orgscout.scrapers.yandex_maps.YandexMapsScraper", return_value=mock_scraper),
    ):
        mock_bm.return_value.__aenter__ = AsyncMock(return_value=MagicMock(
            new_context=AsyncMock(return_value=mock_ctx)
        ))
        mock_bm.return_value.__aexit__ = AsyncMock(return_value=None)
        # source не 2gis → ветка else → YandexMapsScraper
        result = await scrape_organizations("кафе", "Уфа", source="unknown", max_results=5)

    data = json.loads(result)
    assert isinstance(data, list)


# ─── fetch_organization ───────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_fetch_organization_found():
    """fetch_organization возвращает JSON-объект найденной организации."""
    _skip_if_no_mcp()

    from src.mcp_server import fetch_organization

    org = make_org()
    mock_scraper = AsyncMock()
    mock_scraper.fetch = AsyncMock(return_value=org)
    mock_ctx = AsyncMock()

    with (
        patch("src.mcp_server.load_config", return_value=MagicMock()),
        patch("src.mcp_server.BrowserManager") as mock_bm,
        patch("src.tools.orgscout.scrapers.yandex_maps.YandexMapsScraper", return_value=mock_scraper),
    ):
        mock_bm.return_value.__aenter__ = AsyncMock(return_value=MagicMock(
            new_context=AsyncMock(return_value=mock_ctx)
        ))
        mock_bm.return_value.__aexit__ = AsyncMock(return_value=None)

        result = await fetch_organization("https://yandex.ru/maps/org/1/")

    data = json.loads(result)
    assert data["name"] == "Салон Ромашка"


@pytest.mark.asyncio
async def test_fetch_organization_not_found():
    """fetch_organization возвращает ошибку если организация не найдена."""
    _skip_if_no_mcp()

    from src.mcp_server import fetch_organization

    mock_scraper = AsyncMock()
    mock_scraper.fetch = AsyncMock(return_value=None)
    mock_ctx = AsyncMock()

    with (
        patch("src.mcp_server.load_config", return_value=MagicMock()),
        patch("src.mcp_server.BrowserManager") as mock_bm,
        patch("src.tools.orgscout.scrapers.yandex_maps.YandexMapsScraper", return_value=mock_scraper),
    ):
        mock_bm.return_value.__aenter__ = AsyncMock(return_value=MagicMock(
            new_context=AsyncMock(return_value=mock_ctx)
        ))
        mock_bm.return_value.__aexit__ = AsyncMock(return_value=None)

        result = await fetch_organization("https://yandex.ru/maps/org/999/")

    data = json.loads(result)
    assert "error" in data


# ─── search_legal ─────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_search_legal_no_query():
    """search_legal без name и inn возвращает ошибку."""
    _skip_if_no_mcp()

    from src.mcp_server import search_legal

    result = await search_legal()
    data = json.loads(result)
    assert "error" in data


@pytest.mark.asyncio
async def test_search_legal_egrul():
    """search_legal с source=egrul возвращает JSON-массив юрлиц."""
    _skip_if_no_mcp()

    from src.mcp_server import search_legal

    entities = [make_legal()]
    mock_scraper = AsyncMock()
    mock_scraper.search = AsyncMock(return_value=entities)

    with (
        patch("src.mcp_server.load_config", return_value=MagicMock()),
        patch("src.tools.legalscout.scrapers.egrul.EgrulScraper", return_value=mock_scraper),
    ):
        result = await search_legal(name="Ромашка", source="egrul")

    data = json.loads(result)
    assert isinstance(data, list)
    assert len(data) == 1
