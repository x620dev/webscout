"""Тесты CLI LegalScout (tools/legalscout/cli.py)."""

import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from typer.testing import CliRunner

from src.cli import app
from src.tools.legalscout.models import LegalEntity

runner = CliRunner()


# ─── Вспомогательные фикстуры ─────────────────────────────────────────────────


def make_entity(**kwargs) -> LegalEntity:
    """Создать тестовый LegalEntity с дефолтными полями."""
    defaults = {
        "source": "egrul",
        "source_url": "https://egrul.nalog.ru/",
        "name": 'ООО "КОЛОРСТАР"',
        "inn": "0277123456",
        "ogrn": "1027700000000",
        "registration_date": "15.04.2010",
        "address": "г. Уфа, ул. Ленина, д. 1",
        "status": "действующее",
    }
    defaults.update(kwargs)
    return LegalEntity(**defaults)


# ─── legal help ───────────────────────────────────────────────────────────────


def test_legal_help():
    """Команда legal показывает справку."""
    result = runner.invoke(app, ["legal", "--help"])
    assert result.exit_code == 0
    assert "search" in result.output
    assert "enrich" in result.output


# ─── legal search ─────────────────────────────────────────────────────────────


def test_legal_search_help():
    """Команда search показывает справку."""
    result = runner.invoke(app, ["legal", "search", "--help"])
    assert result.exit_code == 0
    assert "egrul" in result.output
    assert "rusprofile" in result.output


def test_legal_search_egrul_help():
    """Команда search egrul показывает справку."""
    result = runner.invoke(app, ["legal", "search", "egrul", "--help"])
    assert result.exit_code == 0
    assert "--name" in result.output
    assert "--inn" in result.output


def test_legal_search_rusprofile_help():
    """Команда search rusprofile показывает справку."""
    result = runner.invoke(app, ["legal", "search", "rusprofile", "--help"])
    assert result.exit_code == 0
    assert "--name" in result.output


def test_legal_search_egrul_no_args():
    """search egrul без --name и --inn сообщает об ошибке."""
    result = runner.invoke(app, ["legal", "search", "egrul"])
    assert result.exit_code != 0


def test_legal_search_rusprofile_no_args():
    """search rusprofile без --name и --inn сообщает об ошибке."""
    result = runner.invoke(app, ["legal", "search", "rusprofile"])
    assert result.exit_code != 0


def test_legal_search_egrul_by_name(tmp_path):
    """search egrul --name сохраняет результат в JSON."""
    out = tmp_path / "legal.json"
    entity = make_entity()

    mock_scraper = AsyncMock()
    mock_scraper.search = AsyncMock(return_value=[entity])

    with patch("src.tools.legalscout.cli.EgrulScraper", return_value=mock_scraper):
        result = runner.invoke(app, [
            "legal", "search", "egrul",
            "--name", "Колорстар",
            "--city", "Уфа",
            "--output", str(out),
        ])

    assert result.exit_code == 0, result.output
    assert out.exists()
    data = json.loads(out.read_text())
    assert isinstance(data, list)
    assert len(data) == 1
    assert data[0]["inn"] == "0277123456"


def test_legal_search_egrul_by_inn(tmp_path):
    """search egrul --inn сохраняет результат в JSON."""
    out = tmp_path / "legal.json"
    entity = make_entity()

    mock_scraper = AsyncMock()
    mock_scraper.search = AsyncMock(return_value=[entity])

    with patch("src.tools.legalscout.cli.EgrulScraper", return_value=mock_scraper):
        result = runner.invoke(app, [
            "legal", "search", "egrul",
            "--inn", "0277123456",
            "--output", str(out),
        ])

    assert result.exit_code == 0, result.output
    assert out.exists()


