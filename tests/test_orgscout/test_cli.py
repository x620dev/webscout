"""Тесты CLI OrgScout (tools/orgscout/cli.py)."""

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from typer.testing import CliRunner

from src.cli import app
from src.tools.orgscout.models import Organization

runner = CliRunner()


# ─── Вспомогательные фикстуры ─────────────────────────────────────────────────


def make_org(**kwargs) -> Organization:
    """Создать тестовую организацию с дефолтными полями."""
    defaults = {
        "source": "yandex_maps",
        "source_url": "https://yandex.ru/maps/org/test/1/",
        "name": "Тестовая Студия",
        "address": "ул. Ленина, 1",
    }
    defaults.update(kwargs)
    return Organization(**defaults)


# ─── org scrape yandex-maps ───────────────────────────────────────────────────


def test_scrape_yandex_maps_help():
    """Команда scrape yandex-maps показывает справку."""
    result = runner.invoke(app, ["org", "scrape", "yandex-maps", "--help"])
    assert result.exit_code == 0
    assert "--query" in result.output


def test_scrape_yandex_maps_missing_query():
    """Команда scrape yandex-maps требует --query."""
    result = runner.invoke(app, ["org", "scrape", "yandex-maps", "--city", "Уфа"])
    assert result.exit_code != 0


def test_scrape_yandex_maps_missing_city():
    """Команда scrape yandex-maps требует --city."""
    result = runner.invoke(app, ["org", "scrape", "yandex-maps", "--query", "маникюр"])
    assert result.exit_code != 0


def test_scrape_yandex_maps_runs(tmp_path):
    """Команда scrape yandex-maps выполняется и сохраняет результат."""
    out = tmp_path / "result.json"
    orgs = [make_org()]

    mock_scraper = AsyncMock()
    mock_scraper.scrape = AsyncMock(return_value=orgs)

    mock_context = AsyncMock()
    mock_manager = AsyncMock()
    mock_manager.__aenter__ = AsyncMock(return_value=mock_manager)
    mock_manager.__aexit__ = AsyncMock(return_value=False)
    mock_manager.new_context = AsyncMock(return_value=mock_context)

    with patch("src.tools.orgscout.cli.BrowserManager", return_value=mock_manager), \
         patch("src.tools.orgscout.cli.YandexMapsScraper", return_value=mock_scraper):
        result = runner.invoke(app, [
            "org", "scrape", "yandex-maps",
            "--query", "маникюр",
            "--city", "Уфа",
            "--output", str(out),
        ])

    assert result.exit_code == 0, result.output
    assert out.exists()
    data = json.loads(out.read_text())
    assert len(data) == 1
    assert data[0]["name"] == "Тестовая Студия"


# ─── org scrape 2gis ──────────────────────────────────────────────────────────


def test_scrape_2gis_help():
    """Команда scrape 2gis показывает справку."""
    result = runner.invoke(app, ["org", "scrape", "2gis", "--help"])
    assert result.exit_code == 0
    assert "--query" in result.output


def test_scrape_2gis_runs(tmp_path):
    """Команда scrape 2gis выполняется и сохраняет результат."""
    out = tmp_path / "result.json"
    orgs = [make_org(source="twogis", source_url="https://2gis.ru/firm/1")]

    mock_scraper = AsyncMock()
    mock_scraper.scrape = AsyncMock(return_value=orgs)

    mock_context = AsyncMock()
    mock_manager = AsyncMock()
    mock_manager.__aenter__ = AsyncMock(return_value=mock_manager)
    mock_manager.__aexit__ = AsyncMock(return_value=False)
    mock_manager.new_context = AsyncMock(return_value=mock_context)

    with patch("src.tools.orgscout.cli.BrowserManager", return_value=mock_manager), \
         patch("src.tools.orgscout.cli.TwoGisScraper", return_value=mock_scraper):
        result = runner.invoke(app, [
            "org", "scrape", "2gis",
            "--query", "маникюр",
            "--city", "Уфа",
            "--output", str(out),
        ])

    assert result.exit_code == 0, result.output
    assert out.exists()


# ─── org fetch ────────────────────────────────────────────────────────────────


def test_fetch_yandex_maps_help():
    """Команда fetch yandex-maps показывает справку."""
    result = runner.invoke(app, ["org", "fetch", "yandex-maps", "--help"])
    assert result.exit_code == 0
    assert "--org-url" in result.output


