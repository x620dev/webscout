"""CLI ReviewScout — команды `webscout reviews scrape` и `webscout reviews enrich`."""

from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path

import typer
from rich.console import Console

from src.core.browser import BrowserManager
from src.core.config import load_config
from src.output.json_writer import save_json
from src.output.naming import auto_path
from src.output.progress import scraping_progress
from src.tools.reviewscout.scrapers.flamp import FlampScraper
from src.tools.reviewscout.scrapers.yandex_reviews import YandexReviewsScraper

console = Console()

# ─── Корневой Typer для команды `webscout reviews` ───────────────────────────

app = typer.Typer(
    name="reviews",
    help="Собирать отзывы об организациях (Яндекс, Flamp).",
    no_args_is_help=True,
)

# ─── Подкоманда scrape ────────────────────────────────────────────────────────

scrape_app = typer.Typer(
    help="Получить отзывы конкретной организации.",
    no_args_is_help=True,
)
app.add_typer(scrape_app, name="scrape")


# ─────────────────────────────────────────────────────────────────────────────
# scrape yandex
# ─────────────────────────────────────────────────────────────────────────────


@scrape_app.command(name="yandex")
def scrape_yandex(
    url: str = typer.Option(..., "--url", "-u", help="URL карточки организации на Яндекс.Картах"),
    max_reviews: int = typer.Option(50, "--max-reviews", "-n", help="Лимит отзывов"),
    output: Path = typer.Option(None, "--output", "-o", help="Путь к выходному файлу"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Подробный лог"),
    config_path: Path = typer.Option(None, "--config", "-c", help="Путь к config.yaml"),
) -> None:
    """Собрать отзывы с Яндекс.Карт для организации по URL её карточки."""
    if verbose:
        logging.basicConfig(level=logging.DEBUG)
    asyncio.run(_run_scrape_yandex(url, max_reviews, output, config_path))


# ─────────────────────────────────────────────────────────────────────────────
# scrape flamp
# ─────────────────────────────────────────────────────────────────────────────


@scrape_app.command(name="flamp")
def scrape_flamp(
    url: str = typer.Option(..., "--url", "-u", help="URL страницы организации на Flamp"),
    max_reviews: int = typer.Option(50, "--max-reviews", "-n", help="Лимит отзывов"),
    output: Path = typer.Option(None, "--output", "-o", help="Путь к выходному файлу"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Подробный лог"),
    config_path: Path = typer.Option(None, "--config", "-c", help="Путь к config.yaml"),
) -> None:
    """Собрать отзывы с Flamp.ru для организации по URL её страницы."""
    if verbose:
        logging.basicConfig(level=logging.DEBUG)
    asyncio.run(_run_scrape_flamp(url, max_reviews, output, config_path))


# ─────────────────────────────────────────────────────────────────────────────
# enrich
# ─────────────────────────────────────────────────────────────────────────────


@app.command(name="enrich")
def enrich(
    input_file: Path = typer.Argument(help="JSON-файл организаций для обогащения отзывами"),
    source: str = typer.Option(
        "yandex", "--source", "-s",
        help="Платформа отзывов: yandex, flamp",
    ),
    max_reviews: int = typer.Option(
        20, "--max-reviews", "-n",
        help="Максимальное число отзывов на организацию",
    ),
    output: Path = typer.Option(
        None, "--output", "-o",
        help="Выходной файл (по умолчанию — перезаписать входной)",
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Подробный лог"),
    config_path: Path = typer.Option(None, "--config", "-c", help="Путь к config.yaml"),
) -> None:
    """Обогатить JSON-файл организаций отзывами.

    Для каждой организации с полем source_url (или yandex_url / flamp_url)
    собираются отзывы и сохраняются в _enriched.reviews.
    """
    if verbose:
        logging.basicConfig(level=logging.DEBUG)
    asyncio.run(_run_enrich(input_file, source, max_reviews, output, config_path))


# ─────────────────────────────────────────────────────────────────────────────
# Async реализация scrape yandex
# ─────────────────────────────────────────────────────────────────────────────


async def _run_scrape_yandex(
    url: str,
    max_reviews: int,
    output: Path | None,
    config_path: Path | None,
) -> None:
    cfg = load_config(config_path)
    out_path = output or auto_path("reviewscout", "yandex", "reviews", "json")

    console.print(f"[bold]ReviewScout Яндекс[/bold] · URL: [cyan]{url}[/cyan]")

    async with BrowserManager(cfg.browser, proxy=cfg.proxy) as manager:
        ctx = await manager.new_context()
        scraper = YandexReviewsScraper(ctx, cfg.scraping)
        summary = await scraper.scrape(url, max_reviews=max_reviews)
        await ctx.close()

    if summary is None:
        console.print("[red]Не удалось получить отзывы.[/red]")
        raise typer.Exit(1)

    save_json([summary], out_path)
    console.print(
        f"[green]Готово:[/green] собрано [bold]{len(summary.reviews)}[/bold] отзывов "
        f"(рейтинг: [yellow]{summary.rating}[/yellow]). Файл: [cyan]{out_path}[/cyan]"
    )


# ─────────────────────────────────────────────────────────────────────────────
# Async реализация scrape flamp
# ─────────────────────────────────────────────────────────────────────────────


async def _run_scrape_flamp(
    url: str,
    max_reviews: int,
    output: Path | None,
    config_path: Path | None,
) -> None:
    cfg = load_config(config_path)
    out_path = output or auto_path("reviewscout", "flamp", "reviews", "json")

    console.print(f"[bold]ReviewScout Flamp[/bold] · URL: [cyan]{url}[/cyan]")

    async with BrowserManager(cfg.browser, proxy=cfg.proxy) as manager:
        ctx = await manager.new_context()
        scraper = FlampScraper(ctx, cfg.scraping)
        summary = await scraper.scrape(url, max_reviews=max_reviews)
        await ctx.close()

    if summary is None:
        console.print("[red]Не удалось получить отзывы.[/red]")
        raise typer.Exit(1)

    save_json([summary], out_path)
    console.print(
        f"[green]Готово:[/green] собрано [bold]{len(summary.reviews)}[/bold] отзывов "
        f"(рейтинг: [yellow]{summary.rating}[/yellow]). Файл: [cyan]{out_path}[/cyan]"
    )


# ─────────────────────────────────────────────────────────────────────────────
# Async реализация enrich
# ─────────────────────────────────────────────────────────────────────────────


async def _run_enrich(
    input_file: Path,
    source: str,
    max_reviews: int,
    output: Path | None,
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

    if source not in ("yandex", "flamp"):
        console.print(f"[red]Неизвестный источник:[/red] {source!r}. Доступно: yandex, flamp")
        raise typer.Exit(1)

    # Определяем URL для каждого источника
    url_field = _get_url_field(source)

    with_url = [o for o in organizations if o.get(url_field) or o.get("source_url")]
    console.print(
        f"[bold]ReviewScout enrich[/bold] · источник: [cyan]{source}[/cyan] · "
        f"организаций: [bold]{len(organizations)}[/bold] · "
        f"с URL: [bold]{len(with_url)}[/bold]"
    )

    if not with_url:
        console.print(
            f"[yellow]Нет организаций с полем {url_field!r} или source_url — нечего обогащать.[/yellow]"
        )
        # Всё равно сохраняем файл
        out_path = output or input_file
        out_path.write_text(
            json.dumps(organizations, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return

    cfg = load_config(config_path)
    enriched_count = 0

    async with BrowserManager(cfg.browser, proxy=cfg.proxy) as manager:
        ctx = await manager.new_context()

        with scraping_progress("Сбор отзывов", total=len(organizations)) as (progress, task_id):
            for org in organizations:
                org_url = org.get(url_field) or org.get("source_url")
                if not org_url:
                    progress.advance(task_id)
                    continue

                org_name = org.get("name", "")
                summary = None
                try:
                    if source == "yandex":
                        scraper = YandexReviewsScraper(ctx, cfg.scraping)
                        summary = await scraper.scrape(org_url, max_reviews=max_reviews)
                    elif source == "flamp":
                        scraper_flamp = FlampScraper(ctx, cfg.scraping)
                        summary = await scraper_flamp.scrape(org_url, max_reviews=max_reviews)
                except Exception as exc:
                    logging.getLogger(__name__).error(
                        "Ошибка сбора отзывов для %r: %s", org_name, exc
                    )

                if summary and summary.reviews:
                    if "_enriched" not in org:
                        org["_enriched"] = {}
                    org["_enriched"]["reviews"] = summary.model_dump(mode="json")
                    enriched_count += 1

                progress.advance(task_id)

        await ctx.close()

    out_path = output or input_file
    out_path.write_text(
        json.dumps(organizations, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    console.print(
        f"[green]Готово:[/green] обогащено отзывами [bold]{enriched_count}[/bold] из "
        f"[bold]{len(organizations)}[/bold] организаций. Файл: [cyan]{out_path}[/cyan]"
    )


def _get_url_field(source: str) -> str:
    """Вернуть имя поля с URL для заданного источника."""
    return {
        "yandex": "source_url",
        "flamp": "flamp_url",
    }.get(source, "source_url")