def test_legal_search_rusprofile_runs(tmp_path):
    """search rusprofile --name сохраняет результат в JSON."""
    out = tmp_path / "legal.json"
    entity = make_entity(source="rusprofile", source_url="https://www.rusprofile.ru/id/12345")

    mock_scraper = AsyncMock()
    mock_scraper.search = AsyncMock(return_value=[entity])

    mock_context = AsyncMock()
    mock_manager = AsyncMock()
    mock_manager.__aenter__ = AsyncMock(return_value=mock_manager)
    mock_manager.__aexit__ = AsyncMock(return_value=False)
    mock_manager.new_context = AsyncMock(return_value=mock_context)

    with patch("src.tools.legalscout.cli.BrowserManager", return_value=mock_manager), \
         patch("src.tools.legalscout.cli.RusprofileScraper", return_value=mock_scraper):
        result = runner.invoke(app, [
            "legal", "search", "rusprofile",
            "--name", "Колорстар",
            "--output", str(out),
        ])

    assert result.exit_code == 0, result.output
    assert out.exists()
    data = json.loads(out.read_text())
    assert len(data) == 1
    assert data[0]["source"] == "rusprofile"


def test_legal_search_rusprofile_empty(tmp_path):
    """search rusprofile завершается без ошибок если ничего не найдено."""
    mock_scraper = AsyncMock()
    mock_scraper.search = AsyncMock(return_value=[])

    mock_context = AsyncMock()
    mock_manager = AsyncMock()
    mock_manager.__aenter__ = AsyncMock(return_value=mock_manager)
    mock_manager.__aexit__ = AsyncMock(return_value=False)
    mock_manager.new_context = AsyncMock(return_value=mock_context)

    with patch("src.tools.legalscout.cli.BrowserManager", return_value=mock_manager), \
         patch("src.tools.legalscout.cli.RusprofileScraper", return_value=mock_scraper):
        result = runner.invoke(app, [
            "legal", "search", "rusprofile",
            "--name", "НесуществующаяКомпания",
        ])

    assert result.exit_code == 0


# ─── legal enrich ─────────────────────────────────────────────────────────────


def test_legal_enrich_help():
    """Команда enrich показывает справку."""
    result = runner.invoke(app, ["legal", "enrich", "--help"])
    assert result.exit_code == 0


def test_legal_enrich_missing_file():
    """enrich сообщает об ошибке при отсутствующем файле."""
    result = runner.invoke(app, ["legal", "enrich", "/nonexistent/file.json"])
    assert result.exit_code != 0


def test_legal_enrich_invalid_json(tmp_path):
    """enrich сообщает об ошибке при невалидном JSON."""
    bad_file = tmp_path / "bad.json"
    bad_file.write_text("not json", encoding="utf-8")
    result = runner.invoke(app, ["legal", "enrich", str(bad_file)])
    assert result.exit_code != 0


def test_legal_enrich_not_array(tmp_path):
    """enrich сообщает об ошибке если JSON не массив."""
    bad_file = tmp_path / "bad.json"
    bad_file.write_text('{"name": "test"}', encoding="utf-8")
    result = runner.invoke(app, ["legal", "enrich", str(bad_file)])
    assert result.exit_code != 0


def test_legal_enrich_unknown_source(tmp_path):
    """enrich сообщает об ошибке при неизвестном источнике."""
    input_file = tmp_path / "orgs.json"
    input_file.write_text('[{"name": "Студия"}]', encoding="utf-8")
    result = runner.invoke(app, [
        "legal", "enrich", str(input_file),
        "--source", "unknown_source",
    ])
    assert result.exit_code != 0


def test_legal_enrich_egrul(tmp_path):
    """enrich обогащает организации юрданными из ЕГРЮЛ."""
    input_file = tmp_path / "orgs.json"
    out_file = tmp_path / "enriched.json"

    orgs = [
        {"name": 'ООО "КОЛОРСТАР"', "city": "Уфа"},
        {"name": "Без ИНН"},
    ]
    input_file.write_text(json.dumps(orgs, ensure_ascii=False), encoding="utf-8")

    entity = make_entity()
    mock_scraper = AsyncMock()
    mock_scraper.search = AsyncMock(return_value=[entity])

    with patch("src.tools.legalscout.cli.EgrulScraper", return_value=mock_scraper):
        result = runner.invoke(app, [
            "legal", "enrich", str(input_file),
            "--source", "egrul",
            "--output", str(out_file),
        ])

    assert result.exit_code == 0, result.output
    assert out_file.exists()
    data = json.loads(out_file.read_text())

    # Первая организация обогащена (fuzzy match "Колорстар" ↔ "Колорстар")
    assert "_enriched" in data[0]
    assert "legal" in data[0]["_enriched"]
    assert data[0]["_enriched"]["legal"]["inn"] == "0277123456"


