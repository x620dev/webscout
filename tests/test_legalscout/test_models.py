"""Тесты моделей LegalScout."""

import pytest

from src.tools.legalscout.models import LegalEntity


def test_legal_entity_minimal():
    """LegalEntity создаётся с минимальными обязательными полями."""
    entity = LegalEntity(
        source="egrul",
        source_url="https://egrul.nalog.ru/",
        name='ООО "КОЛОРСТАР"',
        inn="0277123456",
    )
    assert entity.source == "egrul"
    assert entity.name == 'ООО "КОЛОРСТАР"'
    assert entity.inn == "0277123456"
    assert entity.ogrn is None
    assert entity.director is None
    assert entity.founders == []
    assert entity.status is None
    assert entity.scraped_at is not None


def test_legal_entity_full():
    """LegalEntity создаётся со всеми полями."""
    entity = LegalEntity(
        source="rusprofile",
        source_url="https://www.rusprofile.ru/id/12345",
        name='ООО "КОЛОРСТАР"',
        short_name="Колорстар",
        inn="0277123456",
        ogrn="1027700000000",
        registration_date="15.04.2010",
        address="Республика Башкортостан, г. Уфа, ул. Ленина, д. 1",
        director="Иванов Иван Иванович",
        founders=["Иванов И.И.", "Петров П.П."],
        status="действующее",
        main_activity="86.90 Прочая деятельность в области здравоохранения",
        authorized_capital=10_000,
        employee_count="до 15 человек",
    )
    assert entity.short_name == "Колорстар"
    assert entity.ogrn == "1027700000000"
    assert entity.registration_date == "15.04.2010"
    assert entity.director == "Иванов Иван Иванович"
    assert len(entity.founders) == 2
    assert entity.status == "действующее"
    assert entity.authorized_capital == 10_000
    assert entity.employee_count == "до 15 человек"


def test_legal_entity_serialization():
    """LegalEntity корректно сериализуется в dict/JSON."""
    entity = LegalEntity(
        source="egrul",
        source_url="https://egrul.nalog.ru/",
        name="ООО Тест",
        inn="1234567890",
        status="действующее",
    )
    data = entity.model_dump(mode="json")
    assert data["source"] == "egrul"
    assert data["name"] == "ООО Тест"
    assert data["inn"] == "1234567890"
    assert data["founders"] == []


def test_legal_entity_inherits_scraped_entity():
    """LegalEntity наследует поля ScrapedEntity."""
    from src.core.models import ScrapedEntity
    entity = LegalEntity(
        source="egrul",
        source_url="https://egrul.nalog.ru/",
        name="ООО Тест",
        inn="1234567890",
    )
    assert isinstance(entity, ScrapedEntity)
    assert hasattr(entity, "scraped_at")
