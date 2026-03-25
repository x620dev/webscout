"""Rich progress bar для долгих операций WebScout."""

from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

from rich.console import Console
from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    SpinnerColumn,
    TaskID,
    TaskProgressColumn,
    TextColumn,
    TimeElapsedColumn,
)

# Консоль для прогресс-бара (stderr, чтобы не мешать pipe/redirect)
_err_console = Console(stderr=True)


def make_progress() -> Progress:
    """Создать настроенный rich Progress с колонками WebScout."""
    return Progress(
        SpinnerColumn(),
        TextColumn("[bold blue]{task.description}"),
        BarColumn(),
        MofNCompleteColumn(),
        TaskProgressColumn(),
        TextColumn("• Ошибки: [red]{task.fields[errors]}[/red]"),
        TimeElapsedColumn(),
        console=_err_console,
        transient=False,
    )


@contextmanager
def scraping_progress(
    description: str,
    total: int,
) -> Iterator[tuple[Progress, TaskID]]:
    """Context manager для отображения прогресса долгих операций.

    Выводит прогресс-бар в stderr — не мешает pipe/redirect вывода.
    Формат: «description X/Y XX% • Ошибки: N ETA: ~N мин»

    Пример:
        with scraping_progress("Скрапинг", total=100) as (progress, task_id):
            for item in items:
                # ... обработка ...
                progress.advance(task_id)
                # при ошибке:
                progress.update(task_id, errors=errors_count)

    Args:
        description: Текст описания операции.
        total: Ожидаемое общее количество элементов (0 = неизвестно).

    Yields:
        Кортеж (progress, task_id) для управления прогресс-баром.
    """
    progress = make_progress()
    with progress:
        task_id = progress.add_task(description, total=total, errors=0)
        yield progress, task_id
