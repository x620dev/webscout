"""Тесты для CSV-writer (TSV-формат)."""

import csv
from pathlib import Path

import pytest

from src.core.models import Contacts, ScrapedEntity
from src.output.csv_writer import _flatten, save_csv


class SampleEntity(ScrapedEntity):
    name: str
    value: int = 0
    tags: list[str] = []
    contacts: Contacts = Contacts()


@pytest.fixture
def sample_entity():
    return SampleEntity(
        name="Маникюрный Рай",
        value=100,
        tags=["маникюр", "педикюр"],
        contacts=Contacts(
            phone=["+79051234567", "+79059876543"],
            email="info@example.com",
            website="https://example.com",
        ),
        source="yandex_maps",
        source_url="https://yandex.ru/maps/org/manrai/123/",
    )


def test_flatten_simple():
    """_flatten разворачивает плоский словарь."""
    d = {"a": "1", "b": "2"}
    result = _flatten(d)
    assert result == {"a": "1", "b": "2"}


def test_flatten_nested():
    """_flatten разворачивает вложенный словарь."""
    d = {"outer": {"inner": "value"}}
    result = _flatten(d)
    assert result == {"outer_inner": "value"}


def test_flatten_list():
    """_flatten объединяет списки через '; '."""
    d = {"tags": ["a", "b", "c"]}
    result = _flatten(d)
    assert result["tags"] == "a; b; c"


def test_flatten_none():
    """_flatten заменяет None на пустую строку."""
    d = {"field": None}
    result = _flatten(d)
    assert result["field"] == ""


def test_save_csv_creates_file(tmp_path, sample_entity):
    """save_csv создаёт TSV-файл."""
    path = tmp_path / "output.tsv"
    save_csv([sample_entity], path)
    assert path.exists()


def test_save_csv_tab_delimiter(tmp_path, sample_entity):
    """Файл использует табуляцию как разделитель."""
    path = tmp_path / "output.tsv"
    save_csv([sample_entity], path)
    content = path.read_text(encoding="utf-8")
    first_line = content.splitlines()[0]
    assert "\t" in first_line


def test_save_csv_has_headers(tmp_path, sample_entity):
    """Первая строка — заголовок."""
    path = tmp_path / "output.tsv"
    save_csv([sample_entity], path)

    with open(path, encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f, delimiter="\t")
        headers = reader.fieldnames

    assert "name" in headers
    assert "source" in headers
    assert "source_url" in headers


def test_save_csv_multi_phones_semicolon(tmp_path, sample_entity):
    """Несколько телефонов объединяются через '; '."""
    path = tmp_path / "output.tsv"
    save_csv([sample_entity], path)

    with open(path, encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f, delimiter="\t")
        row = next(reader)

    assert "; " in row["contacts_phone"]
    assert "+79051234567" in row["contacts_phone"]
    assert "+79059876543" in row["contacts_phone"]


def test_save_csv_nested_contacts(tmp_path, sample_entity):
    """Вложенный объект Contacts разворачивается в отдельные колонки."""
    path = tmp_path / "output.tsv"
    save_csv([sample_entity], path)

    with open(path, encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f, delimiter="\t")
        headers = reader.fieldnames

    assert "contacts_phone" in headers
    assert "contacts_email" in headers
    assert "contacts_website" in headers


def test_save_csv_empty_list_no_file(tmp_path):
    """Пустой список — файл не создаётся."""
    path = tmp_path / "empty.tsv"
    save_csv([], path)
    assert not path.exists()


def test_save_csv_creates_parent_dirs(tmp_path, sample_entity):
    """save_csv создаёт родительские директории."""
    path = tmp_path / "nested" / "dir" / "output.tsv"
    save_csv([sample_entity], path)
    assert path.exists()


def test_save_csv_cyrillic(tmp_path, sample_entity):
    """Кирилличные данные сохраняются корректно."""
    path = tmp_path / "cyrillic.tsv"
    save_csv([sample_entity], path)
    content = path.read_text(encoding="utf-8")
    assert "Маникюрный Рай" in content


def test_save_csv_multiple_rows(tmp_path, sample_entity):
    """Несколько сущностей — несколько строк в файле."""
    entity2 = SampleEntity(
        name="Студия 2",
        source="2gis",
        source_url="https://2gis.ru/ufa/firm/2/",
    )
    path = tmp_path / "multi.tsv"
    save_csv([sample_entity, entity2], path)

    with open(path, encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f, delimiter="\t")
        rows = list(reader)

    assert len(rows) == 2
    assert rows[0]["name"] == "Маникюрный Рай"
    assert rows[1]["name"] == "Студия 2"


def test_save_csv_custom_fieldnames(tmp_path, sample_entity):
    """save_csv уважает переданный порядок fieldnames."""
    path = tmp_path / "custom.tsv"
    save_csv([sample_entity], path, fieldnames=["name", "source", "source_url"])

    with open(path, encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f, delimiter="\t")
        headers = list(reader.fieldnames)

    assert headers == ["name", "source", "source_url"]
