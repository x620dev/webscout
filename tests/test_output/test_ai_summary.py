"""Тесты для модуля ai_summary."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from src.core.models import Contacts, ScrapedEntity
from src.output.ai_summary import format_ai_summary, save_ai_summary


class FullEntity(ScrapedEntity):
    name: str
    rating: float | None = None
    reviews_count: int | None = None
    address: str | None = None
    contacts: Contacts = Contacts()
    working_hours: str | None = None
    categories: list[str] = []
    notes: str | None = None


@pytest.fixture
def full_entity() -> FullEntity:
    return FullEntity(
        name="Colorstar Nail Studio",
        rating=4.8,
        reviews_count=256,
        address="ул. Ленина, 12, Уфа",
        contacts=Contacts(
            phone=["+79991234567", "+79992345678"],
            website="colorstar.ru",
            email="info@colorstar.ru",
        ),
        working_hours="Пн–Вс 10:00–21:00",
        categories=["Маникюр", "Педикюр"],
        notes="Сеть салонов",
        source="yandex_maps",
        source_url="https://yandex.com/maps/org/colorstar/1307983921/",
    )


@pytest.fixture
def minimal_entity() -> ScrapedEntity:
    return ScrapedEntity(
        source="2gis",
        source_url="https://2gis.ru/ufa/firm/1234567890",
    )


# ─────────────────────────────────────────────────────────────────────────────
# Заголовок
# ─────────────────────────────────────────────────────────────────────────────


def test_header_contains_query(full_entity):
    text = format_ai_summary([full_entity], query="маникюр", city="Уфа")
    assert '"маникюр"' in text
    assert "Уфа" in text


def test_header_contains_source(full_entity):
    text = format_ai_summary([full_entity], source="yandex_maps")
    assert "yandex_maps" in text


def test_header_contains_count(full_entity, minimal_entity):
    text = format_ai_summary([full_entity, minimal_entity])
    assert "Найдено: 2" in text


def test_header_contains_date(full_entity):
    text = format_ai_summary([full_entity])
    assert re.search(r"\d{4}-\d{2}-\d{2}", text)


def test_header_no_query_placeholder(full_entity):
    """Без query заголовок всё равно корректен."""
    text = format_ai_summary([full_entity])
    assert "Результаты" in text


# ─────────────────────────────────────────────────────────────────────────────
# Тело сущности
# ─────────────────────────────────────────────────────────────────────────────


def test_entity_name_present(full_entity):
    text = format_ai_summary([full_entity])
    assert "Colorstar Nail Studio" in text


def test_entity_rating_present(full_entity):
    text = format_ai_summary([full_entity])
    assert "4.8" in text


def test_entity_reviews_count_present(full_entity):
    text = format_ai_summary([full_entity])
    assert "256" in text


def test_entity_address_present(full_entity):
    text = format_ai_summary([full_entity])
    assert "ул. Ленина, 12" in text


def test_entity_source_url_present(full_entity):
    text = format_ai_summary([full_entity])
    assert "https://yandex.com/maps/org/colorstar/1307983921/" in text


def test_entity_notes_present(full_entity):
    text = format_ai_summary([full_entity])
    assert "Сеть салонов" in text


def test_entity_separator(full_entity):
    text = format_ai_summary([full_entity])
    assert "---" in text


# ─────────────────────────────────────────────────────────────────────────────
# Минимальные данные
# ─────────────────────────────────────────────────────────────────────────────


def test_minimal_entity_no_crash(minimal_entity):
    text = format_ai_summary([minimal_entity])
    assert "---" in text


def test_minimal_entity_source_url(minimal_entity):
    text = format_ai_summary([minimal_entity])
    assert "https://2gis.ru/ufa/firm/1234567890" in text


def test_empty_list():
    text = format_ai_summary([])
    assert "Найдено: 0" in text


# ─────────────────────────────────────────────────────────────────────────────
# Несколько сущностей
# ─────────────────────────────────────────────────────────────────────────────


def test_multiple_entities_numbered(full_entity, minimal_entity):
    text = format_ai_summary([full_entity, minimal_entity])
    assert "## 1." in text
    assert "## 2." in text


def test_multiple_entities_separator_count(full_entity, minimal_entity):
    text = format_ai_summary([full_entity, minimal_entity])
    assert text.count("---") == 2


# ─────────────────────────────────────────────────────────────────────────────
# save_ai_summary
# ─────────────────────────────────────────────────────────────────────────────


def test_save_creates_file(tmp_path, full_entity):
    path = tmp_path / "out.md"
    save_ai_summary([full_entity], path)
    assert path.exists()


def test_save_content_matches_format(tmp_path, full_entity):
    path = tmp_path / "out.md"
    save_ai_summary([full_entity], path, query="маникюр", city="Уфа")
    content = path.read_text(encoding="utf-8")
    assert "Colorstar Nail Studio" in content
    assert '"маникюр"' in content


def test_save_creates_parent_dirs(tmp_path, full_entity):
    path = tmp_path / "nested" / "deep" / "out.md"
    save_ai_summary([full_entity], path)
    assert path.exists()


def test_save_utf8_encoding(tmp_path, full_entity):
    """Файл сохраняется в UTF-8 без escape-последовательностей."""
    path = tmp_path / "utf8.md"
    save_ai_summary([full_entity], path)
    content = path.read_text(encoding="utf-8")
    assert "Маникюр" in content
    assert "\\u" not in content
