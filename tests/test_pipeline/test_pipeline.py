"""Тесты модуля src/pipeline.py."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import yaml

from src.pipeline import load_pipeline, run_pipeline, step_to_args


# ─── Фикстуры ──────────────────────────────────────────────────────────────────


def write_yaml(tmp_path: Path, data: dict) -> Path:
    """Записать YAML-файл пайплайна в tmp_path."""
    p = tmp_path / "pipeline.yaml"
    p.write_text(yaml.dump(data, allow_unicode=True), encoding="utf-8")
    return p


MINIMAL_PIPELINE = {
    "name": "Тестовый пайплайн",
    "steps": [
        {
            "tool": "org",
            "command": "scrape",
            "source": "yandex-maps",
            "params": {"query": "маникюр", "city": "Уфа", "max_results": 10},
            "output": "data/json/test.json",
        }
    ],
}

ENRICH_PIPELINE = {
    "name": "Enrich pipeline",
    "steps": [
        {
            "tool": "jobs",
            "command": "enrich",
            "input": "data/json/studios.json",
            "source": "hh",
        },
        {
            "tool": "legal",
            "command": "enrich",
            "input": "data/json/studios.json",
            "source": "egrul",
        },
    ],
}


# ─── load_pipeline ─────────────────────────────────────────────────────────────


def test_load_pipeline_ok(tmp_path: Path) -> None:
    """load_pipeline успешно загружает корректный YAML."""
    p = write_yaml(tmp_path, MINIMAL_PIPELINE)
    data = load_pipeline(p)
    assert data["name"] == "Тестовый пайплайн"
    assert len(data["steps"]) == 1


def test_load_pipeline_not_found(tmp_path: Path) -> None:
    """load_pipeline бросает FileNotFoundError для несуществующего файла."""
    with pytest.raises(FileNotFoundError):
        load_pipeline(tmp_path / "missing.yaml")


def test_load_pipeline_invalid_yaml(tmp_path: Path) -> None:
    """load_pipeline бросает ValueError для YAML без ключа steps."""
    p = tmp_path / "bad.yaml"
    p.write_text("name: test\n", encoding="utf-8")
    with pytest.raises(ValueError, match="steps"):
        load_pipeline(p)


def test_load_pipeline_step_missing_tool(tmp_path: Path) -> None:
    """load_pipeline бросает ValueError если шаг без tool."""
    data = {"steps": [{"command": "scrape"}]}
    p = write_yaml(tmp_path, data)
    with pytest.raises(ValueError, match="tool"):
        load_pipeline(p)


def test_load_pipeline_step_missing_command(tmp_path: Path) -> None:
    """load_pipeline бросает ValueError если шаг без command."""
    data = {"steps": [{"tool": "org"}]}
    p = write_yaml(tmp_path, data)
    with pytest.raises(ValueError, match="command"):
        load_pipeline(p)


# ─── step_to_args ──────────────────────────────────────────────────────────────


def test_step_to_args_scrape_source_as_subcommand() -> None:
    """source — позиционный sub-command для scrape/fetch/search."""
    step = {
        "tool": "org",
        "command": "scrape",
        "source": "yandex-maps",
        "params": {"query": "маникюр", "city": "Уфа", "max_results": 50},
        "output": "out.json",
    }
    args = step_to_args(step)
    assert args[:3] == ["org", "scrape", "yandex-maps"]
    assert "--query" in args
    assert "маникюр" in args
    assert "--output" in args
    assert "out.json" in args
    # source НЕ должен быть как --source
    assert "--source" not in args


def test_step_to_args_enrich_source_as_option() -> None:
    """source → --source опция для enrich."""
    step = {
        "tool": "jobs",
        "command": "enrich",
        "input": "data/studios.json",
        "source": "hh",
    }
    args = step_to_args(step)
    assert args[:2] == ["jobs", "enrich"]
    assert "data/studios.json" in args
    assert "--source" in args
    assert "hh" in args


def test_step_to_args_legal_search_subcommand() -> None:
    """legal search egrul — egrul как sub-command."""
    step = {
        "tool": "legal",
        "command": "search",
        "source": "egrul",
        "params": {"name": "Ромашка", "city": "Уфа"},
    }
    args = step_to_args(step)
    assert args[:3] == ["legal", "search", "egrul"]
    assert "--name" in args
    assert "--source" not in args


def test_step_to_args_prices_collect_no_source() -> None:
    """prices collect — без source."""
    step = {
        "tool": "prices",
        "command": "collect",
        "input": "data/studios.json",
    }
    args = step_to_args(step)
    assert args[:2] == ["prices", "collect"]
    assert "data/studios.json" in args
    assert "--source" not in args


def test_step_to_args_bool_param_true() -> None:
    """Булевый параметр True → флаг без значения."""
    step = {
        "tool": "org",
        "command": "scrape",
        "source": "2gis",
        "params": {"query": "кафе", "city": "Уфа", "csv": True},
    }
    args = step_to_args(step)
    assert "--csv" in args
    idx = args.index("--csv")
    # Следующий элемент не должен быть "True"
    assert idx == len(args) - 1 or args[idx + 1].startswith("--") or args[idx + 1] in ("2gis",)


def test_step_to_args_bool_param_false() -> None:
    """Булевый параметр False → флаг не добавляется."""
    step = {
        "tool": "org",
        "command": "scrape",
        "source": "2gis",
        "params": {"query": "кафе", "city": "Уфа", "csv": False},
    }
    args = step_to_args(step)
    assert "--csv" not in args


def test_step_to_args_no_source_no_input() -> None:
    """Шаг без source и input — корректный набор аргументов."""
    step = {
        "tool": "org",
        "command": "scrape",
        "source": "yandex-maps",
        "params": {"query": "салон"},
    }
    args = step_to_args(step)
    assert "org" in args
    assert "scrape" in args
    assert "yandex-maps" in args


# ─── run_pipeline ──────────────────────────────────────────────────────────────


def test_run_pipeline_dry_run(tmp_path: Path, capsys) -> None:
    """dry_run: шаги показываются, subprocess не вызывается."""
    p = write_yaml(tmp_path, MINIMAL_PIPELINE)
    with patch("subprocess.run") as mock_run:
        result = run_pipeline(p, dry_run=True)
        mock_run.assert_not_called()
    assert result == 0


def test_run_pipeline_success(tmp_path: Path) -> None:
    """run_pipeline: все шаги возвращают 0 → failed == 0."""
    p = write_yaml(tmp_path, ENRICH_PIPELINE)
    mock_result = MagicMock()
    mock_result.returncode = 0
    with patch("subprocess.run", return_value=mock_result) as mock_run:
        failed = run_pipeline(p, stop_on_error=True)
    assert failed == 0
    assert mock_run.call_count == 2


def test_run_pipeline_stop_on_error(tmp_path: Path) -> None:
    """stop_on_error: пайплайн останавливается после первой ошибки."""
    p = write_yaml(tmp_path, ENRICH_PIPELINE)
    mock_result = MagicMock()
    mock_result.returncode = 1
    with patch("subprocess.run", return_value=mock_result) as mock_run:
        failed = run_pipeline(p, stop_on_error=True)
    assert failed == 1
    # Только первый шаг был выполнен
    assert mock_run.call_count == 1


def test_run_pipeline_with_config(tmp_path: Path) -> None:
    """config_path пробрасывается в аргументы каждого шага."""
    p = write_yaml(tmp_path, MINIMAL_PIPELINE)
    cfg = tmp_path / "config.yaml"
    cfg.write_text("", encoding="utf-8")

    mock_result = MagicMock()
    mock_result.returncode = 0
    with patch("subprocess.run", return_value=mock_result) as mock_run:
        run_pipeline(p, config_path=cfg)

    call_args = mock_run.call_args[0][0]
    assert "--config" in call_args
    assert str(cfg) in call_args


# ─── CLI integration ───────────────────────────────────────────────────────────


def test_cli_pipeline_dry_run(tmp_path: Path) -> None:
    """webscout pipeline --dry-run выводит команды без выполнения."""
    from typer.testing import CliRunner
    from src.cli import app

    p = write_yaml(tmp_path, MINIMAL_PIPELINE)
    runner = CliRunner()
    with patch("subprocess.run") as mock_run:
        result = runner.invoke(app, ["pipeline", str(p), "--dry-run"])
    assert result.exit_code == 0
    mock_run.assert_not_called()


def test_cli_pipeline_file_not_found(tmp_path: Path) -> None:
    """webscout pipeline с несуществующим файлом → exit code 1."""
    from typer.testing import CliRunner
    from src.cli import app

    runner = CliRunner()
    result = runner.invoke(app, ["pipeline", str(tmp_path / "missing.yaml")])
    assert result.exit_code == 1
