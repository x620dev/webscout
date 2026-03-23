"""Тесты для JSON-writer."""

import json
from pathlib import Path

import pytest

from src.core.models import Contacts, ScrapedEntity
from src.output.json_writer import save_json


class SampleEntity(ScrapedEntity):
    name: str
    value: int = 0


@pytest.fixture
def sample_entity():
    return SampleEntity(
        name="Тест Студия",
        value=42,
        source="yandex_maps",
        source_url="https://yandex.ru/maps/org/test/1/",
    )


def test_save_json_creates_file(tmp_path, sample_entity):
    """save_json создаёт JSON-файл."""
    path = tmp_path / "output.json"
    save_json([sample_entity], path)
    assert path.exists()


def test_save_json_valid_json(tmp_path, sample_entity):
    """save_json сохраняет валидный JSON."""
    path = tmp_path / "output.json"
    save_json([sample_entity], path)
    data = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(data, list)
    assert len(data) == 1
    assert data[0]["name"] == "Тест Студия"
    assert data[0]["value"] == 42


def test_save_json_multiple_entities(tmp_path, sample_entity):
    """save_json сохраняет несколько сущностей."""
    entity2 = SampleEntity(
        name="Другая студия",
        source="2gis",
        source_url="https://2gis.ru/ufa/firm/2/",
    )
    path = tmp_path / "multi.json"
    save_json([sample_entity, entity2], path)
    data = json.loads(path.read_text(encoding="utf-8"))
    assert len(data) == 2
    assert data[1]["name"] == "Другая студия"


def test_save_json_pretty(tmp_path, sample_entity):
    """pretty=True создаёт форматированный JSON с отступами."""
    path = tmp_path / "pretty.json"
    save_json([sample_entity], path, pretty=True)
    content = path.read_text(encoding="utf-8")
    assert "\n" in content


def test_save_json_compact(tmp_path, sample_entity):
    """pretty=False создаёт компактный JSON."""
    path = tmp_path / "compact.json"
    save_json([sample_entity], path, pretty=False)
    content = path.read_text(encoding="utf-8")
    assert content.startswith("[{")


def test_save_json_creates_parent_dirs(tmp_path, sample_entity):
    """save_json создаёт родительские директории при необходимости."""
    path = tmp_path / "nested" / "dir" / "output.json"
    save_json([sample_entity], path)
    assert path.exists()


def test_save_json_cyrillic(tmp_path, sample_entity):
    """save_json корректно сохраняет кириллицу (ensure_ascii=False)."""
    path = tmp_path / "cyrillic.json"
    save_json([sample_entity], path)
    content = path.read_text(encoding="utf-8")
    assert "Тест Студия" in content
    assert "\\u" not in content


def test_save_json_empty_list(tmp_path):
    """save_json сохраняет пустой список."""
    path = tmp_path / "empty.json"
    save_json([], path)
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data == []
