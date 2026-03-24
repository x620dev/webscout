"""Тесты CLI JobScout (tools/jobscout/cli.py)."""

import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from typer.testing import CliRunner

from src.cli import app
from src.tools.jobscout.models import Vacancy

runner = CliRunner()


# ─── Вспомогательные фикстуры ─────────────────────────────────────────────────


def make_vacancy(**kwargs) -> Vacancy:
    """Создать тестовую вакансию с дефолтными полями."""
    defaults = {
        "source": "hh",
        "source_url": "https://hh.ru/vacancy/1",
        "title": "Мастер маникюра",
        "company_name": "Студия Colorstar",
        "city": "Уфа",
    }
    defaults.update(kwargs)
    return Vacancy(**defaults)


# ─── jobs search hh ───────────────────────────────────────────────────────────


def test_jobs_search_hh_help():
    """Команда search hh показывает справку."""
    result = runner.invoke(app, ["jobs", "search", "hh", "--help"])
    assert result.exit_code == 0
    assert "--query" in result.output


def test_jobs_search_hh_missing_query():
    """search hh требует --query."""
    result = runner.invoke(app, ["jobs", "search", "hh", "--city", "Уфа"])
    assert result.exit_code != 0


def test_jobs_search_hh_missing_city():
    """search hh требует --city."""
    result = runner.invoke(app, ["jobs", "search", "hh", "--query", "маникюр"])
    assert result.exit_code != 0


def test_jobs_search_hh_runs(tmp_path, monkeypatch):
    """search hh выполняется и сохраняет результат в JSON."""
    monkeypatch.chdir(tmp_path)
    vacancies = [make_vacancy()]

    mock_scraper = AsyncMock()
    mock_scraper.search = AsyncMock(return_value=vacancies)

    with patch("src.tools.jobscout.cli.HhScraper", return_value=mock_scraper):
        result = runner.invoke(app, [
            "jobs", "search", "hh",
            "--query", "маникюр",
            "--city", "Уфа",
            "--output", "vacancies.json",
        ])

    assert result.exit_code == 0, result.output
    out = tmp_path / "data" / "json" / "vacancies.json"
    assert out.exists()
    data = json.loads(out.read_text())
    assert len(data) == 1
    assert data[0]["title"] == "Мастер маникюра"


def test_jobs_search_hh_empty_result(tmp_path, monkeypatch):
    """search hh сохраняет пустой массив при отсутствии вакансий."""
    monkeypatch.chdir(tmp_path)

    mock_scraper = AsyncMock()
    mock_scraper.search = AsyncMock(return_value=[])

    with patch("src.tools.jobscout.cli.HhScraper", return_value=mock_scraper):
        result = runner.invoke(app, [
            "jobs", "search", "hh",
            "--query", "ничегонет",
            "--city", "Уфа",
            "--output", "vacancies.json",
        ])

    assert result.exit_code == 0, result.output
    out = tmp_path / "data" / "json" / "vacancies.json"
    assert out.exists()
    assert json.loads(out.read_text()) == []


# ─── jobs search avito ────────────────────────────────────────────────────────


def test_jobs_search_avito_help():
    """Команда search avito показывает справку."""
    result = runner.invoke(app, ["jobs", "search", "avito", "--help"])
    assert result.exit_code == 0
    assert "--query" in result.output


def test_jobs_search_avito_runs(tmp_path, monkeypatch):
    """search avito выполняется и сохраняет результат."""
    monkeypatch.chdir(tmp_path)
    vacancies = [make_vacancy(source="avito", source_url="https://avito.ru/ufa/1")]

    mock_scraper = AsyncMock()
    mock_scraper.scrape = AsyncMock(return_value=vacancies)

    mock_context = AsyncMock()
    mock_manager = AsyncMock()
    mock_manager.__aenter__ = AsyncMock(return_value=mock_manager)
    mock_manager.__aexit__ = AsyncMock(return_value=False)
    mock_manager.new_context = AsyncMock(return_value=mock_context)

    with patch("src.tools.jobscout.cli.BrowserManager", return_value=mock_manager), \
         patch("src.tools.jobscout.cli.AvitoJobScraper", return_value=mock_scraper):
        result = runner.invoke(app, [
            "jobs", "search", "avito",
            "--query", "маникюр",
            "--city", "Уфа",
            "--output", "avito_vacancies.json",
        ])

    assert result.exit_code == 0, result.output
    assert (tmp_path / "data" / "json" / "avito_vacancies.json").exists()


