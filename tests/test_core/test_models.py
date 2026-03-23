"""Тесты для базовых моделей данных (core/models.py)."""

import pytest

from src.core.models import Contacts, GeoPoint, ScrapedEntity


# ─────────────────────────────────────────────────────────────────────────────
# Contacts
# ─────────────────────────────────────────────────────────────────────────────


def test_contacts_defaults():
    """Contacts создаётся с пустыми значениями по умолчанию."""
    c = Contacts()
    assert c.phone == []
    assert c.email is None
    assert c.website is None
    assert c.telegram is None
    assert c.instagram is None
    assert c.vk is None
    assert c.whatsapp is None


def test_contacts_full():
    """Contacts принимает все поля."""
    c = Contacts(
        phone=["+79991234567", "+79992345678"],
        email="info@example.com",
        website="https://example.com",
        telegram="@example",
        instagram="@example_ig",
        vk="https://vk.com/example",
        whatsapp="+79991234567",
    )
    assert len(c.phone) == 2
    assert c.email == "info@example.com"
    assert c.telegram == "@example"


def test_contacts_model_dump():
    """Contacts корректно сериализуется."""
    c = Contacts(phone=["+79991234567"])
    data = c.model_dump()
    assert data["phone"] == ["+79991234567"]
    assert data["email"] is None


# ─────────────────────────────────────────────────────────────────────────────
# GeoPoint
# ─────────────────────────────────────────────────────────────────────────────


def test_geopoint_creation():
    """GeoPoint создаётся с координатами."""
    point = GeoPoint(lat=54.735152, lon=55.958736)
    assert point.lat == pytest.approx(54.735152)
    assert point.lon == pytest.approx(55.958736)


def test_geopoint_model_dump():
    """GeoPoint корректно сериализуется."""
    point = GeoPoint(lat=55.751244, lon=37.618423)
    data = point.model_dump()
    assert "lat" in data
    assert "lon" in data


def test_geopoint_requires_lat_lon():
    """GeoPoint требует оба поля."""
    with pytest.raises(Exception):
        GeoPoint(lat=55.0)  # нет lon


# ─────────────────────────────────────────────────────────────────────────────
# ScrapedEntity
# ─────────────────────────────────────────────────────────────────────────────


def test_scraped_entity_required_fields():
    """ScrapedEntity требует source и source_url."""
    entity = ScrapedEntity(source="yandex_maps", source_url="https://yandex.ru/maps/org/1/")
    assert entity.source == "yandex_maps"
    assert entity.source_url == "https://yandex.ru/maps/org/1/"


def test_scraped_entity_auto_scraped_at():
    """ScrapedEntity автоматически проставляет scraped_at."""
    entity = ScrapedEntity(source="test", source_url="https://example.com")
    assert entity.scraped_at is not None
    assert "T" in entity.scraped_at  # ISO format


def test_scraped_entity_inheritance():
    """Можно создать подкласс ScrapedEntity с дополнительными полями."""
    class TestEntity(ScrapedEntity):
        name: str
        value: int = 0

    e = TestEntity(name="Тест", source="test", source_url="https://example.com")
    assert e.name == "Тест"
    assert e.value == 0
    assert e.source == "test"


def test_scraped_entity_model_dump():
    """ScrapedEntity корректно сериализуется."""
    entity = ScrapedEntity(source="hh", source_url="https://hh.ru/vacancy/1")
    data = entity.model_dump()
    assert data["source"] == "hh"
    assert data["source_url"] == "https://hh.ru/vacancy/1"
    assert "scraped_at" in data
