"""Исполнитель YAML-пайплайнов WebScout.

Пайплайн — YAML-файл, описывающий цепочку шагов:

    name: "Исследование рынка маникюра в Уфе"
    steps:
      - tool: org
        command: scrape
        source: yandex-maps
        params:
          query: "маникюр"
          city: "Уфа"
          max_results: 200
        output: data/json/studios.json

      - tool: jobs
        command: enrich
        input: data/json/studios.json
        source: hh

      - tool: legal
        command: enrich
        input: data/json/studios.json
        source: egrul

Каждый шаг транслируется в команду `webscout <args>` и выполняется
последовательно. При ошибке шага пайплайн предлагает продолжить или остановиться.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

import yaml
from rich.console import Console
from rich.panel import Panel
from rich.rule import Rule

console = Console()

# ─────────────────────────────────────────────────────────────────────────────
# Команды, где `source` является позиционным sub-command, а не опцией --source
# ─────────────────────────────────────────────────────────────────────────────

_SOURCE_IS_SUBCOMMAND: set[tuple[str, str]] = {
    ("org", "scrape"),
    ("org", "fetch"),
    ("jobs", "search"),
    ("prices", "fetch"),
    ("reviews", "scrape"),
    ("legal", "search"),
}


# ─────────────────────────────────────────────────────────────────────────────
# Загрузка YAML
# ─────────────────────────────────────────────────────────────────────────────


def load_pipeline(path: Path) -> dict[str, Any]:
    """Загрузить и провалидировать YAML-пайплайн."""
    if not path.exists():
        raise FileNotFoundError(f"Файл пайплайна не найден: {path}")

    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f)

    if not isinstance(data, dict):
        raise ValueError("Пайплайн должен быть YAML-словарём с ключами name и steps.")
    if "steps" not in data or not isinstance(data["steps"], list):
        raise ValueError("Пайплайн должен содержать ключ 'steps' со списком шагов.")

    for i, step in enumerate(data["steps"], 1):
        if "tool" not in step:
            raise ValueError(f"Шаг {i}: отсутствует обязательный ключ 'tool'.")
        if "command" not in step:
            raise ValueError(f"Шаг {i}: отсутствует обязательный ключ 'command'.")

    return data


# ─────────────────────────────────────────────────────────────────────────────
# Трансляция шага в аргументы CLI
# ─────────────────────────────────────────────────────────────────────────────


def step_to_args(step: dict[str, Any]) -> list[str]:
    """Преобразовать описание шага YAML в список аргументов CLI webscout."""
    tool: str = step["tool"]
    command: str = step["command"]
    source: str = step.get("source", "")

    args: list[str] = [tool, command]

    # Source как позиционный sub-command (org scrape yandex-maps ...)
    if source and (tool, command) in _SOURCE_IS_SUBCOMMAND:
        args.append(source)

    # Input-файл как позиционный аргумент (для enrich/collect)
    if "input" in step:
        args.append(str(step["input"]))

    # Параметры шага → CLI-опции
    for key, value in (step.get("params") or {}).items():
        cli_key = "--" + key.replace("_", "-")
        if isinstance(value, bool):
            if value:
                args.append(cli_key)
        else:
            args.extend([cli_key, str(value)])

    # Source как --source опция (для enrich/collect)
    if source and (tool, command) not in _SOURCE_IS_SUBCOMMAND:
        args.extend(["--source", source])

    # Output
    if "output" in step:
        args.extend(["--output", str(step["output"])])

    return args


# ─────────────────────────────────────────────────────────────────────────────
# Поиск исполняемого файла webscout
# ─────────────────────────────────────────────────────────────────────────────


def _get_webscout_cmd() -> list[str]:
    """Вернуть команду запуска webscout (установленный бинарь или fallback)."""
    ws = shutil.which("webscout")
    if ws:
        return [ws]
    # Fallback для запуска в режиме разработки (pip install -e .)
    return [sys.executable, "-m", "src.cli"]


# ─────────────────────────────────────────────────────────────────────────────
# Запуск пайплайна
# ─────────────────────────────────────────────────────────────────────────────


def run_pipeline(
    pipeline_path: Path,
    dry_run: bool = False,
    config_path: Path | None = None,
    stop_on_error: bool = False,
) -> int:
    """Выполнить пайплайн из YAML-файла.

    Args:
        pipeline_path: Путь к YAML-файлу пайплайна.
        dry_run: Показать команды без выполнения.
        config_path: Путь к config.yaml (пробрасывается во все шаги).
        stop_on_error: Остановить пайплайн при первой ошибке без подтверждения.

    Returns:
        Количество шагов, завершившихся с ошибкой.
    """
    data = load_pipeline(pipeline_path)
    name: str = data.get("name", pipeline_path.stem)
    steps: list[dict] = data["steps"]

    console.print(Panel(f"[bold]{name}[/bold]", title="Pipeline", expand=False))
    console.print(f"Шагов: [bold]{len(steps)}[/bold]\n")

    webscout_cmd = _get_webscout_cmd()
    failed = 0

    for i, step in enumerate(steps, 1):
        args = step_to_args(step)
        if config_path:
            args.extend(["--config", str(config_path)])

        cmd_display = "webscout " + " ".join(args)
        console.print(Rule(f"Шаг {i}/{len(steps)}"))
        console.print(f"[bold cyan]$[/bold cyan] {cmd_display}")

        if dry_run:
            console.print("[dim]  (dry-run, пропущено)[/dim]")
            continue

        result = subprocess.run(webscout_cmd + args, check=False)

        if result.returncode != 0:
            failed += 1
            console.print(
                f"[red]Шаг {i} завершился с ошибкой (код {result.returncode}).[/red]"
            )

            if stop_on_error or i == len(steps):
                console.print("[yellow]Пайплайн остановлен.[/yellow]")
                return failed

            console.print("Продолжить выполнение? [[green]Y[/green]/n] ", end="")
            answer = input().strip().lower()
            if answer in ("n", "no", "н", "нет"):
                console.print("[yellow]Пайплайн остановлен.[/yellow]")
                return failed
        else:
            console.print(f"[green]Шаг {i} — OK[/green]")

        console.print()

    console.print(Rule())
    if failed:
        console.print(
            f"[yellow]Пайплайн «{name}» завершён с ошибками: "
            f"{failed}/{len(steps)} шагов.[/yellow]"
        )
    else:
        console.print(f"[green]Пайплайн «{name}» выполнен успешно.[/green]")

    return failed