# ─── jobs enrich ──────────────────────────────────────────────────────────────


def test_jobs_enrich_help():
    """Команда enrich показывает справку."""
    result = runner.invoke(app, ["jobs", "enrich", "--help"])
    assert result.exit_code == 0
    assert "--source" in result.output
    assert "--threshold" in result.output


def test_jobs_enrich_missing_file():
    """enrich сообщает об ошибке при отсутствующем файле."""
    result = runner.invoke(app, ["jobs", "enrich", "/nonexistent/file.json"])
    assert result.exit_code != 0


def test_jobs_enrich_invalid_json(tmp_path):
    """enrich сообщает об ошибке при невалидном JSON."""
    bad_file = tmp_path / "bad.json"
    bad_file.write_text("not json", encoding="utf-8")

    result = runner.invoke(app, ["jobs", "enrich", str(bad_file)])
    assert result.exit_code != 0


def test_jobs_enrich_not_array(tmp_path):
    """enrich сообщает об ошибке если JSON не массив."""
    bad_file = tmp_path / "bad.json"
    bad_file.write_text('{"name": "test"}', encoding="utf-8")

    result = runner.invoke(app, ["jobs", "enrich", str(bad_file)])
    assert result.exit_code != 0


def test_jobs_enrich_unknown_source(tmp_path):
    """enrich сообщает об ошибке при неизвестном источнике."""
    input_file = tmp_path / "orgs.json"
    input_file.write_text('[{"name": "Студия"}]', encoding="utf-8")

    result = runner.invoke(app, [
        "jobs", "enrich", str(input_file),
        "--source", "unknownsource",
    ])
    assert result.exit_code != 0


def test_jobs_enrich_adds_vacancies(tmp_path, monkeypatch):
    """enrich добавляет вакансии к организациям через fuzzy matching."""
    monkeypatch.chdir(tmp_path)
    input_file = tmp_path / "orgs.json"

    orgs = [
        {"name": "Студия Colorstar", "city": "Уфа"},
        {"name": "Nail Bar", "city": "Уфа"},
    ]
    input_file.write_text(json.dumps(orgs, ensure_ascii=False), encoding="utf-8")

    # Вакансии: одна совпадёт с "Студия Colorstar"
    matched_vacancy = make_vacancy(company_name="Студия Colorstar")
    no_match_vacancy = make_vacancy(company_name="Совсем другая компания")

    mock_scraper = AsyncMock()
    mock_scraper.search = AsyncMock(side_effect=[
        [matched_vacancy, no_match_vacancy],  # для первой org
        [],                                    # для второй org
    ])

    with patch("src.tools.jobscout.cli.HhScraper", return_value=mock_scraper):
        result = runner.invoke(app, [
            "jobs", "enrich", str(input_file),
            "--output", "enriched.json",
            "--threshold", "70",
        ])

    assert result.exit_code == 0, result.output
    out = tmp_path / "data" / "json" / "enriched.json"
    assert out.exists()
    data = json.loads(out.read_text())

    # Первая org должна быть обогащена
    assert "_enriched" in data[0]
    assert "jobs" in data[0]["_enriched"]
    assert len(data[0]["_enriched"]["jobs"]) == 1
    assert data[0]["_enriched"]["jobs"][0]["company_name"] == "Студия Colorstar"

    # Вторая org не обогащена
    assert "_enriched" not in data[1]


def test_jobs_enrich_overwrites_input_by_default(tmp_path):
    """enrich перезаписывает входной файл если --output не указан."""
    input_file = tmp_path / "orgs.json"
    orgs = [{"name": "Студия", "city": "Уфа"}]
    input_file.write_text(json.dumps(orgs, ensure_ascii=False), encoding="utf-8")

    mock_scraper = AsyncMock()
    mock_scraper.search = AsyncMock(return_value=[])

    with patch("src.tools.jobscout.cli.HhScraper", return_value=mock_scraper):
        result = runner.invoke(app, ["jobs", "enrich", str(input_file)])

    assert result.exit_code == 0, result.output
    # Файл всё ещё существует (перезаписан)
    assert input_file.exists()


# ─── jobs команды в корневом CLI ──────────────────────────────────────────────


def test_jobs_help():
    """Команда jobs показывает справку."""
    result = runner.invoke(app, ["jobs", "--help"])
    assert result.exit_code == 0
    assert "search" in result.output
    assert "enrich" in result.output
