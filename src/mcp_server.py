"""MCP-сервер WebScout — предоставляет инструменты всех модулей через MCP.

Установка зависимости:
    pip install "mcp[cli]>=1.0"   # или: uv add "mcp[cli]>=1.0"

Запуск сервера:
    python -m src.mcp_server

Или через Claude Desktop (claude_desktop_config.json):
    {
      "mcpServers": {
        "webscout": {
          "command": "python",
          "args": ["-m", "src.mcp_server"],
          "cwd": "/path/to/WebScout"
        }
      }
    }

Инструменты:
    scrape_organizations  — поиск организаций (OrgScout)
    fetch_organization    — карточка организации
    search_vacancies      — поиск вакансий (JobScout)
    fetch_prices          — прайс организации (PriceScout)
    scrape_reviews        — отзывы (ReviewScout)
    search_legal          — юридические данные (LegalScout)
"""

from __future__ import annotations

import json
import logging

try:
    from mcp.server.fastmcp import FastMCP
except ImportError as exc:  # pragma: no cover
    raise SystemExit(
        "Для MCP-сервера необходима библиотека mcp.\n"
        "Установите: pip install 'mcp[cli]>=1.0'\n"
        f"Детали: {exc}"
    ) from exc

from src.core.browser import BrowserManager
from src.core.config import load_config

logger = logging.getLogger(__name__)

mcp = FastMCP(
    "webscout",
    instructions=(
        "WebScout предоставляет инструменты для исследования рынка через веб: "
        "поиск организаций на картах, вакансии, прайс-листы, отзывы и юридические данные."
    ),
)

# ─────────────────────────────────────────────────────────────────────────────
# Вспомогательная функция
# ─────────────────────────────────────────────────────────────────────────────


def _to_json(items: list) -> str:
    """Сериализовать список Pydantic-моделей или dict в JSON-строку."""
    result = []
    for item in items:
        if hasattr(item, "model_dump"):
            result.append(item.model_dump(mode="json"))
        else:
            result.append(item)
    return json.dumps(result, ensure_ascii=False, indent=2)


# ─────────────────────────────────────────────────────────────────────────────
# OrgScout
# ─────────────────────────────────────────────────────────────────────────────


@mcp.tool()
async def scrape_organizations(
    query: str,
    city: str,
    source: str = "yandex-maps",
    max_results: int = 50,
) -> str:
    """Найти организации на картографических сервисах.

    Args:
        query: Поисковый запрос (например, «маникюр», «стоматология»).
        city: Город (например, «Уфа», «Москва»).
        source: Источник — yandex-maps или 2gis (по умолчанию yandex-maps).
        max_results: Максимальное число результатов (по умолчанию 50).

    Returns:
        JSON-массив организаций с полями: name, address, contacts, rating, categories.
    """
    from src.tools.orgscout.scrapers.twogis import TwoGisScraper
    from src.tools.orgscout.scrapers.yandex_maps import YandexMapsScraper

    cfg = load_config(None)
    async with BrowserManager(cfg.browser, proxy=cfg.proxy) as manager:
        ctx = await manager.new_context()
        if source == "2gis":
            scraper = TwoGisScraper(ctx, cfg.scraping)
        else:
            scraper = YandexMapsScraper(ctx, cfg.scraping)
        results = await scraper.scrape(query, city, max_results=max_results)
        await ctx.close()

    return _to_json(results)


@mcp.tool()
async def fetch_organization(
    url: str,
    source: str = "yandex-maps",
) -> str:
    """Получить полную карточку одной организации по URL.

    Args:
        url: URL карточки организации на Яндекс.Картах или 2ГИС.
        source: Источник — yandex-maps или 2gis (по умолчанию yandex-maps).

    Returns:
        JSON-объект организации.
    """
    from src.tools.orgscout.scrapers.twogis import TwoGisScraper
    from src.tools.orgscout.scrapers.yandex_maps import YandexMapsScraper

    cfg = load_config(None)
    async with BrowserManager(cfg.browser, proxy=cfg.proxy) as manager:
        ctx = await manager.new_context()
        if source == "2gis":
            scraper = TwoGisScraper(ctx, cfg.scraping)
        else:
            scraper = YandexMapsScraper(ctx, cfg.scraping)
        org = await scraper.fetch(url)
        await ctx.close()

    if org is None:
        return json.dumps({"error": "Организация не найдена"})
    return json.dumps(org.model_dump(mode="json"), ensure_ascii=False, indent=2)


# ─────────────────────────────────────────────────────────────────────────────
# JobScout
# ─────────────────────────────────────────────────────────────────────────────


