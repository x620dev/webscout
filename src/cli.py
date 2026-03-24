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
from src.core.matching import deduplicate
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
from src.tools.orgscout.cli import app as org_app  # noqa: E402
app.add_typer(org_app, name="org")

# Phase 2: JobScout
from src.tools.jobscout.cli import app as jobs_app  # noqa: E402
app.add_typer(jobs_app, name="jobs")

# Phase 3: PriceScout
from src.tools.pricescout.cli import app as prices_app  # noqa: E402
app.add_typer(prices_app, name="prices")

# Phase 4: ReviewScout
from src.tools.reviewscout.cli import app as reviews_app  # noqa: E402
app.add_typer(reviews_app, name="reviews")

# Phase 5: LegalScout
from src.tools.legalscout.cli import app as legal_app  # noqa: E402
app.add_typer(legal_app, name="legal")


# ─────────────────────────────────────────────────────────────────────────────
# render — рендеринг произвольных SPA-страниц
# ─────────────────────────────────────────────────────────────────────────────


@app.command()
def render(
    url: str = typer.Argument(help="URL страницы для рендеринга"),
    output: str = typer.Option(None, "--output", "-o", help="Имя выходного файла (сохраняется в data/)"),
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
    output: str | None,
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
        out_path = Path("data") / output
        out_path.parent.mkdir(parents=True, exist_ok=True)
        if intercept and result.intercepted_responses:
            intercept_path = out_path.with_suffix(".intercepted.json")
            intercept_path.write_text(
                json.dumps(result.intercepted_responses, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            console.print(f"[green]Перехваченные ответы сохранены:[/green] {intercept_path}")
        out_path.write_text(result.content, encoding="utf-8")
        console.print(f"[green]Сохранено:[/green] {out_path}")
    else:
        console.print(result.content)


# ─────────────────────────────────────────────────────────────────────────────
# merge — объединение и дедупликация JSON-файлов из разных источников
# ─────────────────────────────────────────────────────────────────────────────


@app.command()
def merge(
    files: list[Path] = typer.Argument(help="JSON-файлы для объединения (минимум 2)"),
    output: str = typer.Option(None, "--output", "-o", help="Имя выходного файла (сохраняется в data/json/)"),
    threshold: float = typer.Option(80.0, "--threshold", "-t", help="Порог схожести для дедупликации (0–100)"),
    name_key: str = typer.Option("name", "--name-key", help="Поле с названием организации"),
    city_key: str = typer.Option("city", "--city-key", help="Поле с городом (для фильтрации дублей)"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Подробный лог"),
) -> None:
    """Объединить несколько JSON-файлов с дедупликацией по названию организации."""
    if len(files) < 2:
        console.print("[red]Укажите минимум 2 файла для объединения.[/red]")
        raise typer.Exit(1)

    if verbose:
        logging.basicConfig(level=logging.DEBUG)

    all_records: list[dict] = []
    for f in files:
        if not f.exists():
            console.print(f"[red]Файл не найден:[/red] {f}")
            raise typer.Exit(1)
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            console.print(f"[red]Ошибка чтения {f}:[/red] {exc}")
            raise typer.Exit(1)
        if not isinstance(data, list):
            console.print(f"[red]Файл {f} не содержит JSON-массив.[/red]")
            raise typer.Exit(1)
        all_records.extend(data)
        console.print(f"[dim]Загружено {len(data)} записей из {f}[/dim]")

    console.print(f"Всего записей до дедупликации: [bold]{len(all_records)}[/bold]")

    deduped = deduplicate(all_records, name_key=name_key, city_key=city_key, threshold=threshold)
    removed = len(all_records) - len(deduped)
    console.print(f"Удалено дублей: [yellow]{removed}[/yellow]. Осталось: [bold]{len(deduped)}[/bold]")

    # Сохранение
    from src.output.naming import auto_path, named_path
    out_path = named_path(output, "json") if output else auto_path("merge", "all", "merged", "json")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(deduped, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    console.print(f"[green]Сохранено:[/green] {out_path}")


# ─────────────────────────────────────────────────────────────────────────────
# pipeline — запуск цепочки шагов из YAML-файла
# ─────────────────────────────────────────────────────────────────────────────


@app.command()
def pipeline(
    pipeline_file: Path = typer.Argument(help="Путь к YAML-файлу пайплайна"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Показать команды без выполнения"),
    stop_on_error: bool = typer.Option(
        False, "--stop-on-error", "-e", help="Остановить пайплайн при первой ошибке"
    ),
    config_path: Path = typer.Option(None, "--config", "-c", help="Путь к config.yaml"),
) -> None:
    """Запустить цепочку шагов из YAML-файла пайплайна."""
    from src.pipeline import load_pipeline, run_pipeline

    try:
        load_pipeline(pipeline_file)
    except (FileNotFoundError, ValueError) as exc:
        console.print(f"[red]Ошибка:[/red] {exc}")
        raise typer.Exit(1)

    failed = run_pipeline(
        pipeline_file,
        dry_run=dry_run,
        config_path=config_path,
        stop_on_error=stop_on_error,
    )
    if failed:
        raise typer.Exit(1)


if __name__ == "__main__":
    app()
