"""CLI OrgScout — команды `webscout org scrape` и `webscout org fetch`."""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path

import typer
from rich.console import Console

from src.core.browser import BrowserManager
from src.core.config import load_config
from src.output.csv_writer import save_csv
from src.output.json_writer import save_json
from src.output.naming import auto_path, named_path
from src.output.partial import get_seen_urls, load_existing, save_partial
from src.output.progress import scraping_progress
from src.tools.orgscout.models import Organization
from src.tools.orgscout.scrapers.twogis import TwoGisScraper
from src.tools.orgscout.scrapers.yandex_maps import YandexMapsScraper

console = Console()

# ─── Корневой Typer для команды `webscout org` ────────────────────────────────
app = typer.Typer(
    name="org",
    help="Собрать организации с картографических сервисов.",
    no_args_is_help=True,
)

# ─── Подкоманды scrape и fetch ─────────────────────────────────────────────────
scrape_app = typer.Typer(help="Поиск организаций по запросу.", no_args_is_help=True)
fetch_app = typer.Typer(help="Получить карточку одной организации по URL.", no_args_is_help=True)

app.add_typer(scrape_app, name="scrape")
app.add_typer(fetch_app, name="fetch")


# ─────────────────────────────────────────────────────────────────────────────
# Общие параметры (повторяются в командах — Typer не поддерживает наследование)
# ─────────────────────────────────────────────────────────────────────────────

def _common_scrape_opts(
    query: str,
    city: str,
    output: Path | None,
    fmt: str,
    max_results: int,
    csv_flag: bool,
    append: bool,
    verbose: bool,
    config_path: Path | None,
) -> tuple:
    """Сгруппировать общие параметры scrape-команд."""
    return query, city, output, fmt, max_results, csv_flag, append, verbose, config_path


# ─────────────────────────────────────────────────────────────────────────────
# scrape yandex-maps
# ─────────────────────────────────────────────────────────────────────────────


