"""CLI JobScout — команды `webscout jobs search` и `webscout jobs enrich`."""

from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path

import typer
from rich.console import Console

from src.core.browser import BrowserManager
from src.core.config import load_config
from src.core.matching import find_best_match, normalize_name
from src.output.json_writer import save_json
from src.output.naming import auto_path, named_path
from src.output.progress import scraping_progress
from src.tools.jobscout.models import Vacancy
from src.tools.jobscout.scrapers.avito import AvitoJobScraper
from src.tools.jobscout.scrapers.hh import HhScraper

console = Console()

# ─── Корневой Typer для команды `webscout jobs` ───────────────────────────────
app = typer.Typer(
    name="jobs",
    help="Искать вакансии на job-платформах.",
    no_args_is_help=True,
)

# ─── Подкоманда search ────────────────────────────────────────────────────────
search_app = typer.Typer(help="Поиск вакансий по запросу.", no_args_is_help=True)
app.add_typer(search_app, name="search")


# ─────────────────────────────────────────────────────────────────────────────
# search hh
# ─────────────────────────────────────────────────────────────────────────────


@search_app.command(name="hh")
def search_hh(
    query: str = typer.Option(..., "--query", "-q", help="Поисковый запрос"),
    city: str = typer.Option(..., "--city", help="Город"),
    output: str = typer.Option(None, "--output", "-o", help="Имя выходного файла (сохраняется в data/json/)"),
    max_results: int = typer.Option(50, "--max-results", "-n", help="Лимит результатов"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Подробный лог"),
    config_path: Path = typer.Option(None, "--config", "-c", help="Путь к config.yaml"),
) -> None:
    """Поиск вакансий на hh.ru (публичный REST API)."""
    if verbose:
        logging.basicConfig(level=logging.DEBUG)
    asyncio.run(_run_search_hh(query, city, output, max_results, config_path))


# ─────────────────────────────────────────────────────────────────────────────
# search avito
# ─────────────────────────────────────────────────────────────────────────────


@search_app.command(name="avito")
def search_avito(
    query: str = typer.Option(..., "--query", "-q", help="Поисковый запрос"),
    city: str = typer.Option(..., "--city", help="Город"),
    output: str = typer.Option(None, "--output", "-o", help="Имя выходного файла (сохраняется в data/json/)"),
    max_results: int = typer.Option(50, "--max-results", "-n", help="Лимит результатов"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Подробный лог"),
    config_path: Path = typer.Option(None, "--config", "-c", help="Путь к config.yaml"),
) -> None:
    """Поиск вакансий на Avito (Playwright, SPA)."""
    if verbose:
        logging.basicConfig(level=logging.DEBUG)
    asyncio.run(_run_search_avito(query, city, output, max_results, config_path))


# ─────────────────────────────────────────────────────────────────────────────
# enrich
# ─────────────────────────────────────────────────────────────────────────────


@app.command(name="enrich")
def enrich(
    input_file: Path = typer.Argument(help="JSON-файл организаций для обогащения вакансиями"),
    source: str = typer.Option("hh", "--source", "-s", help="Источник вакансий: hh"),
    output: str = typer.Option(
        None, "--output", "-o",
        help="Имя выходного файла в data/json/ (по умолчанию — перезаписать входной)",
    ),
    threshold: float = typer.Option(
        70.0, "--threshold", "-t",
        help="Порог нечёткого совпадения названий компаний (0–100)",
    ),
    max_per_org: int = typer.Option(
        10, "--max-per-org",
        help="Максимальное число вакансий на одну организацию",
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Подробный лог"),
    config_path: Path = typer.Option(None, "--config", "-c", help="Путь к config.yaml"),
) -> None:
    """Обогатить JSON-файл организаций вакансиями через нечёткий матчинг."""
    if verbose:
        logging.basicConfig(level=logging.DEBUG)
    asyncio.run(_run_enrich(input_file, source, output, threshold, max_per_org, config_path))


# ─────────────────────────────────────────────────────────────────────────────
# Async реализация search hh
# ─────────────────────────────────────────────────────────────────────────────


async def _run_search_hh(
    query: str,
    city: str,
    output: str | None,
    max_results: int,
    config_path: Path | None,
) -> None:
    cfg = load_config(config_path)
    out_path = named_path(output, "json") if output else auto_path("jobscout", city, query, "json")

    console.print(
        f"[bold]JobScout hh.ru[/bold] · запрос: [yellow]{query!r}[/yellow] · "
        f"город: [yellow]{city!r}[/yellow]"
    )

    scraper = HhScraper(cfg.http, cfg.proxy)

    with scraping_progress("Поиск вакансий hh.ru", total=max_results) as (progress, task_id):
        vacancies = await scraper.search(query, city, max_results=max_results)
        progress.advance(task_id, len(vacancies))

    save_json(vacancies, out_path)
    console.print(
        f"[green]Готово:[/green] найдено [bold]{len(vacancies)}[/bold] вакансий. "
        f"Файл: [cyan]{out_path}[/cyan]"
    )


# ─────────────────────────────────────────────────────────────────────────────
# Async реализация search avito
# ─────────────────────────────────────────────────────────────────────────────


async def _run_search_avito(
    query: str,
    city: str,
    output: str | None,
    max_results: int,
    config_path: Path | None,
) -> None:
    cfg = load_config(config_path)
    out_path = named_path(output, "json") if output else auto_path("jobscout", city, query, "json")

    console.print(
        f"[bold]JobScout Avito[/bold] · запрос: [yellow]{query!r}[/yellow] · "
        f"город: [yellow]{city!r}[/yellow]"
    )

    vacancies: list[Vacancy] = []
    async with BrowserManager(cfg.browser, proxy=cfg.proxy) as manager:
        ctx = await manager.new_context()
        scraper = AvitoJobScraper(ctx, cfg.scraping)

        with scraping_progress("Скрапинг Avito Jobs", total=max_results) as (progress, task_id):
            vacancies = await scraper.scrape(query, city, max_results=max_results)
            progress.advance(task_id, len(vacancies))

        await ctx.close()

    save_json(vacancies, out_path)
    console.print(
        f"[green]Готово:[/green] найдено [bold]{len(vacancies)}[/bold] вакансий. "
        f"Файл: [cyan]{out_path}[/cyan]"
    )


# ─────────────────────────────────────────────────────────────────────────────
# Async реализация enrich
# ─────────────────────────────────────────────────────────────────────────────


async def _run_enrich(
    input_file: Path,
    source: str,
    output: str | None,
    threshold: float,
    max_per_org: int,
    config_path: Path | None,
) -> None:
    if not input_file.exists():
        console.print(f"[red]Файл не найден:[/red] {input_file}")
        raise typer.Exit(1)

    try:
        organizations: list[dict] = json.loads(input_file.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        console.print(f"[red]Ошибка чтения JSON:[/red] {exc}")
        raise typer.Exit(1)

    if not isinstance(organizations, list):
        console.print("[red]Входной файл должен содержать JSON-массив организаций.[/red]")
        raise typer.Exit(1)

    # Определяем город из первой записи с заполненным полем
    city = next(
        (o.get("city") or "" for o in organizations if o.get("city")),
        "",
    )
    if not city:
        # Пробуем извлечь из address (первое слово)
        first_address = next((o.get("address", "") for o in organizations if o.get("address")), "")
        city = first_address.split(",")[0].strip() if first_address else ""

    if source not in ("hh",):
        console.print(f"[red]Неизвестный источник:[/red] {source!r}. Доступно: hh")
        raise typer.Exit(1)

    cfg = load_config(config_path)

    console.print(
        f"[bold]JobScout enrich[/bold] · источник: [cyan]{source}[/cyan] · "
        f"организаций: [bold]{len(organizations)}[/bold]"
        + (f" · город: [yellow]{city!r}[/yellow]" if city else "")
    )

    enriched_count = 0
    scraper = HhScraper(cfg.http, cfg.proxy)

    with scraping_progress("Обогащение вакансиями", total=len(organizations)) as (progress, task_id):
        for org in organizations:
            org_name = org.get("name", "").strip()
            if not org_name:
                progress.advance(task_id)
                continue

            # Ищем вакансии с названием компании в запросе
            org_city = org.get("city") or city
            vacancies = await scraper.search(org_name, org_city, max_results=max_per_org * 3)

            # Фильтрация: оставляем только вакансии, где employer.name fuzzy-совпадает
            norm_org = normalize_name(org_name)
            matched: list[dict] = []
            for v in vacancies:
                if not v.company_name:
                    continue
                norm_company = normalize_name(v.company_name)
                hit = find_best_match(norm_org, [norm_company], threshold=threshold)
                if hit is not None:
                    matched.append(v.model_dump(mode="json"))
                    if len(matched) >= max_per_org:
                        break

            if matched:
                if "_enriched" not in org:
                    org["_enriched"] = {}
                org["_enriched"]["jobs"] = matched
                enriched_count += 1

            progress.advance(task_id)

    # Сохраняем результат
    out_path = named_path(output, "json") if output else input_file
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(organizations, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    console.print(
        f"[green]Готово:[/green] обогащено [bold]{enriched_count}[/bold] из "
        f"[bold]{len(organizations)}[/bold] организаций. Файл: [cyan]{out_path}[/cyan]"
    )
