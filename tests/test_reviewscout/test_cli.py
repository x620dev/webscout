"""Тесты CLI ReviewScout (tools/reviewscout/cli.py)."""

import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from typer.testing import CliRunner

from src.cli import app
from src.tools.reviewscout.models import Review, ReviewSummary

runner = CliRunner()


# ─── Вспомогательные фикстуры ─────────────────────────────────────────────────


def make_summary(**kwargs) -> ReviewSummary:
    """Создать тестовый ReviewSummary с дефолтными полями."""
    defaults = {
        "source": "yandex",
        "source_url": "https://yandex.ru/maps/org/salon/123456789/reviews/",
        "org_name": "Студия Colorstar",
        "rating": 4.8,
        "reviews_count": 42,
        "reviews": [
            Review(author="Иван", rating=5.0, text="Отлично!"),
            Review(author="Мария", rating=4.5, text="Хорошо"),
        ],
    }
    defaults.update(kwargs)
    return ReviewSummary(**defaults)


# ─── reviews help ──────────────────────────────────────────────────────────────


def test_reviews_help():
    """Команда reviews показывает справку."""
    result = runner.invoke(app, ["reviews", "--help"])
    assert result.exit_code == 0
    assert "scrape" in result.output
    assert "enrich" in result.output


# ─── reviews scrape ───────────────────────────────────────────────────────────


def test_reviews_scrape_help():
    """Команда scrape показывает справку."""
    result = runner.invoke(app, ["reviews", "scrape", "--help"])
    assert result.exit_code == 0
    assert "yandex" in result.output
    assert "flamp" in result.output


def test_reviews_scrape_yandex_help():
    """Команда scrape yandex показывает справку."""
    result = runner.invoke(app, ["reviews", "scrape", "yandex", "--help"])
    assert result.exit_code == 0
    assert "--url" in result.output


def test_reviews_scrape_flamp_help():
    """Команда scrape flamp показывает справку."""
    result = runner.invoke(app, ["reviews", "scrape", "flamp", "--help"])
    assert result.exit_code == 0
    assert "--url" in result.output


def test_reviews_scrape_yandex_missing_url():
    """scrape yandex требует --url."""
    result = runner.invoke(app, ["reviews", "scrape", "yandex"])
    assert result.exit_code != 0


def test_reviews_scrape_flamp_missing_url():
    """scrape flamp требует --url."""
    result = runner.invoke(app, ["reviews", "scrape", "flamp"])
    assert result.exit_code != 0


def test_reviews_scrape_yandex_runs(tmp_path):
    """scrape yandex сохраняет результат в JSON."""
    out = tmp_path / "reviews.json"
    summary = make_summary()

    mock_scraper = AsyncMock()
    mock_scraper.scrape = AsyncMock(return_value=summary)

    mock_context = AsyncMock()
    mock_manager = AsyncMock()
    mock_manager.__aenter__ = AsyncMock(return_value=mock_manager)
    mock_manager.__aexit__ = AsyncMock(return_value=False)
    mock_manager.new_context = AsyncMock(return_value=mock_context)

    with patch("src.tools.reviewscout.cli.BrowserManager", return_value=mock_manager), \
         patch("src.tools.reviewscout.cli.YandexReviewsScraper", return_value=mock_scraper):
        result = runner.invoke(app, [
            "reviews", "scrape", "yandex",
            "--url", "https://yandex.ru/maps/org/salon/123456789/",
            "--output", str(out),
        ])

    assert result.exit_code == 0, result.output
    assert out.exists()
    data = json.loads(out.read_text())
    assert isinstance(data, list)
    assert len(data) == 1
    assert data[0]["org_name"] == "Студия Colorstar"
    assert len(data[0]["reviews"]) == 2


