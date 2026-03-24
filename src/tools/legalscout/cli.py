"""CLI LegalScout — команды `webscout legal search` и `webscout legal enrich`."""

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
from src.tools.legalscout.models import LegalEntity
from src.tools.legalscout.scrapers.egrul import EgrulScraper
from src.tools.legalscout.scrapers.rusprofile import RusprofileScraper

console = Console()

# ─── Корневой Typer для команды `webscout legal` ──────────────────────────────

app = typer.Typer(
    name="legal",
    help="Получать юридические данные организаций (ЕГРЮЛ, Rusprofile).",
    no_args_is_help=True,
)

# ─── Подкоманда search ────────────────────────────────────────────────────────

search_app = typer.Typer(
    help="Поиск юридического лица по названию или ИНН.",
    no_args_is_help=True,
)
app.add_typer(search_app, name="search")


# ─────────────────────────────────────────────────────────────────────────────
# search egrul
# ─────────────────────────────────────────────────────────────────────────────


@search_app.command(name="egrul")
def search_egrul(
    name: str = typer.Option("", "--name", "-n", help="Название организации"),
    inn: str = typer.Option("", "--inn", help="ИНН организации"),
    city: str = typer.Option("", "--city", help="Город для фильтрации по региону"),
    output: str = typer.Option(None, "--output", "-o", help="Имя выходного файла (сохраняется в data/json/)"),
    max_results: int = typer.Option(10, "--max-results", help="Лимит результатов"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Подробный лог"),
    config_path: Path = typer.Option(None, "--config", "-c", help="Путь к config.yaml"),
) -> None:
    """Поиск юридического лица в ЕГРЮЛ (nalog.ru) по названию или ИНН."""
    if not name and not inn:
        console.print("[red]Укажите --name или --inn.[/red]")
        raise typer.Exit(1)
    if verbose:
        logging.basicConfig(level=logging.DEBUG)
    asyncio.run(_run_search_egrul(name, inn, city, output, max_results, config_path))


# ─────────────────────────────────────────────────────────────────────────────
# search rusprofile
# ─────────────────────────────────────────────────────────────────────────────


@search_app.command(name="rusprofile")
def search_rusprofile(
    name: str = typer.Option("", "--name", "-n", help="Название организации"),
    inn: str = typer.Option("", "--inn", help="ИНН организации"),
    output: str = typer.Option(None, "--output", "-o", help="Имя выходного файла (сохраняется в data/json/)"),
    max_results: int = typer.Option(5, "--max-results", help="Лимит результатов"),
    details: bool = typer.Option(False, "--details", "-d", help="Загружать полную карточку первой компании"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Подробный лог"),
    config_path: Path = typer.Option(None, "--config", "-c", help="Путь к config.yaml"),
) -> None:
    """Поиск юридического лица на Rusprofile.ru (Playwright, SPA)."""
    if not name and not inn:
        console.print("[red]Укажите --name или --inn.[/red]")
        raise typer.Exit(1)
    if verbose:
        logging.basicConfig(level=logging.DEBUG)
    asyncio.run(_run_search_rusprofile(name, inn, output, max_results, details, config_path))


# ─────────────────────────────────────────────────────────────────────────────
# enrich
# ─────────────────────────────────────────────────────────────────────────────


@app.command(name="enrich")
def enrich(
    input_file: Path = typer.Argument(help="JSON-файл организаций для обогащения юрданными"),
    source: str = typer.Option(
        "egrul", "--source", "-s",
        help="Источник юрданных: egrul, rusprofile",
    ),
    output: str = typer.Option(
        None, "--output", "-o",
        help="Имя выходного файла в data/json/ (по умолчанию — перезаписать входной)",
    ),
    threshold: float = typer.Option(
        70.0, "--threshold", "-t",
        help="Порог нечёткого совпадения названий (0–100)",
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Подробный лог"),
    config_path: Path = typer.Option(None, "--config", "-c", help="Путь к config.yaml"),
) -> None:
    """Обогатить JSON-файл организаций юридическими данными через нечёткий матчинг."""
    if verbose:
        logging.basicConfig(level=logging.DEBUG)
    asyncio.run(_run_enrich(input_file, source, output, threshold, config_path))


# ─────────────────────────────────────────────────────────────────────────────
# Async реализация search egrul
# ─────────────────────────────────────────────────────────────────────────────


async def _run_search_egrul(
    name: str,
    inn: str,
    city: str,
    output: str | None,
    max_results: int,
    config_path: Path | None,
) -> None:
    cfg = load_config(config_path)
    query_label = inn or name
    out_path = named_path(output, "json") if output else auto_path("legalscout", city or "all", query_label, "json")

    console.print(
        f"[bold]LegalScout ЕГРЮЛ[/bold] · запрос: [yellow]{query_label!r}[/yellow]"
        + (f" · город: [yellow]{city!r}[/yellow]" if city else "")
    )

    scraper = EgrulScraper(cfg.http, cfg.proxy)

    with scraping_progress("Поиск в ЕГРЮЛ", total=max_results) as (progress, task_id):
        entities = await scraper.search(
            name=name,
            inn=inn,
            city=city,
            max_results=max_results,
        )
        progress.advance(task_id, len(entities))

    save_json(entities, out_path)
    console.print(
        f"[green]Готово:[/green] найдено [bold]{len(entities)}[/bold] юрлиц. "
        f"Файл: [cyan]{out_path}[/cyan]"
    )


# ─────────────────────────────────────────────────────────────────────────────
# Async реализация search rusprofile
# ─────────────────────────────────────────────────────────────────────────────


async def _run_search_rusprofile(
    name: str,
    inn: str,
    output: str | None,
    max_results: int,
    fetch_details: bool,
    config_path: Path | None,
) -> None:
    cfg = load_config(config_path)
    query_label = inn or name
    out_path = named_path(output, "json") if output else auto_path("legalscout", "rusprofile", query_label, "json")

    console.print(
        f"[bold]LegalScout Rusprofile[/bold] · запрос: [yellow]{query_label!r}[/yellow]"
    )

    async with BrowserManager(cfg.browser, proxy=cfg.proxy) as manager:
        ctx = await manager.new_context()
        scraper = RusprofileScraper(ctx, cfg.scraping)
        entities = await scraper.search(
            name=name,
            inn=inn,
            max_results=max_results,
            fetch_details=fetch_details,
        )
        await ctx.close()

    if not entities:
        console.print("[yellow]Ничего не найдено.[/yellow]")
        raise typer.Exit(0)

    save_json(entities, out_path)
    console.print(
        f"[green]Готово:[/green] найдено [bold]{len(entities)}[/bold] юрлиц. "
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

    if source not in ("egrul", "rusprofile"):
        console.print(
            f"[red]Неизвестный источник:[/red] {source!r}. Доступно: egrul, rusprofile"
        )
        raise typer.Exit(1)

    console.print(
        f"[bold]LegalScout enrich[/bold] · источник: [cyan]{source}[/cyan] · "
        f"организаций: [bold]{len(organizations)}[/bold]"
    )

    cfg = load_config(config_path)
    enriched_count = 0

    if source == "egrul":
        scraper_egrul = EgrulScraper(cfg.http, cfg.proxy)

        with scraping_progress("Обогащение юрданными (ЕГРЮЛ)", total=len(organizations)) as (progress, task_id):
            for org in organizations:
                org_name = (org.get("name") or "").strip()
                if not org_name:
                    progress.advance(task_id)
                    continue

                org_city = (org.get("city") or "").strip()
                entities = await scraper_egrul.search(
                    name=org_name,
                    city=org_city,
                    max_results=5,
                )

                matched = _find_legal_match(org_name, entities, threshold)
                if matched:
                    if "_enriched" not in org:
                        org["_enriched"] = {}
                    org["_enriched"]["legal"] = matched.model_dump(mode="json")
                    enriched_count += 1

                progress.advance(task_id)

    else:  # rusprofile
        async with BrowserManager(cfg.browser, proxy=cfg.proxy) as manager:
            ctx = await manager.new_context()

            with scraping_progress("Обогащение юрданными (Rusprofile)", total=len(organizations)) as (progress, task_id):
                for org in organizations:
                    org_name = (org.get("name") or "").strip()
                    if not org_name:
                        progress.advance(task_id)
                        continue

                    scraper_rp = RusprofileScraper(ctx, cfg.scraping)
                    try:
                        entities = await scraper_rp.search(name=org_name, max_results=5)
                    except Exception as exc:
                        logging.getLogger(__name__).error(
                            "Rusprofile enrich ошибка для %r: %s", org_name, exc
                        )
                        progress.advance(task_id)
                        continue

                    matched = _find_legal_match(org_name, entities, threshold)
                    if matched:
                        if "_enriched" not in org:
                            org["_enriched"] = {}
                        org["_enriched"]["legal"] = matched.model_dump(mode="json")
                        enriched_count += 1

                    progress.advance(task_id)

            await ctx.close()

    out_path = named_path(output, "json") if output else input_file
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(organizations, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    console.print(
        f"[green]Готово:[/green] обогащено юрданными [bold]{enriched_count}[/bold] из "
        f"[bold]{len(organizations)}[/bold] организаций. Файл: [cyan]{out_path}[/cyan]"
    )


def _find_legal_match(
    org_name: str,
    entities: list,
    threshold: float,
) -> LegalEntity | None:
    """Найти наилучшее совпадение среди результатов поиска по нечёткому матчингу."""
    if not entities:
        return None

    norm_org = normalize_name(org_name)
    norm_names = [normalize_name(e.name) for e in entities]
    hit = find_best_match(norm_org, norm_names, threshold=threshold)
    if hit is None:
        return None

    idx, _ = hit
    return entities[idx]
