"""CLI PriceScout — команды `webscout prices fetch` и `webscout prices collect`."""

from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path
from urllib.parse import urlparse

import typer
from rich.console import Console

from src.core.browser import BrowserManager
from src.core.config import load_config
from src.output.json_writer import save_json
from src.output.naming import auto_path, named_path
from src.output.progress import scraping_progress
from src.tools.pricescout.scrapers.dikidi import DikidiScraper
from src.tools.pricescout.scrapers.yclients import YclientsScraper

console = Console()

# ─── Корневой Typer для команды `webscout prices` ────────────────────────────

app = typer.Typer(
    name="prices",
    help="Собирать прайс-листы с CRM-сервисов (YCLIENTS, Dikidi).",
    no_args_is_help=True,
)

# ─── Подкоманда fetch ─────────────────────────────────────────────────────────

fetch_app = typer.Typer(help="Получить прайс конкретной организации.", no_args_is_help=True)
app.add_typer(fetch_app, name="fetch")


# ─────────────────────────────────────────────────────────────────────────────
# fetch yclients
# ─────────────────────────────────────────────────────────────────────────────


@fetch_app.command(name="yclients")
def fetch_yclients(
    url: str = typer.Option(..., "--url", "-u", help="URL виджета YCLIENTS"),
    org_name: str = typer.Option("", "--name", "-n", help="Название организации"),
    output: str = typer.Option(None, "--output", "-o", help="Имя выходного файла (сохраняется в data/json/)"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Подробный лог"),
    config_path: Path = typer.Option(None, "--config", "-c", help="Путь к config.yaml"),
) -> None:
    """Получить прайс с YCLIENTS-виджета."""
    if verbose:
        logging.basicConfig(level=logging.DEBUG)
    asyncio.run(_run_fetch_yclients(url, org_name, output, config_path))


# ─────────────────────────────────────────────────────────────────────────────
# fetch dikidi
# ─────────────────────────────────────────────────────────────────────────────


@fetch_app.command(name="dikidi")
def fetch_dikidi(
    url: str = typer.Option(..., "--url", "-u", help="URL виджета Dikidi"),
    org_name: str = typer.Option("", "--name", "-n", help="Название организации"),
    output: str = typer.Option(None, "--output", "-o", help="Имя выходного файла (сохраняется в data/json/)"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Подробный лог"),
    config_path: Path = typer.Option(None, "--config", "-c", help="Путь к config.yaml"),
) -> None:
    """Получить прайс с Dikidi-виджета."""
    if verbose:
        logging.basicConfig(level=logging.DEBUG)
    asyncio.run(_run_fetch_dikidi(url, org_name, output, config_path))


# ─────────────────────────────────────────────────────────────────────────────
# collect
# ─────────────────────────────────────────────────────────────────────────────


@app.command(name="collect")
def collect(
    input_file: Path = typer.Argument(help="JSON-файл организаций с полем online_booking"),
    output: str = typer.Option(
        None, "--output", "-o",
        help="Имя выходного файла в data/json/ (по умолчанию — перезаписать входной)",
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Подробный лог"),
    config_path: Path = typer.Option(None, "--config", "-c", help="Путь к config.yaml"),
) -> None:
    """Массовый сбор прайсов: обойти все online_booking URL из JSON-файла.

    Тип CRM определяется автоматически по домену online_booking:
    - yclients.com → YCLIENTS
    - dikidi.net   → Dikidi
    Остальные домены пропускаются с предупреждением в лог.
    """
    if verbose:
        logging.basicConfig(level=logging.DEBUG)
    asyncio.run(_run_collect(input_file, output, config_path))


# ─────────────────────────────────────────────────────────────────────────────
# Async реализация fetch yclients
# ─────────────────────────────────────────────────────────────────────────────


async def _run_fetch_yclients(
    url: str,
    org_name: str,
    output: str | None,
    config_path: Path | None,
) -> None:
    cfg = load_config(config_path)
    out_path = named_path(output, "json") if output else auto_path("pricescout", "yclients", org_name or "unknown", "json")

    console.print(
        f"[bold]PriceScout YCLIENTS[/bold] · URL: [cyan]{url}[/cyan]"
        + (f" · организация: [yellow]{org_name!r}[/yellow]" if org_name else "")
    )

    async with BrowserManager(cfg.browser, proxy=cfg.proxy) as manager:
        ctx = await manager.new_context()
        scraper = YclientsScraper(ctx, cfg.scraping)
        price_list = await scraper.fetch(url, org_name)
        await ctx.close()

    if price_list is None:
        console.print("[red]Не удалось получить прайс.[/red]")
        raise typer.Exit(1)

    save_json([price_list], out_path)
    console.print(
        f"[green]Готово:[/green] найдено [bold]{len(price_list.services)}[/bold] услуг. "
        f"Файл: [cyan]{out_path}[/cyan]"
    )


# ─────────────────────────────────────────────────────────────────────────────
# Async реализация fetch dikidi
# ─────────────────────────────────────────────────────────────────────────────


async def _run_fetch_dikidi(
    url: str,
    org_name: str,
    output: str | None,
    config_path: Path | None,
) -> None:
    cfg = load_config(config_path)
    out_path = named_path(output, "json") if output else auto_path("pricescout", "dikidi", org_name or "unknown", "json")

    console.print(
        f"[bold]PriceScout Dikidi[/bold] · URL: [cyan]{url}[/cyan]"
        + (f" · организация: [yellow]{org_name!r}[/yellow]" if org_name else "")
    )

    async with BrowserManager(cfg.browser, proxy=cfg.proxy) as manager:
        ctx = await manager.new_context()
        scraper = DikidiScraper(ctx, cfg.scraping)
        price_list = await scraper.fetch(url, org_name)
        await ctx.close()

    if price_list is None:
        console.print("[red]Не удалось получить прайс.[/red]")
        raise typer.Exit(1)

    save_json([price_list], out_path)
    console.print(
        f"[green]Готово:[/green] найдено [bold]{len(price_list.services)}[/bold] услуг. "
        f"Файл: [cyan]{out_path}[/cyan]"
    )


# ─────────────────────────────────────────────────────────────────────────────
# Async реализация collect
# ─────────────────────────────────────────────────────────────────────────────

# Маппинг домена → название CRM (для логов и выбора скрапера)
_CRM_BY_DOMAIN: dict[str, str] = {
    "yclients.com": "yclients",
    "n.yclients.com": "yclients",
    "w.yclients.com": "yclients",
    "dikidi.net": "dikidi",
}


def _detect_crm(url: str) -> str | None:
    """Определить тип CRM по домену URL.

    Returns:
        "yclients", "dikidi" или None если домен неизвестен.
    """
    try:
        hostname = urlparse(url).hostname or ""
        # Проверяем точные домены и поддомены
        for domain, crm in _CRM_BY_DOMAIN.items():
            if hostname == domain or hostname.endswith("." + domain):
                return crm
    except Exception:
        pass
    return None


async def _run_collect(
    input_file: Path,
    output: str | None,
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

    # Считаем сколько организаций имеют online_booking
    with_booking = [o for o in organizations if o.get("online_booking")]
    console.print(
        f"[bold]PriceScout collect[/bold] · организаций: [bold]{len(organizations)}[/bold] · "
        f"с online_booking: [bold]{len(with_booking)}[/bold]"
    )

    if not with_booking:
        console.print("[yellow]Нет организаций с полем online_booking — нечего собирать.[/yellow]")
        return

    cfg = load_config(config_path)
    enriched_count = 0
    skipped_count = 0

    async with BrowserManager(cfg.browser, proxy=cfg.proxy) as manager:
        ctx = await manager.new_context()

        with scraping_progress("Сбор прайсов", total=len(with_booking)) as (progress, task_id):
            for org in organizations:
                booking_url = org.get("online_booking")
                if not booking_url:
                    continue

                crm = _detect_crm(booking_url)
                org_name = org.get("name", "")

                if crm is None:
                    skipped_count += 1
                    logging.getLogger(__name__).info(
                        "Неизвестный CRM, пропущено: %s (org: %r)", booking_url, org_name
                    )
                    progress.advance(task_id)
                    continue

                price_list = None
                try:
                    if crm == "yclients":
                        scraper_yclients = YclientsScraper(ctx, cfg.scraping)
                        price_list = await scraper_yclients.fetch(booking_url, org_name)
                    elif crm == "dikidi":
                        scraper_dikidi = DikidiScraper(ctx, cfg.scraping)
                        price_list = await scraper_dikidi.fetch(booking_url, org_name)
                except Exception as exc:
                    logging.getLogger(__name__).error(
                        "Ошибка сбора прайса для %r: %s", org_name, exc
                    )

                if price_list and price_list.services:
                    if "_enriched" not in org:
                        org["_enriched"] = {}
                    org["_enriched"]["prices"] = price_list.model_dump(mode="json")
                    enriched_count += 1

                progress.advance(task_id)

        await ctx.close()

    # Сохранение результата
    out_path = named_path(output, "json") if output else input_file
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(organizations, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    console.print(
        f"[green]Готово:[/green] обогащено прайсами [bold]{enriched_count}[/bold] из "
        f"[bold]{len(with_booking)}[/bold] организаций"
        + (f" · пропущено (неизвестный CRM): [yellow]{skipped_count}[/yellow]" if skipped_count else "")
        + f". Файл: [cyan]{out_path}[/cyan]"
    )
