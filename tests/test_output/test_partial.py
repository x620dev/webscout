"""Тесты для модуля partial.py (частичные результаты и --append)."""

import json
from pathlib import Path

import pytest

from src.core.models import ScrapedEntity
from src.output.partial import get_seen_urls, load_existing, save_partial


class SimpleEntity(ScrapedEntity):
    name: str


# ─────────────────────────────────────────────────────────────────────────────
# load_existing
# ─────────────────────────────────────────────────────────────────────────────


def test_load_existing_returns_empty_for_missing_file(tmp_path):
    """load_existing возвращает [] если файл не существует."""
    result = load_existing(tmp_path / "nonexistent.json")
    assert result == []


def test_load_existing_loads_list(tmp_path):
    """load_existing загружает список из файла."""
    path = tmp_path / "data.json"
    data = [{"name": "Студия", "source": "yandex_maps", "source_url": "https://example.com"}]
    path.write_text(json.dumps(data), encoding="utf-8")

    result = load_existing(path)
    assert len(result) == 1
    assert result[0]["name"] == "Студия"


def test_load_existing_returns_empty_for_invalid_json(tmp_path):
    """load_existing возвращает [] для некорректного JSON."""
    path = tmp_path / "broken.json"
    path.write_text("not valid json", encoding="utf-8")
    result = load_existing(path)
    assert result == []


def test_load_existing_returns_empty_for_non_list(tmp_path):
    """load_existing возвращает [] если файл содержит не список."""
    path = tmp_path / "dict.json"
    path.write_text(json.dumps({"key": "value"}), encoding="utf-8")
    result = load_existing(path)
    assert result == []


# ─────────────────────────────────────────────────────────────────────────────
# get_seen_urls
# ─────────────────────────────────────────────────────────────────────────────


def test_get_seen_urls_extracts_urls():
    """get_seen_urls извлекает source_url из списка записей."""
    entities = [
        {"source_url": "https://example.com/1"},
        {"source_url": "https://example.com/2"},
    ]
    result = get_seen_urls(entities)
    assert result == {"https://example.com/1", "https://example.com/2"}


def test_get_seen_urls_skips_missing():
    """get_seen_urls пропускает записи без source_url."""
    entities = [
        {"source_url": "https://example.com/1"},
        {"name": "без url"},
    ]
    result = get_seen_urls(entities)
    assert result == {"https://example.com/1"}


def test_get_seen_urls_empty_list():
    """get_seen_urls возвращает пустое множество для пустого списка."""
    result = get_seen_urls([])
    assert result == set()


# ─────────────────────────────────────────────────────────────────────────────
# save_partial
# ─────────────────────────────────────────────────────────────────────────────


def test_save_partial_creates_file(tmp_path, capsys):
    """save_partial создаёт JSON-файл."""
    entities = [
        SimpleEntity(name="Тест", source="test", source_url="https://example.com")
    ]
    path = tmp_path / "partial.json"
    save_partial(entities, path, total=10)
    assert path.exists()


def test_save_partial_valid_json(tmp_path, capsys):
    """save_partial сохраняет валидный JSON."""
    entities = [
        SimpleEntity(name="Студия A", source="yandex_maps", source_url="https://a.ru"),
        SimpleEntity(name="Студия B", source="2gis", source_url="https://b.ru"),
    ]
    path = tmp_path / "partial.json"
    save_partial(entities, path, total=100)

    data = json.loads(path.read_text(encoding="utf-8"))
    assert len(data) == 2
    assert data[0]["name"] == "Студия A"


def test_save_partial_prints_message(tmp_path, capsys):
    """save_partial выводит сообщение о количестве сохранённых записей."""
    entities = [
        SimpleEntity(name="X", source="test", source_url="https://x.ru")
    ]
    path = tmp_path / "partial.json"
    save_partial(entities, path, total=50)

    captured = capsys.readouterr()
    assert "1" in captured.out
    assert "50" in captured.out


def test_save_partial_creates_parent_dirs(tmp_path, capsys):
    """save_partial создаёт родительские директории."""
    entities = [
        SimpleEntity(name="X", source="test", source_url="https://x.ru")
    ]
    path = tmp_path / "nested" / "dir" / "partial.json"
    save_partial(entities, path, total=1)
    assert path.exists()


def test_save_partial_accepts_dicts(tmp_path, capsys):
    """save_partial принимает словари, а не только Pydantic-модели."""
    entities = [{"name": "Тест", "source_url": "https://example.com"}]
    path = tmp_path / "partial.json"
    save_partial(entities, path, total=1)

    data = json.loads(path.read_text(encoding="utf-8"))
    assert data[0]["name"] == "Тест"
