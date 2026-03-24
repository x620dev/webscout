"""Тесты CLI PriceScout (tools/pricescout/cli.py)."""

import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from typer.testing import CliRunner

from src.cli import app
from src.tools.pricescout.models import PriceList, ServicePrice

runner = CliRunner()


# ─── Вспомогательные фикстуры ─────────────────────────────────────────────────


def make_price_list(**kwargs) -> PriceList:
    """Создать тестовый PriceList с дефолтными полями."""
    defaults = {
        "source": "yclients",
        "source_url": "https://yclients.com/company/1/",
        "fetched_from": "https://yclients.com/company/1/",
        "org_name": "Студия Colorstar",
        "services": [
            ServicePrice(name="Маникюр", price=800, category="Маникюр"),
            ServicePrice(name="Педикюр", price=1200, category="Педикюр"),
        ],
    }
    defaults.update(kwargs)
    return PriceList(**defaults)


# ─── prices help ──────────────────────────────────────────────────────────────


def test_prices_help():
    """Команда prices показывает справку."""
    result = runner.invoke(app, ["prices", "--help"])
    assert result.exit_code == 0
    assert "fetch" in result.output
    assert "collect" in result.output


# ─── prices fetch ─────────────────────────────────────────────────────────────


def test_prices_fetch_help():
    """Команда fetch показывает справку."""
    result = runner.invoke(app, ["prices", "fetch", "--help"])
    assert result.exit_code == 0
    assert "yclients" in result.output
    assert "dikidi" in result.output


def test_prices_fetch_yclients_help():
    """Команда fetch yclients показывает справку."""
    result = runner.invoke(app, ["prices", "fetch", "yclients", "--help"])
    assert result.exit_code == 0
    assert "--url" in result.output


def test_prices_fetch_dikidi_help():
    """Команда fetch dikidi показывает справку."""
    result = runner.invoke(app, ["prices", "fetch", "dikidi", "--help"])
    assert result.exit_code == 0
    assert "--url" in result.output


def test_prices_fetch_yclients_missing_url():
    """fetch yclients требует --url."""
    result = runner.invoke(app, ["prices", "fetch", "yclients"])
    assert result.exit_code != 0


def test_prices_fetch_dikidi_missing_url():
    """fetch dikidi требует --url."""
    result = runner.invoke(app, ["prices", "fetch", "dikidi"])
    assert result.exit_code != 0


def test_prices_fetch_yclients_runs(tmp_path, monkeypatch):
    """fetch yclients сохраняет результат в JSON."""
    monkeypatch.chdir(tmp_path)
    price_list = make_price_list()

    mock_scraper = AsyncMock()
    mock_scraper.fetch = AsyncMock(return_value=price_list)

    mock_context = AsyncMock()
    mock_manager = AsyncMock()
    mock_manager.__aenter__ = AsyncMock(return_value=mock_manager)
    mock_manager.__aexit__ = AsyncMock(return_value=False)
    mock_manager.new_context = AsyncMock(return_value=mock_context)

    with patch("src.tools.pricescout.cli.BrowserManager", return_value=mock_manager), \
         patch("src.tools.pricescout.cli.YclientsScraper", return_value=mock_scraper):
        result = runner.invoke(app, [
            "prices", "fetch", "yclients",
            "--url", "https://yclients.com/company/1/",
            "--output", "prices.json",
        ])

    assert result.exit_code == 0, result.output
    out = tmp_path / "data" / "json" / "prices.json"
    assert out.exists()
    data = json.loads(out.read_text())
    assert isinstance(data, list)
    assert len(data) == 1
    assert data[0]["org_name"] == "Студия Colorstar"
    assert len(data[0]["services"]) == 2


def test_prices_fetch_dikidi_runs(tmp_path, monkeypatch):
    """fetch dikidi сохраняет результат в JSON."""
    monkeypatch.chdir(tmp_path)
    price_list = make_price_list(
        source="dikidi",
        source_url="https://dikidi.net/salon/456",
        fetched_from="https://dikidi.net/salon/456",
    )

    mock_scraper = AsyncMock()
    mock_scraper.fetch = AsyncMock(return_value=price_list)

    mock_context = AsyncMock()
    mock_manager = AsyncMock()
    mock_manager.__aenter__ = AsyncMock(return_value=mock_manager)
    mock_manager.__aexit__ = AsyncMock(return_value=False)
    mock_manager.new_context = AsyncMock(return_value=mock_context)

    with patch("src.tools.pricescout.cli.BrowserManager", return_value=mock_manager), \
         patch("src.tools.pricescout.cli.DikidiScraper", return_value=mock_scraper):
        result = runner.invoke(app, [
            "prices", "fetch", "dikidi",
            "--url", "https://dikidi.net/salon/456",
            "--output", "prices.json",
        ])

    assert result.exit_code == 0, result.output
    assert (tmp_path / "data" / "json" / "prices.json").exists()