def test_legal_enrich_egrul_no_match(tmp_path):
    """enrich не обогащает если нет совпадения по fuzzy matching."""
    input_file = tmp_path / "orgs.json"

    orgs = [{"name": "Студия без совпадения", "city": "Уфа"}]
    input_file.write_text(json.dumps(orgs, ensure_ascii=False), encoding="utf-8")

    # Возвращаем компанию с совсем другим именем
    entity = make_entity(name="ООО АБСОЛЮТНО ДРУГОЕ")
    mock_scraper = AsyncMock()
    mock_scraper.search = AsyncMock(return_value=[entity])

    with patch("src.tools.legalscout.cli.EgrulScraper", return_value=mock_scraper):
        result = runner.invoke(app, [
            "legal", "enrich", str(input_file),
            "--source", "egrul",
            "--threshold", "95",  # высокий порог — не должно совпасть
        ])

    assert result.exit_code == 0
    data = json.loads(input_file.read_text())
    assert "_enriched" not in data[0]


def test_legal_enrich_overwrites_input_by_default(tmp_path):
    """enrich перезаписывает входной файл если --output не указан."""
    input_file = tmp_path / "orgs.json"
    orgs = [{"name": "Студия", "city": "Уфа"}]
    input_file.write_text(json.dumps(orgs, ensure_ascii=False), encoding="utf-8")

    mock_scraper = AsyncMock()
    mock_scraper.search = AsyncMock(return_value=[])

    with patch("src.tools.legalscout.cli.EgrulScraper", return_value=mock_scraper):
        result = runner.invoke(app, [
            "legal", "enrich", str(input_file),
            "--source", "egrul",
        ])

    assert result.exit_code == 0
    assert input_file.exists()


def test_legal_enrich_rusprofile(tmp_path):
    """enrich обогащает организации юрданными из Rusprofile."""
    input_file = tmp_path / "orgs.json"
    out_file = tmp_path / "enriched.json"

    orgs = [{"name": 'ООО "КОЛОРСТАР"', "city": "Уфа"}]
    input_file.write_text(json.dumps(orgs, ensure_ascii=False), encoding="utf-8")

    entity = make_entity(source="rusprofile", source_url="https://www.rusprofile.ru/id/12345")
    mock_scraper = AsyncMock()
    mock_scraper.search = AsyncMock(return_value=[entity])

    mock_context = AsyncMock()
    mock_manager = AsyncMock()
    mock_manager.__aenter__ = AsyncMock(return_value=mock_manager)
    mock_manager.__aexit__ = AsyncMock(return_value=False)
    mock_manager.new_context = AsyncMock(return_value=mock_context)

    with patch("src.tools.legalscout.cli.BrowserManager", return_value=mock_manager), \
         patch("src.tools.legalscout.cli.RusprofileScraper", return_value=mock_scraper):
        result = runner.invoke(app, [
            "legal", "enrich", str(input_file),
            "--source", "rusprofile",
            "--output", str(out_file),
        ])

    assert result.exit_code == 0, result.output
    data = json.loads(out_file.read_text())
    assert "_enriched" in data[0]
    assert data[0]["_enriched"]["legal"]["source"] == "rusprofile"


# ─── _find_legal_match ────────────────────────────────────────────────────────


def test_find_legal_match_found():
    """_find_legal_match находит совпадение."""
    from src.tools.legalscout.cli import _find_legal_match

    entities = [make_entity(name='ООО "КОЛОРСТАР"')]
    result = _find_legal_match("Колорстар", entities, threshold=60.0)
    assert result is not None
    assert result.inn == "0277123456"


def test_find_legal_match_empty_entities():
    """_find_legal_match возвращает None при пустом списке."""
    from src.tools.legalscout.cli import _find_legal_match

    result = _find_legal_match("Колорстар", [], threshold=60.0)
    assert result is None


def test_find_legal_match_high_threshold():
    """_find_legal_match возвращает None при высоком пороге без совпадения."""
    from src.tools.legalscout.cli import _find_legal_match

    entities = [make_entity(name="ООО АБСОЛЮТНО ДРУГОЕ")]
    result = _find_legal_match("Колорстар", entities, threshold=99.0)
    assert result is None
