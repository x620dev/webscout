"""Тесты для модели Organization (tools/orgscout/models.py)."""

import pytest

from src.core.models import Contacts, GeoPoint
from src.tools.orgscout.models import Organization


def test_organization_minimal():
    """Organization создаётся с минимальным набором полей."""
    org = Organization(
        source="yandex_maps",
        source_url="https://yandex.ru/maps/org/colorstar/1/",
        name="Colorstar Nail Studio",
    )
    assert org.name == "Colorstar Nail Studio"
    assert org.source == "yandex_maps"
    assert org.address == ""
    assert org.type is None
    assert org.geo is None
    assert org.rating is None
    assert org.reviews_count is None
    assert org.categories == []
    assert org.services == []
    assert org.photos == []
    assert org.online_booking is None
    assert org.notes is None


def test_organization_full():
    """Organization принимает все поля."""
    org = Organization(
        source="twogis",
        source_url="https://2gis.ru/firm/123",
        name="Студия маникюра",
        type="студия",
        address="ул. Ленина, 1",
        geo=GeoPoint(lat=54.74, lon=55.96),
        contacts=Contacts(phone=["+79991234567"], website="https://example.com"),
        working_hours="Пн–Пт 9:00–20:00",
        rating=4.8,
        reviews_count=120,
        categories=["Маникюр", "Педикюр"],
        services=["Маникюр", "Гель-лак"],
        online_booking="https://yclients.com/company/123",
        photos=["https://example.com/photo1.jpg"],
        notes="Ведущий мастер — Анна",
    )
    assert org.type == "студия"
    assert org.rating == pytest.approx(4.8)
    assert org.reviews_count == 120
    assert org.geo.lat == pytest.approx(54.74)
    assert org.geo.lon == pytest.approx(55.96)
    assert org.contacts.phone == ["+79991234567"]
    assert org.online_booking == "https://yclients.com/company/123"


def test_organization_address_string():
    """Organization.address может быть строкой."""
    org = Organization(
        source="yandex_maps",
        source_url="https://example.com",
        name="Студия",
        address="ул. Пушкина, 10",
    )
    assert org.address == "ул. Пушкина, 10"


def test_organization_address_list():
    """Organization.address может быть списком (для сетей с несколькими адресами)."""
    org = Organization(
        source="yandex_maps",
        source_url="https://example.com",
        name="Сеть студий",
        address=["ул. Ленина, 1", "пр. Мира, 5"],
    )
    assert isinstance(org.address, list)
    assert len(org.address) == 2


def test_organization_model_dump():
    """Organization.model_dump() возвращает корректный словарь."""
    org = Organization(
        source="yandex_maps",
        source_url="https://yandex.ru/maps/org/1/",
        name="Тест",
        rating=4.5,
    )
    data = org.model_dump(mode="json")
    assert data["name"] == "Тест"
    assert data["source"] == "yandex_maps"
    assert data["rating"] == pytest.approx(4.5)
    assert "scraped_at" in data


def test_organization_default_contacts():
    """Organization создаётся с пустым объектом Contacts по умолчанию."""
    org = Organization(
        source="test",
        source_url="https://example.com",
        name="Студия",
    )
    assert isinstance(org.contacts, Contacts)
    assert org.contacts.phone == []
    assert org.contacts.email is None


def test_organization_inherits_scraped_entity():
    """Organization наследует scraped_at от ScrapedEntity."""
    org = Organization(
        source="yandex_maps",
        source_url="https://example.com",
        name="Тест",
    )
    assert org.scraped_at is not None
    assert "T" in org.scraped_at  # ISO format


def test_organization_serialization_roundtrip():
    """Organization сериализуется и восстанавливается без потерь."""
    org = Organization(
        source="twogis",
        source_url="https://2gis.ru/firm/42",
        name="Colorstar",
        categories=["Маникюр"],
        contacts=Contacts(phone=["+79991234567"]),
        rating=4.9,
        reviews_count=200,
    )
    data = org.model_dump(mode="json")
    restored = Organization(**data)
    assert restored.name == org.name
    assert restored.rating == org.rating
    assert restored.contacts.phone == org.contacts.phone