def test_prices_fetch_yclients_scraper_fails(tmp_path, monkeypatch):
    """fetch yclients сообщает об ошибке если скрапер вернул None."""
    monkeypatch.chdir(tmp_path)

    mock_scraper = AsyncMock()
    mock_scraper.fetch = AsyncMock(return_value=None)

    mock_context = AsyncMock()
    mock_manager = AsyncMock()
    mock_manager.__aenter__ = AsyncMock(return_value=mock_manager)
    mock_manager.__aexit__ = AsyncMock(return_value=False)
    mock_manager.new_context = AsyncMock(return_value=mock_context)

    with patch("src.tools.pricescout.cli.BrowserManager", return_value=mock_manager), \
         patch("src.tools.pricescout.cli.YclientsScraper", return_value=mock_scraper):
        result = runner.invoke(app, [
            "prices", "fetch", "yclients",
            "--url", "https://yclients.com/company/1/",
            "--output", "prices.json",
        ])

    assert result.exit_code != 0


# ─── prices collect ───────────────────────────────────────────────────────────


def test_prices_collect_help():
    """Команда collect показывает справку."""
    result = runner.invoke(app, ["prices", "collect", "--help"])
    assert result.exit_code == 0


def test_prices_collect_missing_file():
    """collect сообщает об ошибке при отсутствующем файле."""
    result = runner.invoke(app, ["prices", "collect", "/nonexistent/file.json"])
    assert result.exit_code != 0


def test_prices_collect_invalid_json(tmp_path):
    """collect сообщает об ошибке при невалидном JSON."""
    bad_file = tmp_path / "bad.json"
    bad_file.write_text("not json", encoding="utf-8")
    result = runner.invoke(app, ["prices", "collect", str(bad_file)])
    assert result.exit_code != 0


def test_prices_collect_not_array(tmp_path):
    """collect сообщает об ошибке если JSON не массив."""
    bad_file = tmp_path / "bad.json"
    bad_file.write_text('{"name": "test"}', encoding="utf-8")
    result = runner.invoke(app, ["prices", "collect", str(bad_file)])
    assert result.exit_code != 0


def test_prices_collect_no_booking_urls(tmp_path):
    """collect завершается без ошибок если нет online_booking URL."""
    input_file = tmp_path / "orgs.json"
    orgs = [{"name": "Студия", "city": "Уфа"}]
    input_file.write_text(json.dumps(orgs, ensure_ascii=False), encoding="utf-8")

    result = runner.invoke(app, ["prices", "collect", str(input_file)])
    assert result.exit_code == 0


def test_prices_collect_yclients(tmp_path, monkeypatch):
    """collect обогащает организации прайсами с YCLIENTS."""
    monkeypatch.chdir(tmp_path)
    input_file = tmp_path / "orgs.json"

    orgs = [
        {
            "name": "Студия Colorstar",
            "city": "Уфа",
            "online_booking": "https://yclients.com/company/12345/",
        },
        {
            "name": "Без бронирования",
            "city": "Уфа",
        },
    ]
    input_file.write_text(json.dumps(orgs, ensure_ascii=False), encoding="utf-8")

    price_list = make_price_list()
    mock_scraper = AsyncMock()
    mock_scraper.fetch = AsyncMock(return_value=price_list)

    mock_context = AsyncMock()
    mock_manager = AsyncMock()
    mock_manager.__aenter__ = AsyncMock(return_value=mock_manager)
    mock_manager.__aexit__ = AsyncMock(return_value=False)
    mock_manager.new_context = AsyncMock(return_value=mock_context)

    with patch("src.tools.pricescout.cli.BrowserManager", return_value=mock_manager), \
         patch("src.tools.pricescout.cli.YclientsScraper", return_value=mock_scraper):
        result = runner.invoke(app, [
            "prices", "collect", str(input_file),
            "--output", "enriched.json",
        ])

    assert result.exit_code == 0, result.output
    out = tmp_path / "data" / "json" / "enriched.json"
    assert out.exists()
    data = json.loads(out.read_text())

    # Первая организация должна быть обогащена
    assert "_enriched" in data[0]
    assert "prices" in data[0]["_enriched"]
    assert data[0]["_enriched"]["prices"]["org_name"] == "Студия Colorstar"

    # Вторая не обогащена
    assert "_enriched" not in data[1]


