"""Корневой CLI WebScout — единая точка входа для всех инструментов."""

from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path

import typer
from rich.console import Console

from src.core.browser import BrowserManager
from src.core.config import load_config
from src.core.renderer import OutputFormat, PageRenderer

app = typer.Typer(
    name="webscout",
    help="CLI-инструменты для исследования рынка через веб.",
    no_args_is_help=True,
)

console = Console()

# ─────────────────────────────────────────────────────────────────────────────
# Подключение инструментов (добавляются по мере реализации фаз)
# ─────────────────────────────────────────────────────────────────────────────
# Phase 1: OrgScout
# from src.tools.orgscout.cli import app as org_app
# app.add_typer(org_app, name="org")

# Phase 2: JobScout
# from src.tools.jobscout.cli import app as jobs_app
# app.add_typer(jobs_app, name="jobs")

# Phase 3: PriceScout
# from src.tools.pricescout.cli import app as prices_app
# app.add_typer(prices_app, name="prices")

# Phase 4: ReviewScout
# from src.tools.reviewscout.cli import app as reviews_app
# app.add_typer(reviews_app, name="reviews")

# Phase 5: LegalScout
# from src.tools.legalscout.cli import app as legal_app
# app.add_typer(legal_app, name="legal")


# ─────────────────────────────────────────────────────────────────────────────
# render — рендеринг произвольных SPA-страниц
# ─────────────────────────────────────────────────────────────────────────────


@app.command()
def render(
    url: str = typer.Argument(help="URL страницы для рендеринга"),
    output: Path = typer.Option(None, "--output", "-o", help="Файл для сохранения результата"),
    fmt: OutputFormat = typer.Option(OutputFormat.HTML, "--format", "-f", help="Формат: html или text"),
    wait_for: str = typer.Option(None, "--wait-for", "-w", help="CSS-селектор для ожидания загрузки"),
    config_path: Path = typer.Option(None, "--config", "-c", help="Путь к config.yaml"),
    intercept: list[str] = typer.Option(None, "--intercept", "-i", help="Паттерн URL для перехвата API-ответов"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Подробный лог"),
) -> None:
    """Открыть SPA-страницу в браузере и вернуть отрендеренный HTML/текст."""
    if verbose:
        logging.basicConfig(level=logging.DEBUG)
    asyncio.run(_render(url, output, fmt, wait_for, config_path, intercept))


async def _render(
    url: str,
    output: Path | None,
    fmt: OutputFormat,
    wait_for: str | None,
    config_path: Path | None,
    intercept: list[str] | None,
) -> None:
    cfg = load_config(config_path)
    console.print(f"[bold]Рендеринг:[/bold] {url}")

    async with BrowserManager(cfg.browser, proxy=cfg.proxy) as manager:
        ctx = await manager.new_context()
        renderer = PageRenderer(ctx, cfg.scraping)

        result = await renderer.render(
            url=url,
            fmt=fmt,
            wait_for=wait_for,
            intercept_urls=intercept or None,
        )
        await ctx.close()

    console.print(f"[green]Статус:[/green] {result.status}")
    console.print(f"[green]Размер контента:[/green] {len(result.content)} символов")

    if result.intercepted_responses:
        console.print(f"[green]Перехвачено API-ответов:[/green] {len(result.intercepted_responses)}")

    if output:
        output.parent.mkdir(parents=True, exist_ok=True)
        if intercept and result.intercepted_responses:
            intercept_path = output.with_suffix(".intercepted.json")
            intercept_path.write_text(
                json.dumps(result.intercepted_responses, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            console.print(f"[green]Перехваченные ответы сохранены:[/green] {intercept_path}")
        output.write_text(result.content, encoding="utf-8")
        console.print(f"[green]Сохранено:[/green] {output}")
    else:
        console.print(result.content)


if __name__ == "__main__":
    app()