@scrape_app.command(name="yandex-maps")
def scrape_yandex_maps(
    query: str = typer.Option(..., "--query", "-q", help="Поисковый запрос"),
    city: str = typer.Option(..., "--city", help="Город"),
    output: str = typer.Option(None, "--output", "-o", help="Имя выходного файла (json→data/json/, ai-summary→data/ai/)"),
    fmt: str = typer.Option("json", "--format", "-f", help="Формат: json, ai-summary"),
    max_results: int = typer.Option(50, "--max-results", "-n", help="Лимит результатов"),
    csv_flag: bool = typer.Option(False, "--csv", help="Дополнительно сохранить TSV"),
    append: bool = typer.Option(False, "--append", help="Дозапуск: дописать к существующему файлу"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Подробный лог"),
    config_path: Path = typer.Option(None, "--config", "-c", help="Путь к config.yaml"),
) -> None:
    """Поиск организаций на Яндекс.Картах."""
    if verbose:
        logging.basicConfig(level=logging.DEBUG)
    asyncio.run(
        _run_scrape(
            source="yandex-maps",
            query=query,
            city=city,
            output=output,
            fmt=fmt,
            max_results=max_results,
            csv_flag=csv_flag,
            append=append,
            verbose=verbose,
            config_path=config_path,
        )
    )


# ─────────────────────────────────────────────────────────────────────────────
# scrape 2gis
# ─────────────────────────────────────────────────────────────────────────────


@scrape_app.command(name="2gis")
def scrape_2gis(
    query: str = typer.Option(..., "--query", "-q", help="Поисковый запрос"),
    city: str = typer.Option(..., "--city", help="Город"),
    output: str = typer.Option(None, "--output", "-o", help="Имя выходного файла (json→data/json/, ai-summary→data/ai/)"),
    fmt: str = typer.Option("json", "--format", "-f", help="Формат: json, ai-summary"),
    max_results: int = typer.Option(50, "--max-results", "-n", help="Лимит результатов"),
    csv_flag: bool = typer.Option(False, "--csv", help="Дополнительно сохранить TSV"),
    append: bool = typer.Option(False, "--append", help="Дозапуск: дописать к существующему файлу"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Подробный лог"),
    config_path: Path = typer.Option(None, "--config", "-c", help="Путь к config.yaml"),
) -> None:
    """Поиск организаций в 2ГИС."""
    if verbose:
        logging.basicConfig(level=logging.DEBUG)
    asyncio.run(
        _run_scrape(
            source="2gis",
            query=query,
            city=city,
            output=output,
            fmt=fmt,
            max_results=max_results,
            csv_flag=csv_flag,
            append=append,
            verbose=verbose,
            config_path=config_path,
        )
    )


# ─────────────────────────────────────────────────────────────────────────────
# fetch yandex-maps
# ─────────────────────────────────────────────────────────────────────────────


@fetch_app.command(name="yandex-maps")
def fetch_yandex_maps(
    org_url: str = typer.Option(..., "--org-url", help="URL карточки организации"),
    output: str = typer.Option(None, "--output", "-o", help="Имя выходного файла (сохраняется в data/json/)"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Подробный лог"),
    config_path: Path = typer.Option(None, "--config", "-c", help="Путь к config.yaml"),
) -> None:
    """Получить карточку одной организации с Яндекс.Карт."""
    if verbose:
        logging.basicConfig(level=logging.DEBUG)
    asyncio.run(_run_fetch(source="yandex-maps", org_url=org_url, output=output, config_path=config_path))


# ─────────────────────────────────────────────────────────────────────────────
# fetch 2gis
# ─────────────────────────────────────────────────────────────────────────────


@fetch_app.command(name="2gis")
def fetch_2gis(
    org_url: str = typer.Option(..., "--org-url", help="URL карточки организации"),
    output: str = typer.Option(None, "--output", "-o", help="Имя выходного файла (сохраняется в data/json/)"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Подробный лог"),
    config_path: Path = typer.Option(None, "--config", "-c", help="Путь к config.yaml"),
) -> None:
    """Получить карточку одной организации из 2ГИС."""
    if verbose:
        logging.basicConfig(level=logging.DEBUG)
    asyncio.run(_run_fetch(source="2gis", org_url=org_url, output=output, config_path=config_path))


# ─────────────────────────────────────────────────────────────────────────────
# Async реализация scrape
# ─────────────────────────────────────────────────────────────────────────────


async def _run_scrape(
    source: str,
    query: str,
    city: str,
    output: str | None,
    fmt: str,
    max_results: int,
    csv_flag: bool,
    append: bool,
    verbose: bool,
    config_path: Path | None,
) -> None:
    cfg = load_config(config_path)
    out_path = named_path(output, fmt) if output else auto_path("orgscout", city, query, fmt)

    console.print(
        f"[bold]OrgScout[/bold] · источник: [cyan]{source}[/cyan] · "
        f"запрос: [yellow]{query!r}[/yellow] · город: [yellow]{city!r}[/yellow]"
    )

    # Режим --append: загружаем существующий файл
    existing: list[dict] = []
    seen_urls: set[str] = set()
    if append and out_path.exists():
        existing = load_existing(out_path)
        seen_urls = get_seen_urls(existing)
        console.print(f"[dim]Дозапуск: загружено {len(existing)} существующих записей.[/dim]")

    results: list[Organization] = []

    try:
        async with BrowserManager(cfg.browser, proxy=cfg.proxy) as manager:
            ctx = await manager.new_context()

            if source == "yandex-maps":
                scraper = YandexMapsScraper(ctx, cfg.scraping)
            else:
                scraper = TwoGisScraper(ctx, cfg.scraping)

            with scraping_progress(f"Скрапинг {source}", total=max_results) as (progress, task_id):
                raw = await scraper.scrape(query, city, max_results=max_results)
                for org in raw:
                    if org.source_url in seen_urls:
                        if verbose:
                            console.print(f"[dim]Пропуск (уже есть): {org.source_url}[/dim]")
                        continue
                    results.append(org)
                    seen_urls.add(org.source_url)
                    progress.advance(task_id)
                    if verbose:
                        console.print(f"  {org.name} · {org.address}")

            await ctx.close()

    except KeyboardInterrupt:
        console.print("\n[yellow]Прервано пользователем.[/yellow]")
        if results:
            save_partial(results, out_path, total=max_results)
        raise typer.Exit(1)

    # Объединяем с существующими в режиме append
    if append and existing:
        all_dicts = existing + [o.model_dump(mode="json") for o in results]
        import json
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(
            json.dumps(all_dicts, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    else:
        save_json(results, out_path)

    if csv_flag:
        csv_path = named_path(out_path.stem, "csv")
        save_csv(results, csv_path)
        console.print(f"[green]TSV:[/green] {csv_path}")

    console.print(
        f"[green]Готово:[/green] собрано [bold]{len(results)}[/bold] организаций. "
        f"Файл: [cyan]{out_path}[/cyan]"
    )


# ─────────────────────────────────────────────────────────────────────────────
# Async реализация fetch
# ─────────────────────────────────────────────────────────────────────────────


async def _run_fetch(
    source: str,
    org_url: str,
    output: str | None,
    config_path: Path | None,
) -> None:
    cfg = load_config(config_path)
    console.print(f"[bold]OrgScout fetch[/bold] · источник: [cyan]{source}[/cyan] · {org_url}")

    async with BrowserManager(cfg.browser, proxy=cfg.proxy) as manager:
        ctx = await manager.new_context()

        if source == "yandex-maps":
            scraper = YandexMapsScraper(ctx, cfg.scraping)
        else:
            scraper = TwoGisScraper(ctx, cfg.scraping)

        org = await scraper.fetch(org_url)
        await ctx.close()

    if not org:
        console.print("[red]Не удалось получить данные организации.[/red]")
        raise typer.Exit(1)

    console.print(f"[green]Получено:[/green] {org.name}")

    if output:
        out_path = named_path(output, "json")
        save_json([org], out_path)
        console.print(f"[green]Сохранено:[/green] {out_path}")
    else:
        import json
        console.print(json.dumps(org.model_dump(mode="json"), ensure_ascii=False, indent=2))