def test_prices_collect_dikidi(tmp_path, monkeypatch):
    """collect обогащает организации прайсами с Dikidi."""
    monkeypatch.chdir(tmp_path)
    input_file = tmp_path / "orgs.json"

    orgs = [{"name": "Nail Bar", "online_booking": "https://dikidi.net/salon/789"}]
    input_file.write_text(json.dumps(orgs, ensure_ascii=False), encoding="utf-8")

    price_list = make_price_list(
        source="dikidi",
        source_url="https://dikidi.net/salon/789",
        fetched_from="https://dikidi.net/salon/789",
        org_name="Nail Bar",
    )
    mock_scraper = AsyncMock()
    mock_scraper.fetch = AsyncMock(return_value=price_list)

    mock_context = AsyncMock()
    mock_manager = AsyncMock()
    mock_manager.__aenter__ = AsyncMock(return_value=mock_manager)
    mock_manager.__aexit__ = AsyncMock(return_value=False)
    mock_manager.new_context = AsyncMock(return_value=mock_context)

    with patch("src.tools.pricescout.cli.BrowserManager", return_value=mock_manager), \
         patch("src.tools.pricescout.cli.DikidiScraper", return_value=mock_scraper):
        result = runner.invoke(app, [
            "prices", "collect", str(input_file),
            "--output", "enriched.json",
        ])

    assert result.exit_code == 0, result.output
    out = tmp_path / "data" / "json" / "enriched.json"
    data = json.loads(out.read_text())
    assert "_enriched" in data[0]
    assert data[0]["_enriched"]["prices"]["source"] == "dikidi"


def test_prices_collect_unknown_crm_skipped(tmp_path, monkeypatch):
    """collect пропускает организации с неизвестным CRM."""
    monkeypatch.chdir(tmp_path)
    input_file = tmp_path / "orgs.json"

    orgs = [{"name": "Студия", "online_booking": "https://unknowncrm.ru/booking/123"}]
    input_file.write_text(json.dumps(orgs, ensure_ascii=False), encoding="utf-8")

    mock_manager = AsyncMock()
    mock_manager.__aenter__ = AsyncMock(return_value=mock_manager)
    mock_manager.__aexit__ = AsyncMock(return_value=False)
    mock_manager.new_context = AsyncMock(return_value=AsyncMock())

    with patch("src.tools.pricescout.cli.BrowserManager", return_value=mock_manager):
        result = runner.invoke(app, [
            "prices", "collect", str(input_file),
            "--output", "enriched.json",
        ])

    assert result.exit_code == 0
    out = tmp_path / "data" / "json" / "enriched.json"
    data = json.loads(out.read_text())
    # Пропущено — нет обогащения
    assert "_enriched" not in data[0]


def test_prices_collect_overwrites_input_by_default(tmp_path):
    """collect перезаписывает входной файл если --output не указан."""
    input_file = tmp_path / "orgs.json"
    orgs = [{"name": "Студия", "city": "Уфа"}]
    input_file.write_text(json.dumps(orgs, ensure_ascii=False), encoding="utf-8")

    result = runner.invoke(app, ["prices", "collect", str(input_file)])

    assert result.exit_code == 0
    assert input_file.exists()


# ─── _detect_crm ──────────────────────────────────────────────────────────────


def test_detect_crm_yclients():
    """_detect_crm определяет YCLIENTS по домену."""
    from src.tools.pricescout.cli import _detect_crm

    assert _detect_crm("https://yclients.com/company/123/") == "yclients"
    assert _detect_crm("https://n.yclients.com/company/123/") == "yclients"
    assert _detect_crm("https://w.yclients.com/o/123") == "yclients"


def test_detect_crm_dikidi():
    """_detect_crm определяет Dikidi по домену."""
    from src.tools.pricescout.cli import _detect_crm

    assert _detect_crm("https://dikidi.net/salon/456") == "dikidi"
    assert _detect_crm("https://dikidi.net/company/789") == "dikidi"


def test_detect_crm_unknown():
    """_detect_crm возвращает None для неизвестных доменов."""
    from src.tools.pricescout.cli import _detect_crm

    assert _detect_crm("https://example.com/booking") is None
    assert _detect_crm("https://bookform.ru/123") is None
    assert _detect_crm("") is None