def test_fetch_yandex_maps_runs(tmp_path):
    """Команда fetch yandex-maps получает организацию и сохраняет."""
    out = tmp_path / "org.json"
    org = make_org()

    mock_scraper = AsyncMock()
    mock_scraper.fetch = AsyncMock(return_value=org)

    mock_context = AsyncMock()
    mock_manager = AsyncMock()
    mock_manager.__aenter__ = AsyncMock(return_value=mock_manager)
    mock_manager.__aexit__ = AsyncMock(return_value=False)
    mock_manager.new_context = AsyncMock(return_value=mock_context)

    with patch("src.tools.orgscout.cli.BrowserManager", return_value=mock_manager), \
         patch("src.tools.orgscout.cli.YandexMapsScraper", return_value=mock_scraper):
        result = runner.invoke(app, [
            "org", "fetch", "yandex-maps",
            "--org-url", "https://yandex.ru/maps/org/test/1/",
            "--output", str(out),
        ])

    assert result.exit_code == 0, result.output
    assert out.exists()
    data = json.loads(out.read_text())
    assert data[0]["name"] == "Тестовая Студия"


def test_fetch_2gis_not_found(tmp_path):
    """fetch возвращает код ошибки если организация не найдена."""
    mock_scraper = AsyncMock()
    mock_scraper.fetch = AsyncMock(return_value=None)

    mock_context = AsyncMock()
    mock_manager = AsyncMock()
    mock_manager.__aenter__ = AsyncMock(return_value=mock_manager)
    mock_manager.__aexit__ = AsyncMock(return_value=False)
    mock_manager.new_context = AsyncMock(return_value=mock_context)

    with patch("src.tools.orgscout.cli.BrowserManager", return_value=mock_manager), \
         patch("src.tools.orgscout.cli.TwoGisScraper", return_value=mock_scraper):
        result = runner.invoke(app, [
            "org", "fetch", "2gis",
            "--org-url", "https://2gis.ru/firm/9999",
        ])

    assert result.exit_code != 0


# ─── scrape --csv флаг ────────────────────────────────────────────────────────


def test_scrape_with_csv_flag(tmp_path):
    """Флаг --csv сохраняет дополнительный TSV-файл."""
    out = tmp_path / "result.json"
    orgs = [make_org()]

    mock_scraper = AsyncMock()
    mock_scraper.scrape = AsyncMock(return_value=orgs)

    mock_context = AsyncMock()
    mock_manager = AsyncMock()
    mock_manager.__aenter__ = AsyncMock(return_value=mock_manager)
    mock_manager.__aexit__ = AsyncMock(return_value=False)
    mock_manager.new_context = AsyncMock(return_value=mock_context)

    with patch("src.tools.orgscout.cli.BrowserManager", return_value=mock_manager), \
         patch("src.tools.orgscout.cli.YandexMapsScraper", return_value=mock_scraper):
        result = runner.invoke(app, [
            "org", "scrape", "yandex-maps",
            "--query", "маникюр",
            "--city", "Уфа",
            "--output", str(out),
            "--csv",
        ])

    assert result.exit_code == 0, result.output
    tsv_path = out.with_suffix(".tsv")
    assert tsv_path.exists()


# ─── merge ────────────────────────────────────────────────────────────────────


def test_merge_help():
    """Команда merge показывает справку."""
    result = runner.invoke(app, ["merge", "--help"])
    assert result.exit_code == 0
    assert "--threshold" in result.output


def test_merge_two_files(tmp_path):
    """Команда merge объединяет два файла с дедупликацией."""
    file1 = tmp_path / "a.json"
    file2 = tmp_path / "b.json"
    out = tmp_path / "merged.json"

    file1.write_text(json.dumps([
        {"name": "Colorstar", "city": "Уфа"},
        {"name": "Студия Л", "city": "Уфа"},
    ], ensure_ascii=False), encoding="utf-8")

    file2.write_text(json.dumps([
        {"name": "Colorstar", "city": "Уфа"},  # дубль
        {"name": "Nail Art", "city": "Уфа"},
    ], ensure_ascii=False), encoding="utf-8")

    result = runner.invoke(app, [
        "merge", str(file1), str(file2),
        "--output", str(out),
        "--threshold", "90",
    ])

    assert result.exit_code == 0, result.output
    assert out.exists()
    data = json.loads(out.read_text())
    # Дубль "Colorstar" должен быть удалён
    assert len(data) == 3


def test_merge_requires_two_files(tmp_path):
    """merge требует минимум 2 файла."""
    file1 = tmp_path / "a.json"
    file1.write_text("[]", encoding="utf-8")

    result = runner.invoke(app, ["merge", str(file1)])
    assert result.exit_code != 0


def test_merge_missing_file(tmp_path):
    """merge сообщает об ошибке при отсутствующем файле."""
    result = runner.invoke(app, [
        "merge",
        str(tmp_path / "nonexistent1.json"),
        str(tmp_path / "nonexistent2.json"),
    ])
    assert result.exit_code != 0