def test_reviews_scrape_flamp_runs(tmp_path):
    """scrape flamp сохраняет результат в JSON."""
    out = tmp_path / "reviews.json"
    summary = make_summary(
        source="flamp",
        source_url="https://ufa.flamp.ru/firm/salon-123",
    )

    mock_scraper = AsyncMock()
    mock_scraper.scrape = AsyncMock(return_value=summary)

    mock_context = AsyncMock()
    mock_manager = AsyncMock()
    mock_manager.__aenter__ = AsyncMock(return_value=mock_manager)
    mock_manager.__aexit__ = AsyncMock(return_value=False)
    mock_manager.new_context = AsyncMock(return_value=mock_context)

    with patch("src.tools.reviewscout.cli.BrowserManager", return_value=mock_manager), \
         patch("src.tools.reviewscout.cli.FlampScraper", return_value=mock_scraper):
        result = runner.invoke(app, [
            "reviews", "scrape", "flamp",
            "--url", "https://ufa.flamp.ru/firm/salon-123",
            "--output", str(out),
        ])

    assert result.exit_code == 0, result.output
    assert out.exists()


def test_reviews_scrape_yandex_fails(tmp_path):
    """scrape yandex сообщает об ошибке если скрапер вернул None."""
    out = tmp_path / "reviews.json"

    mock_scraper = AsyncMock()
    mock_scraper.scrape = AsyncMock(return_value=None)

    mock_context = AsyncMock()
    mock_manager = AsyncMock()
    mock_manager.__aenter__ = AsyncMock(return_value=mock_manager)
    mock_manager.__aexit__ = AsyncMock(return_value=False)
    mock_manager.new_context = AsyncMock(return_value=mock_context)

    with patch("src.tools.reviewscout.cli.BrowserManager", return_value=mock_manager), \
         patch("src.tools.reviewscout.cli.YandexReviewsScraper", return_value=mock_scraper):
        result = runner.invoke(app, [
            "reviews", "scrape", "yandex",
            "--url", "https://yandex.ru/maps/org/salon/1/",
            "--output", str(out),
        ])

    assert result.exit_code != 0


# ─── reviews enrich ───────────────────────────────────────────────────────────


def test_reviews_enrich_help():
    """Команда enrich показывает справку."""
    result = runner.invoke(app, ["reviews", "enrich", "--help"])
    assert result.exit_code == 0


def test_reviews_enrich_missing_file():
    """enrich сообщает об ошибке при отсутствующем файле."""
    result = runner.invoke(app, ["reviews", "enrich", "/nonexistent/file.json"])
    assert result.exit_code != 0


def test_reviews_enrich_invalid_json(tmp_path):
    """enrich сообщает об ошибке при невалидном JSON."""
    bad_file = tmp_path / "bad.json"
    bad_file.write_text("not json", encoding="utf-8")
    result = runner.invoke(app, ["reviews", "enrich", str(bad_file)])
    assert result.exit_code != 0


def test_reviews_enrich_not_array(tmp_path):
    """enrich сообщает об ошибке если JSON не массив."""
    bad_file = tmp_path / "bad.json"
    bad_file.write_text('{"name": "test"}', encoding="utf-8")
    result = runner.invoke(app, ["reviews", "enrich", str(bad_file)])
    assert result.exit_code != 0


def test_reviews_enrich_unknown_source(tmp_path):
    """enrich сообщает об ошибке при неизвестном источнике."""
    input_file = tmp_path / "orgs.json"
    input_file.write_text('[{"name": "Студия"}]', encoding="utf-8")
    result = runner.invoke(app, [
        "reviews", "enrich", str(input_file),
        "--source", "unknown_source",
    ])
    assert result.exit_code != 0


def test_reviews_enrich_no_urls(tmp_path):
    """enrich завершается без ошибок если нет подходящих URL."""
    input_file = tmp_path / "orgs.json"
    orgs = [{"name": "Студия без ссылок", "city": "Уфа"}]
    input_file.write_text(json.dumps(orgs, ensure_ascii=False), encoding="utf-8")

    result = runner.invoke(app, [
        "reviews", "enrich", str(input_file),
        "--source", "flamp",  # flamp использует flamp_url, которого нет
    ])
    assert result.exit_code == 0