@mcp.tool()
async def search_vacancies(
    query: str,
    city: str,
    source: str = "hh",
    max_results: int = 50,
) -> str:
    """Найти вакансии на job-платформах.

    Args:
        query: Поисковый запрос (например, «администратор», «мастер маникюра»).
        city: Город.
        source: Источник — hh (hh.ru) или avito (по умолчанию hh).
        max_results: Максимальное число результатов (по умолчанию 50).

    Returns:
        JSON-массив вакансий с полями: title, company, salary, url.
    """
    from src.tools.jobscout.scrapers.avito import AvitoJobScraper
    from src.tools.jobscout.scrapers.hh import HhScraper

    cfg = load_config(None)

    if source == "avito":
        async with BrowserManager(cfg.browser, proxy=cfg.proxy) as manager:
            ctx = await manager.new_context()
            scraper = AvitoJobScraper(ctx, cfg.scraping)
            results = await scraper.search(query, city, max_results=max_results)
            await ctx.close()
    else:
        scraper_hh = HhScraper(cfg.http, cfg.proxy)
        results = await scraper_hh.search(query, city, max_results=max_results)

    return _to_json(results)


# ─────────────────────────────────────────────────────────────────────────────
# PriceScout
# ─────────────────────────────────────────────────────────────────────────────


@mcp.tool()
async def fetch_prices(
    url: str,
    org_name: str = "",
    source: str = "yclients",
) -> str:
    """Получить прайс-лист организации из CRM-виджета.

    Args:
        url: URL виджета онлайн-записи (YCLIENTS или Dikidi).
        org_name: Название организации (для метаданных).
        source: CRM-система — yclients или dikidi (по умолчанию yclients).

    Returns:
        JSON-объект прайс-листа с услугами и ценами.
    """
    from src.tools.pricescout.scrapers.dikidi import DikidiScraper
    from src.tools.pricescout.scrapers.yclients import YclientsScraper

    cfg = load_config(None)
    async with BrowserManager(cfg.browser, proxy=cfg.proxy) as manager:
        ctx = await manager.new_context()
        if source == "dikidi":
            scraper = DikidiScraper(ctx, cfg.scraping)
        else:
            scraper = YclientsScraper(ctx, cfg.scraping)
        price_list = await scraper.fetch(url, org_name=org_name)
        await ctx.close()

    if price_list is None:
        return json.dumps({"error": "Прайс не найден"})
    return json.dumps(price_list.model_dump(mode="json"), ensure_ascii=False, indent=2)


# ─────────────────────────────────────────────────────────────────────────────
# ReviewScout
# ─────────────────────────────────────────────────────────────────────────────


@mcp.tool()
async def scrape_reviews(
    url: str,
    source: str = "yandex",
    max_reviews: int = 50,
) -> str:
    """Собрать отзывы об организации.

    Args:
        url: URL страницы организации (Яндекс.Карты или Flamp).
        source: Платформа — yandex или flamp (по умолчанию yandex).
        max_reviews: Максимальное число отзывов (по умолчанию 50).

    Returns:
        JSON-объект с отзывами, рейтингом и сводкой.
    """
    from src.tools.reviewscout.scrapers.flamp import FlampScraper
    from src.tools.reviewscout.scrapers.yandex_reviews import YandexReviewsScraper

    cfg = load_config(None)
    async with BrowserManager(cfg.browser, proxy=cfg.proxy) as manager:
        ctx = await manager.new_context()
        if source == "flamp":
            scraper = FlampScraper(ctx, cfg.scraping)
        else:
            scraper = YandexReviewsScraper(ctx, cfg.scraping)
        review_summary = await scraper.scrape(url, max_reviews=max_reviews)
        await ctx.close()

    if review_summary is None:
        return json.dumps({"error": "Отзывы не найдены"})
    return json.dumps(review_summary.model_dump(mode="json"), ensure_ascii=False, indent=2)


# ─────────────────────────────────────────────────────────────────────────────
# LegalScout
# ─────────────────────────────────────────────────────────────────────────────


@mcp.tool()
async def search_legal(
    name: str = "",
    inn: str = "",
    city: str = "",
    source: str = "egrul",
    max_results: int = 5,
) -> str:
    """Найти юридическую информацию об организации.

    Args:
        name: Название организации.
        inn: ИНН организации (альтернатива name).
        city: Город для фильтрации по региону.
        source: Источник — egrul (nalog.ru) или rusprofile (по умолчанию egrul).
        max_results: Максимальное число результатов (по умолчанию 5).

    Returns:
        JSON-массив юридических лиц с полями: name, inn, ogrn, address, status.
    """
    from src.tools.legalscout.scrapers.egrul import EgrulScraper
    from src.tools.legalscout.scrapers.rusprofile import RusprofileScraper

    if not name and not inn:
        return json.dumps({"error": "Укажите name или inn."})

    cfg = load_config(None)

    if source == "rusprofile":
        async with BrowserManager(cfg.browser, proxy=cfg.proxy) as manager:
            ctx = await manager.new_context()
            scraper = RusprofileScraper(ctx, cfg.scraping)
            results = await scraper.search(name=name, inn=inn, max_results=max_results)
            await ctx.close()
    else:
        scraper_egrul = EgrulScraper(cfg.http, cfg.proxy)
        results = await scraper_egrul.search(
            name=name, inn=inn, city=city, max_results=max_results
        )

    return _to_json(results)


# ─────────────────────────────────────────────────────────────────────────────
# Точка входа
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    mcp.run()