def test_reviews_enrich_yandex(tmp_path):
    """enrich обогащает организации отзывами с Яндекс."""
    input_file = tmp_path / "orgs.json"
    out_file = tmp_path / "enriched.json"

    orgs = [
        {
            "name": "Студия Colorstar",
            "source": "yandex_maps",
            "source_url": "https://yandex.ru/maps/org/salon/123456789/",
        },
        {
            "name": "Без ссылки",
        },
    ]
    input_file.write_text(json.dumps(orgs, ensure_ascii=False), encoding="utf-8")

    summary = make_summary()
    mock_scraper = AsyncMock()
    mock_scraper.scrape = AsyncMock(return_value=summary)

    mock_context = AsyncMock()
    mock_manager = AsyncMock()
    mock_manager.__aenter__ = AsyncMock(return_value=mock_manager)
    mock_manager.__aexit__ = AsyncMock(return_value=False)
    mock_manager.new_context = AsyncMock(return_value=mock_context)

    with patch("src.tools.reviewscout.cli.BrowserManager", return_value=mock_manager), \
         patch("src.tools.reviewscout.cli.YandexReviewsScraper", return_value=mock_scraper):
        result = runner.invoke(app, [
            "reviews", "enrich", str(input_file),
            "--source", "yandex",
            "--output", str(out_file),
        ])

    assert result.exit_code == 0, result.output
    assert out_file.exists()
    data = json.loads(out_file.read_text())

    # Первая организация обогащена
    assert "_enriched" in data[0]
    assert "reviews" in data[0]["_enriched"]
    assert data[0]["_enriched"]["reviews"]["org_name"] == "Студия Colorstar"
    assert len(data[0]["_enriched"]["reviews"]["reviews"]) == 2

    # Вторая не обогащена
    assert "_enriched" not in data[1]


def test_reviews_enrich_flamp(tmp_path):
    """enrich обогащает организации отзывами с Flamp."""
    input_file = tmp_path / "orgs.json"
    out_file = tmp_path / "enriched.json"

    orgs = [
        {
            "name": "Nail Bar",
            "flamp_url": "https://ufa.flamp.ru/firm/nail-bar-123",
        }
    ]
    input_file.write_text(json.dumps(orgs, ensure_ascii=False), encoding="utf-8")

    summary = make_summary(
        source="flamp",
        source_url="https://ufa.flamp.ru/firm/nail-bar-123",
        org_name="Nail Bar",
    )
    mock_scraper = AsyncMock()
    mock_scraper.scrape = AsyncMock(return_value=summary)

    mock_context = AsyncMock()
    mock_manager = AsyncMock()
    mock_manager.__aenter__ = AsyncMock(return_value=mock_manager)
    mock_manager.__aexit__ = AsyncMock(return_value=False)
    mock_manager.new_context = AsyncMock(return_value=mock_context)

    with patch("src.tools.reviewscout.cli.BrowserManager", return_value=mock_manager), \
         patch("src.tools.reviewscout.cli.FlampScraper", return_value=mock_scraper):
        result = runner.invoke(app, [
            "reviews", "enrich", str(input_file),
            "--source", "flamp",
            "--output", str(out_file),
        ])

    assert result.exit_code == 0, result.output
    data = json.loads(out_file.read_text())
    assert "_enriched" in data[0]
    assert data[0]["_enriched"]["reviews"]["source"] == "flamp"


def test_reviews_enrich_overwrites_input_by_default(tmp_path):
    """enrich перезаписывает входной файл если --output не указан."""
    input_file = tmp_path / "orgs.json"
    orgs = [{"name": "Студия", "city": "Уфа"}]
    input_file.write_text(json.dumps(orgs, ensure_ascii=False), encoding="utf-8")

    result = runner.invoke(app, [
        "reviews", "enrich", str(input_file),
        "--source", "flamp",
    ])

    assert result.exit_code == 0
    assert input_file.exists()


# ─── _get_url_field ───────────────────────────────────────────────────────────


def test_get_url_field_yandex():
    """yandex использует source_url."""
    from src.tools.reviewscout.cli import _get_url_field
    assert _get_url_field("yandex") == "source_url"


def test_get_url_field_flamp():
    """flamp использует flamp_url."""
    from src.tools.reviewscout.cli import _get_url_field
    assert _get_url_field("flamp") == "flamp_url"


def test_get_url_field_unknown():
    """Неизвестный источник → source_url по умолчанию."""
    from src.tools.reviewscout.cli import _get_url_field
    assert _get_url_field("unknown") == "source_url"
